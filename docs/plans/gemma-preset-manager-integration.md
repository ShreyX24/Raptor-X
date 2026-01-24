# Gemma + Preset-Manager Integration Plan (Final)

## Architecture Overview

**Branch:** `pre-prod/v6-pm-gemma-merger`

The **SUT Discovery Service** is the **SINGLE GATEWAY** for all SUT communication. Neither Preset-Manager nor Gemma talk directly to SUTs.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SUT DISCOVERY SERVICE (Port 5001)                     │
│              ** SINGLE GATEWAY FOR ALL SUT COMMUNICATION **              │
│                                                                         │
│  Responsibilities:                                                       │
│  - UDP Broadcast + WebSocket for SUT registration                       │
│  - Device registry with pairing                                         │
│  - PROXY all calls to SUTs:                                             │
│    • /api/suts/{id}/games      → SUT /installed_games                   │
│    • /api/suts/{id}/apply-preset → SUT /apply-preset                    │
│    • /api/suts/{id}/screenshot  → SUT /screenshot                       │
│    • /api/suts/{id}/action      → SUT /action                           │
│    • /api/suts/{id}/launch      → SUT /launch                           │
│    • /api/suts/{id}/status      → SUT /status                           │
└─────────────────────────────────────────────────────────────────────────┘
        ▲                           ▲                           ▲
        │                           │                           │
┌───────┴───────┐           ┌───────┴───────┐           ┌───────┴───────┐
│  GEMMA GUI    │           │ PRESET-MANAGER │           │  SUT CLIENT   │
│               │           │  (Port 5000)   │           │  (Port 8080)  │
│ NO internal   │           │ NO internal    │           │               │
│ discovery     │           │ discovery      │           │ Registers     │
│ NO mysuts.json│           │ Removed        │           │ with Discovery│
│               │           │                │           │ Service only  │
│ Calls Discovery│          │ Calls Discovery│           │               │
│ for everything│           │ for SUT proxy  │           │               │
└───────────────┘           └────────────────┘           └───────────────┘
```

**Preset Naming Convention:** `ppg-{quality}-{resolution}` (e.g., `ppg-high-1080p`)

---

## What Needs to Be Built

| Component | Location | Status |
|-----------|----------|--------|
| **Standalone Discovery Service** | `sut_discovery_service/` | ❌ NEW - with full SUT proxy |
| `/installed_games` endpoint | `sut_client/service.py` | ❌ Add endpoint |
| **Remove PM internal discovery** | `preset_manager/server.py` | ❌ Disable scanner/announcer |
| **PM Discovery Client** | `preset_manager/discovery_client.py` | ❌ NEW - calls Discovery Service |
| **Gemma Discovery Client** | `Gemma/modules/discovery_client.py` | ❌ NEW |
| **Gemma Preset Client** | `Gemma/modules/preset_manager_client.py` | ❌ NEW |
| Gemma GUI Integration | `Gemma/gui_app_multi_sut.py` | ❌ Modify - remove mysuts.json |
| Integration Config | `Gemma/config/integration_config.json` | ❌ NEW |

---

## Phase 1: Create Standalone SUT Discovery Service

### 1.1 Directory Structure

**New Directory:** `D:\Code\Gemma\sut_discovery_service\`

```
sut_discovery_service/
├── __init__.py
├── __main__.py                # python -m sut_discovery_service
├── main.py                    # FastAPI entry point
├── config.py                  # Configuration settings
├── requirements.txt
├── discovery/
│   ├── __init__.py
│   ├── device_registry.py     # COPY from preset-manager
│   ├── scanner.py             # COPY from preset-manager
│   ├── udp_announcer.py       # COPY from preset-manager
│   ├── websocket_manager.py   # COPY from preset-manager
│   └── events.py              # COPY from preset-manager
├── api/
│   ├── __init__.py
│   ├── suts.py                # SUT listing & management
│   └── proxy.py               # NEW: Proxy all SUT calls
└── utils/
    ├── __init__.py
    └── network.py             # COPY from preset-manager
```

### 1.2 Files to Copy from Preset-Manager

**Source:** `D:\Code\Gemma\preset-manager\src\preset_manager\`

| Source File | Destination | Changes |
|-------------|-------------|---------|
| `discovery/device_registry.py` | `discovery/` | Update imports |
| `discovery/scanner.py` | `discovery/` | Update imports |
| `discovery/udp_announcer.py` | `discovery/` | Update imports |
| `discovery/websocket_manager.py` | `discovery/` | Update imports |
| `discovery/events.py` | `discovery/` | As-is |
| `utils/network.py` | `utils/` | As-is |

### 1.3 API Endpoints

**SUT Management** (`api/suts.py`):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/suts` | GET | List all SUTs (query: status=online\|offline\|paired) |
| `/api/suts/{unique_id}` | GET | Get specific SUT details |
| `/api/suts/{unique_id}/pair` | POST | Pair SUT for priority scanning |
| `/api/suts/{unique_id}/unpair` | POST | Unpair SUT |
| `/api/discover` | POST | Trigger immediate scan |
| `/api/discover/status` | GET | Get discovery service status |
| `/api/ws/sut/{sut_id}` | WebSocket | SUT registration endpoint |

**SUT Proxy** (`api/proxy.py`) - **NEW**:

| Endpoint | Method | Proxies To |
|----------|--------|------------|
| `/api/suts/{unique_id}/games` | GET | SUT `/installed_games` |
| `/api/suts/{unique_id}/apply-preset` | POST | SUT `/apply-preset` |
| `/api/suts/{unique_id}/screenshot` | GET | SUT `/screenshot` |
| `/api/suts/{unique_id}/action` | POST | SUT `/action` |
| `/api/suts/{unique_id}/launch` | POST | SUT `/launch` |
| `/api/suts/{unique_id}/check-process` | POST | SUT `/check_process` |
| `/api/suts/{unique_id}/kill-process` | POST | SUT `/kill_process` |
| `/api/suts/{unique_id}/terminate-game` | POST | SUT `/terminate_game` |

### 1.4 Proxy Implementation

**Path:** `sut_discovery_service/api/proxy.py`

```python
"""
Proxy all SUT communication through Discovery Service.
Neither Gemma nor Preset-Manager talk directly to SUTs.
"""

from fastapi import APIRouter, HTTPException, Request, Response
import httpx
import logging

from ..discovery.device_registry import get_device_registry

logger = logging.getLogger(__name__)
router = APIRouter()

async def proxy_to_sut(unique_id: str, endpoint: str, method: str = "GET",
                       json_data: dict = None, timeout: float = 30.0) -> dict:
    """Proxy a request to a SUT."""
    registry = get_device_registry()
    device = registry.get_device_by_id(unique_id)

    if not device:
        raise HTTPException(status_code=404, detail=f"SUT {unique_id} not found")

    if not device.is_online:
        raise HTTPException(status_code=503, detail=f"SUT {unique_id} is offline")

    sut_url = f"http://{device.ip}:{device.port}{endpoint}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                response = await client.get(sut_url)
            elif method == "POST":
                response = await client.post(sut_url, json=json_data)
            else:
                raise HTTPException(status_code=405, detail=f"Method {method} not supported")

            return response.json()

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Timeout connecting to SUT {unique_id}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error proxying to SUT: {str(e)}")

@router.get("/suts/{unique_id}/games")
async def get_installed_games(unique_id: str):
    """Proxy to SUT /installed_games endpoint."""
    return await proxy_to_sut(unique_id, "/installed_games", "GET")

@router.post("/suts/{unique_id}/apply-preset")
async def apply_preset(unique_id: str, request: Request):
    """Proxy to SUT /apply-preset endpoint."""
    body = await request.json()
    return await proxy_to_sut(unique_id, "/apply-preset", "POST", body, timeout=60.0)

@router.get("/suts/{unique_id}/screenshot")
async def get_screenshot(unique_id: str):
    """Proxy to SUT /screenshot endpoint."""
    return await proxy_to_sut(unique_id, "/screenshot", "GET")

@router.post("/suts/{unique_id}/action")
async def send_action(unique_id: str, request: Request):
    """Proxy to SUT /action endpoint."""
    body = await request.json()
    return await proxy_to_sut(unique_id, "/action", "POST", body)

@router.post("/suts/{unique_id}/launch")
async def launch_game(unique_id: str, request: Request):
    """Proxy to SUT /launch endpoint."""
    body = await request.json()
    return await proxy_to_sut(unique_id, "/launch", "POST", body, timeout=120.0)

@router.post("/suts/{unique_id}/check-process")
async def check_process(unique_id: str, request: Request):
    """Proxy to SUT /check_process endpoint."""
    body = await request.json()
    return await proxy_to_sut(unique_id, "/check_process", "POST", body)

@router.post("/suts/{unique_id}/kill-process")
async def kill_process(unique_id: str, request: Request):
    """Proxy to SUT /kill_process endpoint."""
    body = await request.json()
    return await proxy_to_sut(unique_id, "/kill_process", "POST", body)

@router.post("/suts/{unique_id}/terminate-game")
async def terminate_game(unique_id: str):
    """Proxy to SUT /terminate_game endpoint."""
    return await proxy_to_sut(unique_id, "/terminate_game", "POST", {})
```

---

## Phase 2: Add /installed_games Endpoint to SUT Client

### 2.1 Modify service.py

**Path:** `D:\Code\Gemma\preset-manager\sut_client\src\sut_client\service.py`

Add endpoint (uses existing `steam.py`):

```python
@app.route('/installed_games', methods=['GET'])
def get_installed_games():
    """Scan Steam library folders and return installed games."""
    try:
        from .steam import get_steam_library_folders
        import os
        import re

        libraries = get_steam_library_folders()
        installed_games = []

        for lib in libraries:
            steamapps = os.path.join(lib, "steamapps")
            if not os.path.exists(steamapps):
                continue

            for filename in os.listdir(steamapps):
                if filename.startswith("appmanifest_") and filename.endswith(".acf"):
                    app_id = filename.replace("appmanifest_", "").replace(".acf", "")
                    manifest_path = os.path.join(steamapps, filename)

                    try:
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        name_match = re.search(r'"name"\s+"([^"]+)"', content)
                        installdir_match = re.search(r'"installdir"\s+"([^"]+)"', content)

                        if name_match and installdir_match:
                            game_name = name_match.group(1)
                            install_dir = installdir_match.group(1)
                            full_path = os.path.join(steamapps, "common", install_dir)

                            installed_games.append({
                                "steam_app_id": app_id,
                                "name": game_name,
                                "install_dir": install_dir,
                                "install_path": full_path,
                                "exists": os.path.exists(full_path)
                            })
                    except Exception as e:
                        logger.warning(f"Failed to parse {filename}: {e}")

        return jsonify({
            "success": True,
            "games": installed_games,
            "count": len(installed_games),
            "libraries_scanned": len(libraries)
        })
    except Exception as e:
        logger.error(f"Error getting installed games: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
```

---

## Phase 3: Remove Internal Discovery from Preset-Manager

### 3.1 Modify server.py

**Path:** `D:\Code\Gemma\preset-manager\src\preset_manager\server.py`

**Remove from startup:**
- Don't initialize `SUTDiscoveryService`
- Don't start `UDPAnnouncer`
- Don't start scanner thread

**Add:**
- Create `DiscoveryServiceClient` for external discovery

### 3.2 Create Discovery Client for Preset-Manager

**Path:** `D:\Code\Gemma\preset-manager\src\preset_manager\discovery_client.py`

```python
"""
Client for external SUT Discovery Service.
Preset-Manager no longer has internal discovery.
"""

import httpx
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DiscoveryServiceClient:
    """Client to communicate with standalone SUT Discovery Service."""

    def __init__(self, discovery_url: str = "http://localhost:5001"):
        self.discovery_url = discovery_url.rstrip("/")
        self.timeout = 10.0

    async def get_suts(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all SUTs from discovery service."""
        params = {"status": status} if status else {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.discovery_url}/api/suts", params=params)
            response.raise_for_status()
            return response.json().get("suts", [])

    async def get_sut(self, unique_id: str) -> Optional[Dict[str, Any]]:
        """Get specific SUT."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.discovery_url}/api/suts/{unique_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def get_sut_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """Find SUT by IP address."""
        suts = await self.get_suts()
        return next((s for s in suts if s.get("ip") == ip), None)

    async def get_installed_games(self, unique_id: str) -> List[Dict[str, Any]]:
        """Get installed games via proxy."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.discovery_url}/api/suts/{unique_id}/games")
            response.raise_for_status()
            return response.json().get("games", [])

    async def apply_preset(self, unique_id: str, preset_data: dict) -> Dict[str, Any]:
        """Apply preset via proxy."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.discovery_url}/api/suts/{unique_id}/apply-preset",
                json=preset_data
            )
            response.raise_for_status()
            return response.json()

    def is_available(self) -> bool:
        """Check if discovery service is available (sync version)."""
        import requests
        try:
            response = requests.get(f"{self.discovery_url}/health", timeout=3)
            return response.status_code == 200
        except:
            return False
```

### 3.3 Update sync.py to Use Discovery Client

**Path:** `D:\Code\Gemma\preset-manager\src\preset_manager\api\sync.py`

Modify to use `DiscoveryServiceClient` instead of internal `_device_registry`:

```python
# Replace direct SUT calls with Discovery Service proxy calls
async def sync_to_sut_via_discovery(discovery_client, unique_id, preset_data):
    """Apply preset to SUT via Discovery Service proxy."""
    return await discovery_client.apply_preset(unique_id, preset_data)
```

---

## Phase 4: Add Clients to Gemma

### 4.1 Create discovery_client.py

**Path:** `D:\Code\Gemma\Gemma\modules\discovery_client.py`

```python
"""
Client for SUT Discovery Service.
Gemma uses this for ALL SUT communication - no direct SUT access.
"""

import requests
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SUTInfo:
    unique_id: str
    ip: str
    port: int
    hostname: str
    status: str
    is_online: bool
    is_paired: bool
    display_name: Optional[str] = None
    cpu_model: Optional[str] = None
    capabilities: List[str] = None

class DiscoveryClient:
    """Client for SUT Discovery Service. All SUT calls go through here."""

    def __init__(self, discovery_url: str = "http://localhost:5001"):
        self.discovery_url = discovery_url.rstrip("/")
        self.timeout = 10

    # --- SUT Discovery ---

    def get_suts(self, status: Optional[str] = None) -> List[SUTInfo]:
        """Get all discovered SUTs."""
        params = {"status": status} if status else {}
        try:
            response = requests.get(
                f"{self.discovery_url}/api/suts",
                params=params, timeout=self.timeout
            )
            response.raise_for_status()
            return [self._to_sut_info(s) for s in response.json().get("suts", [])]
        except Exception as e:
            logger.error(f"Failed to get SUTs: {e}")
            return []

    def get_online_suts(self) -> List[SUTInfo]:
        return self.get_suts(status="online")

    def get_sut(self, unique_id: str) -> Optional[SUTInfo]:
        try:
            response = requests.get(
                f"{self.discovery_url}/api/suts/{unique_id}",
                timeout=self.timeout
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return self._to_sut_info(response.json())
        except Exception as e:
            logger.error(f"Failed to get SUT {unique_id}: {e}")
            return None

    # --- Proxy Methods (all SUT communication) ---

    def get_installed_games(self, unique_id: str) -> List[Dict[str, Any]]:
        """Get installed games on SUT via proxy."""
        try:
            response = requests.get(
                f"{self.discovery_url}/api/suts/{unique_id}/games",
                timeout=30
            )
            response.raise_for_status()
            return response.json().get("games", [])
        except Exception as e:
            logger.error(f"Failed to get games for {unique_id}: {e}")
            return []

    def send_action(self, unique_id: str, action: dict) -> dict:
        """Send input action to SUT via proxy."""
        try:
            response = requests.post(
                f"{self.discovery_url}/api/suts/{unique_id}/action",
                json=action, timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to send action to {unique_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_screenshot(self, unique_id: str) -> bytes:
        """Get screenshot from SUT via proxy."""
        try:
            response = requests.get(
                f"{self.discovery_url}/api/suts/{unique_id}/screenshot",
                timeout=30
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to get screenshot from {unique_id}: {e}")
            return None

    def launch_game(self, unique_id: str, launch_data: dict) -> dict:
        """Launch game on SUT via proxy."""
        try:
            response = requests.post(
                f"{self.discovery_url}/api/suts/{unique_id}/launch",
                json=launch_data, timeout=120
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to launch game on {unique_id}: {e}")
            return {"success": False, "error": str(e)}

    def check_process(self, unique_id: str, process_name: str) -> dict:
        """Check if process running on SUT via proxy."""
        try:
            response = requests.post(
                f"{self.discovery_url}/api/suts/{unique_id}/check-process",
                json={"process_name": process_name}, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to check process on {unique_id}: {e}")
            return {"running": False, "error": str(e)}

    def kill_process(self, unique_id: str, process_name: str) -> dict:
        """Kill process on SUT via proxy."""
        try:
            response = requests.post(
                f"{self.discovery_url}/api/suts/{unique_id}/kill-process",
                json={"process_name": process_name}, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to kill process on {unique_id}: {e}")
            return {"success": False, "error": str(e)}

    # --- Utility ---

    def is_service_available(self) -> bool:
        try:
            response = requests.get(f"{self.discovery_url}/health", timeout=3)
            return response.status_code == 200
        except:
            return False

    def _to_sut_info(self, data: dict) -> SUTInfo:
        return SUTInfo(
            unique_id=data.get("unique_id", ""),
            ip=data.get("ip", ""),
            port=data.get("port", 8080),
            hostname=data.get("hostname", ""),
            status=data.get("status", "unknown"),
            is_online=data.get("is_online", False),
            is_paired=data.get("is_paired", False),
            display_name=data.get("display_name"),
            cpu_model=data.get("cpu_model"),
            capabilities=data.get("capabilities", [])
        )
```

### 4.2 Create preset_manager_client.py

**Path:** `D:\Code\Gemma\Gemma\modules\preset_manager_client.py`

```python
"""
Client for Preset-Manager API.
Used by Gemma to apply PPG presets before automation.
"""

import requests
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PresetResult:
    sut_ip: str
    game: str
    success: bool
    preset_level: Optional[str] = None
    error: Optional[str] = None
    reason: Optional[str] = None

class PresetManagerClient:
    """Client for Preset-Manager API (port 5000)."""

    def __init__(self, preset_manager_url: str = "http://localhost:5000"):
        self.preset_manager_url = preset_manager_url.rstrip("/")
        self.timeout = 60

    def apply_presets(
        self,
        sut_ids: List[str],  # unique_ids, not IPs
        games: List[str],
        resolution: str = "1920x1080",
        graphics: str = "high"
    ) -> Dict[str, List[PresetResult]]:
        """Apply presets for games on SUTs."""
        try:
            payload = {
                "sut_ids": sut_ids,
                "games": games,
                "preset": {"resolution": resolution, "graphics": graphics}
            }
            response = requests.post(
                f"{self.preset_manager_url}/api/sync/gemma-presets",
                json=payload, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            return {
                "successful": [PresetResult(**item, success=True) for item in data.get("successful", [])],
                "failed": [PresetResult(**item, success=False) for item in data.get("failed", [])],
                "skipped": [PresetResult(**item, success=False) for item in data.get("skipped", [])]
            }
        except Exception as e:
            logger.error(f"Failed to apply presets: {e}")
            return {
                "successful": [],
                "failed": [PresetResult(sut_ip=sid, game=g, success=False, error=str(e))
                          for sid in sut_ids for g in games],
                "skipped": []
            }

    def get_available_games(self) -> List[Dict[str, Any]]:
        try:
            response = requests.get(f"{self.preset_manager_url}/api/games", timeout=self.timeout)
            response.raise_for_status()
            return response.json().get("games", [])
        except Exception as e:
            logger.error(f"Failed to get games: {e}")
            return []

    def is_service_available(self) -> bool:
        try:
            response = requests.get(f"{self.preset_manager_url}/health", timeout=3)
            return response.status_code == 200
        except:
            return False
```

---

## Phase 5: Update Gemma GUI

### 5.1 Modify gui_app_multi_sut.py

**Path:** `D:\Code\Gemma\Gemma\gui_app_multi_sut.py`

**Remove:**
- All `mysuts.json` loading/saving
- Manual SUT entry dialogs
- Direct SUT HTTP calls in `network.py`

**Add:**
- `DiscoveryClient` for all SUT communication
- `PresetManagerClient` for preset application
- SUT discovery panel with refresh button
- Preset selection panel (resolution, graphics dropdowns)
- Validation before automation
- Preset application step in `start_automation()`

**Key changes to network.py:**

The existing `NetworkManager` class should be replaced/modified to use `DiscoveryClient`:

```python
# OLD: Direct SUT communication
def send_action(self, action):
    return requests.post(f"http://{self.sut_ip}:{self.sut_port}/action", json=action)

# NEW: Via Discovery Service
def send_action(self, action):
    return self.discovery_client.send_action(self.sut_unique_id, action)
```

---

## Phase 6: Configuration File

### 6.1 Create integration_config.json

**Path:** `D:\Code\Gemma\Gemma\config\integration_config.json`

```json
{
  "discovery_service": {
    "url": "http://localhost:5001",
    "timeout": 10
  },
  "preset_manager": {
    "url": "http://localhost:5000",
    "timeout": 60
  },
  "defaults": {
    "resolution": "1920x1080",
    "graphics": "high"
  }
}
```

---

## Phase 5: Gemma Admin Frontend (React/TypeScript/Tailwind 4.0)

Replace tkinter `gui_app_multi_sut.py` with modern React frontend like preset-manager/admin.

### 5.1 Directory Structure

**New Directory:** `D:\Code\Gemma\Gemma\admin\`

```
Gemma/admin/
├── src/
│   ├── main.tsx                 # React entry point
│   ├── App.tsx                  # Main application
│   ├── index.css                # Tailwind @theme + custom styles
│   ├── api/
│   │   └── index.ts             # API client (Discovery + PM)
│   ├── types/
│   │   └── index.ts             # TypeScript interfaces
│   └── components/
│       ├── SUTCard.tsx          # SUT selection card
│       ├── GameCard.tsx         # Game selection card
│       ├── PresetSelector.tsx   # Resolution/Graphics dropdowns
│       ├── AutomationPanel.tsx  # Start/Stop automation
│       └── LogViewer.tsx        # Real-time log display
├── public/
├── index.html
├── package.json
├── vite.config.ts               # Proxy to Discovery (5001) & PM (5000)
├── tsconfig.json
└── tsconfig.app.json
```

### 5.2 Tech Stack (Same as preset-manager)
- React 19 + Vite 7
- TypeScript 5.9
- Tailwind CSS v4 (with @theme, no config file)
- SSE for real-time SUT updates

### 5.3 vite.config.ts

```typescript
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3001,  // Different from PM's 3000
    proxy: {
      '/api/discovery': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/discovery/, '/api')
      },
      '/api/presets': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/presets/, '/api')
      }
    }
  }
})
```

### 5.4 Launch via pyproject.toml

Create `Gemma/pyproject.toml`:

```toml
[project]
name = "gemma"
version = "1.0.0"

[project.scripts]
gemma = "gemma:main"
```

Create `Gemma/__init__.py` with `--host` flag to launch frontend.

---

## Implementation Order

| Order | Phase | Description | Effort |
|-------|-------|-------------|--------|
| 1 | Phase 1 | SUT Discovery Service with full proxy | ~12 files |
| 2 | Phase 2 | SUT client `/installed_games` | ~40 lines |
| 3 | Phase 3 | Remove PM internal discovery, add client | ~2 files |
| 4 | Phase 4 | Gemma Python clients | 2 new files |
| 5 | Phase 5 | Gemma React frontend | ~15 files |
| 6 | Phase 6 | Configuration | 1 file |

---

## Port Summary

| Service | Port | Purpose |
|---------|------|---------|
| **SUT Discovery Service** | 5001 | Gateway for ALL SUT communication |
| **Preset-Manager** | 5000 | Preset storage & management |
| **SUT Client** | 8080 | Runs on gaming machines |
| **UDP Broadcast** | 9999 | Fast discovery announcements |

---

## Data Flow

```
STARTUP:
1. SUT Discovery Service starts on port 5001
2. SUT Clients register via WebSocket to Discovery Service
3. Preset-Manager starts on port 5000 (no internal discovery)
4. Gemma GUI starts, connects to Discovery Service

AUTOMATION:
1. Gemma GUI → Discovery Service: GET /api/suts
2. User selects SUTs, games, preset (1080p high)
3. User clicks "Start"
4. Gemma → Preset-Manager: POST /api/sync/gemma-presets
5. Preset-Manager → Discovery Service: GET /api/suts/{id}/games
6. Preset-Manager → Discovery Service: POST /api/suts/{id}/apply-preset
7. Discovery Service → SUT Client: POST /apply-preset
8. Results flow back: SUT → Discovery → PM → Gemma
9. Gemma → Discovery Service: POST /api/suts/{id}/launch
10. Gemma → Discovery Service: POST /api/suts/{id}/action (automation)
11. Gemma → Discovery Service: GET /api/suts/{id}/screenshot
```

---

## Testing Checklist

- [ ] SUT Discovery Service starts on port 5001
- [ ] SUTs register via WebSocket
- [ ] Discovery Service proxies `/installed_games` correctly
- [ ] Discovery Service proxies `/apply-preset` correctly
- [ ] Discovery Service proxies `/action`, `/screenshot`, `/launch` correctly
- [ ] Preset-Manager starts without internal discovery
- [ ] Preset-Manager uses Discovery Client for all SUT access
- [ ] Gemma GUI shows SUTs from Discovery Service
- [ ] Gemma GUI has no mysuts.json dependency
- [ ] Preset application works end-to-end
- [ ] Automation runs using only Discovery Service for SUT communication
