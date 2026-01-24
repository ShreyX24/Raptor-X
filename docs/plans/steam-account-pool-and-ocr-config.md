# Steam Account Pool Implementation Plan

> **STATUS: SAVED FOR LATER** - Complete E2E automation testing for all 12 games first, then implement this feature.

## Overview
Implement a centralized **Account Pool Manager** for multi-SUT automation:
- **Multiple account pairs** (3 initially, scalable to N)
- Each pair has: **A-F account** (games starting A-F) + **G-Z account** (games G-Z)
- **Concurrency control**: Steam allows only 1 user per account simultaneously
- **Per-session allocation**: SUT acquires account pair at session start, holds until session ends

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Service Manager UI                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Steam Account Pairs (configurable like OmniParser) │    │
│  │  Pair 1: arlrauto / arlrauto1                       │    │
│  │  Pair 2: arlrauto2 / arlrauto3                      │    │
│  │  Pair 3: arlrauto4 / arlrauto5                      │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (STEAM_ACCOUNT_PAIRS env var)
┌─────────────────────────────────────────────────────────────┐
│                     Gemma Backend                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Account Pool Manager                    │    │
│  │  - Pool of account pairs                            │    │
│  │  - Track: which SUT has which pair                  │    │
│  │  - acquire_account_pair(sut_id) → pair              │    │
│  │  - release_account_pair(sut_id)                     │    │
│  │  - get_account_for_game(sut_id, game_name)          │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│  ┌───────────────────────────┴───────────────────────┐      │
│  │            Automation Orchestrator                 │      │
│  │  1. acquire_account_pair(sut_id) at session start  │      │
│  │  2. For each game: get correct account from pair   │      │
│  │  3. login_steam() before game launch               │      │
│  │  4. release_account_pair(sut_id) at session end    │      │
│  └────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (HTTP: /login_steam)
┌─────────────────────────────────────────────────────────────┐
│                    SUT Client (per machine)                  │
│  - Executes steam.exe -login username password              │
│  - Already implemented in sut_client/steam.py               │
└─────────────────────────────────────────────────────────────┘
```

---

## Files to Modify

### 1. `service_manager/src/service_manager/settings.py`
Add Steam account pair storage (like OmniParserServer list):

```python
@dataclass
class SteamAccountPair:
    """A pair of Steam accounts: one for A-F games, one for G-Z games"""
    name: str           # e.g., "Pair 1"
    af_username: str    # Account for games A-F
    af_password: str
    gz_username: str    # Account for games G-Z
    gz_password: str
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "af_username": self.af_username,
            "af_password": self.af_password,
            "gz_username": self.gz_username,
            "gz_password": self.gz_password,
            "enabled": self.enabled,
        }
```

Add to `SettingsManager`:
- `self._steam_account_pairs: List[SteamAccountPair] = []`
- `get/set_steam_account_pairs()` methods
- `get_steam_account_pairs_env()` - returns JSON for env var

---

### 2. `service_manager/src/service_manager/ui/settings_dialog.py`
Add `SteamAccountPairsTab` widget (like OmniParserServersTab):
- List of account pairs with add/remove buttons
- Each pair shows: Name, A-F account, G-Z account
- Edit dialog for username/password (passwords masked)

---

### 3. `service_manager/src/service_manager/services/process_manager.py`
Inject `STEAM_ACCOUNT_PAIRS` env var when starting gemma-backend:
```python
if name == "gemma-backend":
    pairs_json = settings.get_steam_account_pairs_env()
    if pairs_json:
        env.insert("STEAM_ACCOUNT_PAIRS", pairs_json)
```

---

### 4. NEW: `Gemma/backend/core/account_pool.py`
Create new Account Pool Manager:

```python
import threading
import json
import os
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class AccountPair:
    def __init__(self, name: str, af_user: str, af_pass: str, gz_user: str, gz_pass: str):
        self.name = name
        self.af_username = af_user
        self.af_password = af_pass
        self.gz_username = gz_user
        self.gz_password = gz_pass

class AccountPoolManager:
    """Thread-safe manager for Steam account pair allocation.

    Each SUT acquires an account pair for its session.
    Steam only allows 1 concurrent user per account.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._pairs: List[AccountPair] = []
        self._allocations: Dict[str, AccountPair] = {}  # sut_id -> pair
        self._load_from_env()

    def _load_from_env(self):
        """Load account pairs from STEAM_ACCOUNT_PAIRS env var."""
        pairs_json = os.environ.get("STEAM_ACCOUNT_PAIRS", "[]")
        try:
            pairs_data = json.loads(pairs_json)
            for p in pairs_data:
                if p.get("enabled", True):
                    self._pairs.append(AccountPair(
                        p["name"], p["af_username"], p["af_password"],
                        p["gz_username"], p["gz_password"]
                    ))
            logger.info(f"Loaded {len(self._pairs)} Steam account pairs")
        except json.JSONDecodeError:
            logger.error("Invalid STEAM_ACCOUNT_PAIRS format")

    def acquire_account_pair(self, sut_id: str) -> Optional[AccountPair]:
        """Acquire an available account pair for a SUT session.

        Returns None if no pairs available.
        """
        with self._lock:
            # Check if SUT already has a pair
            if sut_id in self._allocations:
                return self._allocations[sut_id]

            # Find first unallocated pair
            allocated_pairs = set(self._allocations.values())
            for pair in self._pairs:
                if pair not in allocated_pairs:
                    self._allocations[sut_id] = pair
                    logger.info(f"Allocated {pair.name} to SUT {sut_id}")
                    return pair

            logger.warning(f"No account pairs available for SUT {sut_id}")
            return None

    def release_account_pair(self, sut_id: str):
        """Release account pair when SUT session ends."""
        with self._lock:
            if sut_id in self._allocations:
                pair = self._allocations.pop(sut_id)
                logger.info(f"Released {pair.name} from SUT {sut_id}")

    def get_account_for_game(self, sut_id: str, game_name: str) -> Optional[Tuple[str, str]]:
        """Get (username, password) for a game based on SUT's allocated pair."""
        with self._lock:
            pair = self._allocations.get(sut_id)
            if not pair:
                return None

            first_letter = game_name[0].upper() if game_name else 'Z'
            if 'A' <= first_letter <= 'F':
                return (pair.af_username, pair.af_password)
            else:
                return (pair.gz_username, pair.gz_password)

    def get_status(self) -> Dict:
        """Get current allocation status for monitoring."""
        with self._lock:
            return {
                "total_pairs": len(self._pairs),
                "available": len(self._pairs) - len(self._allocations),
                "allocations": {sut: pair.name for sut, pair in self._allocations.items()}
            }

# Global singleton
_account_pool: Optional[AccountPoolManager] = None

def get_account_pool() -> AccountPoolManager:
    global _account_pool
    if _account_pool is None:
        _account_pool = AccountPoolManager()
    return _account_pool
```

---

### 5. `Gemma/backend/core/automation_orchestrator.py`
Integrate account pool with smart switching:

```python
from .account_pool import get_account_pool

# In execute_run() - at session start:
def execute_run(self, run: AutomationRun):
    account_pool = get_account_pool()
    sut_id = run.sut_device_id or run.sut_ip
    current_steam_user = None  # Track current logged-in user

    # Acquire account pair for this SUT session
    pair = account_pool.acquire_account_pair(sut_id)
    if not pair:
        return False, None, "No Steam account pairs available"

    try:
        for game in games_to_run:
            # Get required account for this game
            account = account_pool.get_account_for_game(sut_id, game.name)
            if account:
                username, password = account
                # Only switch if different from current
                if username != current_steam_user:
                    logger.info(f"Switching Steam: {current_steam_user} → {username}")
                    network.login_steam(username, password)
                    current_steam_user = username
                else:
                    logger.info(f"Already on {username}, skipping switch")

            # ... launch game ...
    finally:
        # Release at session end
        account_pool.release_account_pair(sut_id)
```

**Smart Switching Example** (BMW → Cyberpunk → SOTR → RDR2):
```
Game: Black Myth Wukong (B) → Need A-F account
  → Switch to arlrauto ✓

Game: Cyberpunk 2077 (C) → Need A-F account
  → Already on arlrauto, skip switch ✓

Game: SOTR (S) → Need G-Z account
  → Switch to arlrauto1 ✓

Game: RDR2 (R) → Need G-Z account
  → Already on arlrauto1, skip switch ✓
```

---

### 6. `Gemma/backend/api/routes.py` (Optional)
Add API endpoint for monitoring:
```python
@app.route('/api/account-pool/status', methods=['GET'])
def get_account_pool_status():
    from ..core.account_pool import get_account_pool
    return jsonify(get_account_pool().get_status())
```

---

## Data Flow

```
Service Manager UI → settings.json → ProcessManager (STEAM_ACCOUNT_PAIRS env)
→ Gemma Backend → AccountPoolManager (singleton)
→ AutomationOrchestrator.execute_run():
    1. acquire_account_pair(sut_id) at session start
    2. For each game: get_account_for_game(sut_id, game_name)
    3. network.login_steam(username, password)
    4. release_account_pair(sut_id) at session end
→ SUT /login_steam endpoint → steam.exe -login
```

---

## Account Pair Configuration (Example)

| Pair | A-F Account | G-Z Account |
|------|-------------|-------------|
| Pair 1 | arlrauto | arlrauto1 |
| Pair 2 | arlrauto2 | arlrauto3 |
| Pair 3 | arlrauto4 | arlrauto5 |

When 3 SUTs run simultaneously:
- SUT-1 gets Pair 1 → uses arlrauto for Cyberpunk, arlrauto1 for Hitman
- SUT-2 gets Pair 2 → uses arlrauto2 for Far Cry, arlrauto3 for RDR2
- SUT-3 gets Pair 3 → uses arlrauto4 for BMW, arlrauto5 for SOTR

---

## Game → Account Mapping

| Game Name | First Letter | Uses Account |
|-----------|--------------|--------------|
| Black Myth Wukong | B | A-F account from pair |
| Cyberpunk 2077 | C | A-F account from pair |
| Far Cry 6 | F | A-F account from pair |
| Hitman 3 | H | G-Z account from pair |
| Mirage | M | G-Z account from pair |
| Shadow of the Tomb Raider | S | G-Z account from pair |

---

## Implementation Order

1. **Settings** (settings.py) - SteamAccountPair dataclass + list storage
2. **UI** (settings_dialog.py) - SteamAccountPairsTab with add/remove/edit
3. **Env injection** (process_manager.py) - Pass pairs JSON to backend
4. **Account Pool** (NEW account_pool.py) - Thread-safe pool manager
5. **Orchestrator** (automation_orchestrator.py) - Acquire/release/switch integration
6. **API** (routes.py) - Optional monitoring endpoint

---

## Existing Code (No Changes Needed)

- `sut_client/src/sut_client/steam.py` - Already has `login_steam()`
- `Gemma/modules/network.py` - Already has `login_steam()` that calls SUT
- SUT `/login_steam` endpoint - Already functional

---

---

# Per-Game Per-Step OmniParser OCR Configuration

> **STATUS: IMPLEMENTED** - Completed on 2025-12-27

## Overview
Implemented per-request OCR configuration for OmniParser to handle games with stylized fonts (like Hitman 3) that PaddleOCR struggles with.

## Key Features
- **Per-request OCR params**: Each OmniParser request can specify its own OCR settings
- **Game-level defaults**: Set default OCR config in game YAML metadata
- **Per-step overrides**: Override OCR config at individual step level
- **Automatic fallback**: Try alternative OCR configs when target text not found
- **Config caching**: Save successful configs for future runs

## Files Modified

### 1. OmniParser Server (`Omniparser server/omnitool/omniparserserver/omniparserserver.py`)
Extended `ParseRequest` model to accept per-request params:
```python
class ParseRequest(BaseModel):
    base64_image: str
    box_threshold: float = None  # YOLO detection confidence threshold
    iou_threshold: float = None  # IOU threshold for overlap removal
    use_paddleocr: bool = None   # True = PaddleOCR, False = EasyOCR
    text_threshold: float = None # OCR confidence threshold
    use_local_semantics: bool = None  # Use caption model for icons
    scale_img: bool = None       # Scale image before processing
    imgsz: int = None            # Image size for YOLO model
```

### 2. Omniparser Class (`Omniparser server/util/omniparser.py`)
Updated `parse()` to accept override config:
```python
def parse(self, image_base64: str, override_config: dict = None):
    # Merge startup config with per-request overrides
    use_paddleocr = override_config.get('use_paddleocr', self.config.get('use_paddleocr', True))
    # ... etc
```

### 3. Queue Service (`queue_service/src/queue_service/queue_manager.py`)
Extended `ParseRequest` model with all OCR params (passed through to OmniParser).

### 4. OmniparserClient (`Gemma/modules/omniparser_client.py`)
- Added `DEFAULT_OCR_CONFIG` with default values
- Added `FALLBACK_OCR_CONFIGS` list for automatic fallback attempts
- Updated `detect_ui_elements()` to accept `ocr_config` parameter
- Added `detect_ui_elements_with_fallback()` for automatic retry with different configs

### 5. SimpleAutomation (`Gemma/modules/simple_automation.py`)
- Reads OCR config from game YAML (`metadata.ocr_config`)
- Supports per-step OCR config overrides (`step.ocr_config`)
- Uses `detect_ui_elements_with_fallback()` when target text specified
- Caches successful configs per step
- Saves successful configs to `successful_ocr_configs.yaml`

## OCR Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `box_threshold` | float | 0.05 | YOLO detection confidence |
| `iou_threshold` | float | 0.1 | IOU threshold for overlap removal |
| `use_paddleocr` | bool | True | True=PaddleOCR, False=EasyOCR |
| `text_threshold` | float | 0.8 | OCR confidence threshold |
| `use_local_semantics` | bool | True | Use caption model for icons |
| `scale_img` | bool | False | Scale image before processing |
| `imgsz` | int | None | Image size for YOLO (None=original) |

## Fallback OCR Configs
When target text not found, tries these configs in order:
1. Lower text threshold (0.5) with PaddleOCR
2. EasyOCR with text threshold 0.7
3. Lower box threshold (0.03) + text threshold 0.6
4. EasyOCR with very lenient threshold (0.5)

## Game YAML Example (Hitman 3)
```yaml
metadata:
  game_name: Hitman 3 Free Starter Pack
  use_ocr_fallback: true  # Enable automatic OCR config fallback
  ocr_config:  # Game-level defaults
    use_paddleocr: false  # EasyOCR for stylized fonts
    text_threshold: 0.6
steps:
  1:
    description: Click OPTIONS button
    find:
      type: any
      text: OPTIONS
    ocr_config:  # Per-step override (optional)
      text_threshold: 0.5
    action:
      type: click
```

## Data Flow
```
Game YAML → SimpleAutomation (reads ocr_config)
→ OmniparserClient.detect_ui_elements(ocr_config=...)
→ Queue Service (passes params)
→ OmniParser Server (applies overrides)
→ Returns detected elements with config used
→ SimpleAutomation caches successful config
```

---

# Future Plans: OpenSSH for SUT Client & Discovery

## Exploration Goals
- Investigate using OpenSSH as alternative/complement to HTTP-based SUT client
- Evaluate SSH for SUT discovery (replacing/enhancing current discovery service)
- Consider SSH tunneling for secure multi-SUT communication across networks

## Potential Benefits
- **Direct remote execution**: Run commands on SUTs without HTTP server
- **Secure channel**: SSH provides encryption, authentication
- **Reduced client complexity**: May not need full SUT client running
- **Remote file access**: SCP for transferring screenshots, logs, presets
- **Port forwarding**: Access SUT services through SSH tunnels

## Areas to Explore
1. **SSH-based SUT discovery**: Scan network for SSH-enabled SUTs, verify identity
2. **Remote command execution**: Launch games, take screenshots via SSH
3. **Hybrid approach**: SSH for control plane, HTTP for data plane (screenshots)
4. **Authentication**: SSH key management across multiple SUTs
5. **Current working SSH setup**: ZEL-X7 already has OpenSSH configured
