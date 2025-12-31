# Gemma Architecture Learnings

> **Last Updated**: 2025-12-28
> **Purpose**: Document architectural decisions and learnings from development

---

## Frontend Communication Rules

### Rule: Frontend NEVER talks directly to SUTs

**Date Learned**: 2025-12-28

**Context**: When implementing expandable run details with SUT hardware info, the initial approach was to have the frontend fetch `/system_info` directly from the SUT IP.

**Problem**:
- CORS blocks browser requests to different origins (SUT on different IP/port)
- Security risk exposing SUT IPs/ports directly to browser
- Breaks single-source-of-truth principle

**Solution**: All SUT communication must be proxied through Gemma Backend.

```
WRONG:
┌─────────────┐                    ┌─────────────┐
│   Frontend  │ ───── BLOCKED ────→│     SUT     │
│ (Browser)   │        CORS        │ (port 8080) │
└─────────────┘                    └─────────────┘

CORRECT:
┌─────────────┐      ┌─────────────────┐      ┌─────────────┐
│   Frontend  │ ──── │  Gemma Backend  │ ──── │     SUT     │
│ (Browser)   │      │   (port 5000)   │      │ (port 8080) │
└─────────────┘      └─────────────────┘      └─────────────┘
```

**Implementation**:
```typescript
// WRONG - Direct SUT call (CORS blocked)
fetch(`http://${sutIp}:8080/system_info`)

// CORRECT - Through Gemma backend
fetch(`/api/sut/by-ip/${sutIp}/system_info`)
```

**Backend endpoints added**:
- `GET /api/sut/<device_id>/system_info` - By device ID
- `GET /api/sut/by-ip/<ip>/system_info` - By IP (for run history)

---

## Architecture Pattern: Single Backend Gateway

**Rule**: Frontend only knows ONE backend - Gemma Backend

All service communication flows through Gemma:
```
Frontend → Gemma Backend → SUT Client
Frontend → Gemma Backend → Discovery Service
Frontend → Gemma Backend → Queue Service
Frontend → Gemma Backend → Preset Manager
```

**Benefits**:
1. Single CORS configuration (Gemma Backend only)
2. Centralized auth/security
3. Single API versioning
4. Backend can aggregate/transform data
5. Frontend doesn't need service discovery

---

## SUT Access & Deployment

**Date**: 2025-12-28

### SUT Client Source of Truth

**Source of Truth**: `ZEL-X7 (192.168.0.106)` at `D:\Code\Gemma\sut_client\`

**Rule**: The SUT version IS the source of truth. Edit directly on SUT via SSH.
- NO local copy in Gemma-e2e repo
- sut_client only runs on SUTs, not development machine

### SSH Access to SUT

```bash
# SSH to SUT (ZEL-X7)
ssh shrey@192.168.0.106

# Edit files directly on SUT
ssh shrey@192.168.0.106 "notepad D:\\Code\\Gemma\\sut_client\\src\\sut_client\\service.py"

# Or use VS Code Remote SSH extension

# Copy file FROM SUT to local (for reference)
scp shrey@192.168.0.106:"D:/Code/Gemma/sut_client/src/sut_client/service.py" ./

# Copy file TO SUT
scp local_file.py shrey@192.168.0.106:"D:/Code/Gemma/sut_client/src/sut_client/"
```

### SUT Locations

| SUT | IP | Path | Hostname | Role |
|-----|-----|------|----------|------|
| ZEL-X7 | 192.168.0.106 | `D:\Code\Gemma\sut_client` | ZEL-X7 | **Source of Truth** |
| ZEL-X2 | 192.168.0.103 | TBD | ZEL-X2 | Secondary |

### Development Workflow

1. SSH into ZEL-X7: `ssh shrey@192.168.0.106`
2. Edit sut_client code directly on SUT
3. Restart sut_client service to test
4. Copy to other SUTs when ready

### Important: No CORS on SUT Client

The SUT client should NOT have CORS enabled because:
- Frontend NEVER talks directly to SUT
- All communication goes through Gemma Backend
- CORS on SUT would wrongly suggest direct browser access is allowed

---

## SSH Key-Based Authentication for SUTs

**Date**: 2025-12-31

**Problem**: SSH to SUTs requires password every time, blocking automation.

**Solution**: Generate SSH key pair and add public key to SUT's authorized_keys.

### Step 1: Generate SSH Key (On Orchestrator - Dev Machine)

```bash
# Generate a 4096-bit RSA key
ssh-keygen -t rsa -b 4096 -f "$HOME/.ssh/id_rsa_sut" -N "" -C "gemma-orchestrator"

# View the public key
cat "$HOME/.ssh/id_rsa_sut.pub"
```

### Step 2: Add Public Key to SUT (Run on Each SUT)

**PowerShell on SUT:**
```powershell
# Create .ssh directory if it doesn't exist
if (!(Test-Path "$env:USERPROFILE\.ssh")) { mkdir "$env:USERPROFILE\.ssh" }

# Add the public key (replace with your actual public key)
Add-Content -Path "$env:USERPROFILE\.ssh\authorized_keys" -Value 'ssh-rsa AAAA...your-key-here... gemma-orchestrator'

# Ensure correct permissions (Windows OpenSSH requires this)
icacls "$env:USERPROFILE\.ssh\authorized_keys" /inheritance:r /grant "$env:USERNAME`:R"
```

### Step 3: Test Connection

```bash
# From orchestrator, test passwordless SSH
ssh -i ~/.ssh/id_rsa_sut zelos@192.168.0.106 "echo connected"

# Configure SSH to use this key by default for SUTs
# Add to ~/.ssh/config:
# Host 192.168.0.*
#     User zelos
#     IdentityFile ~/.ssh/id_rsa_sut
```

### SUT SSH Configuration

| SUT | IP | Username | Status |
|-----|-----|----------|--------|
| ZEL-X7 | 192.168.0.106 | zelos | Primary test SUT |
| ZEL-X2 | 192.168.0.103 | TBD | Secondary |

---

## SUT Client Deployment

**Date**: 2025-12-31

### Building SUT Client

```bash
# Navigate to sut_client directory
cd sut_client

# Build the wheel package
python -m build

# Output: dist/pml_sut_client-X.X.X-py3-none-any.whl
```

### Deploying to SUT

**Method 1: SCP + SSH (Automated)**
```bash
# Copy wheel to SUT
scp -i ~/.ssh/id_rsa_sut dist/pml_sut_client-*.whl zelos@192.168.0.106:~/

# Install on SUT
ssh -i ~/.ssh/id_rsa_sut zelos@192.168.0.106 "pip install ~/pml_sut_client-*.whl --force-reinstall"
```

**Method 2: Manual (When SSH Issues)**
1. Copy wheel file to SUT via network share or USB
2. On SUT PowerShell:
   ```powershell
   pip install pml_sut_client-0.3.0-py3-none-any.whl --force-reinstall
   ```

### Running SUT Client

```bash
# Start SUT client (runs on port 8080 by default)
sut-client

# Or with custom port
SUT_CLIENT_PORT=5555 sut-client
```

---

## Steam Dialog Detection Architecture

**Date**: 2025-12-31

**Problem**: Steam shows various popup dialogs during game launch:
- "Account in use on another computer" (conflict)
- "Which graphics API?" (DX11/DX12/Vulkan)
- EULA agreements
- Cloud sync conflicts

**Why SUT Client Can't Detect**: Steam uses SDL rendering. Dialogs are rendered inside the main SDL window, not as separate Win32 windows. Win32 EnumWindows/EnumChildWindows cannot see them.

**Solution**: Use OmniParser (screenshot + OCR) from the Gemma backend.

### Architecture

```
┌────────────────┐                    ┌─────────────────┐
│  Gemma Backend │                    │   SUT Client    │
│                │                    │                 │
│  1. Launch game ─────────────────────→ Launch via Steam
│                │                    │                 │
│  2. Wait 3-5s  │                    │                 │
│                │                    │                 │
│  3. Get screenshot ──────────────────→ /screenshot    │
│       (base64) ←────────────────────── Returns PNG    │
│                │                    │                 │
│  4. Send to OmniParser              │                 │
│     ↓                               │                 │
│  ┌─────────────────┐                │                 │
│  │  Queue Service  │                │                 │
│  │  → OmniParser   │                │                 │
│  │  → Parsed text  │                │                 │
│  └─────────────────┘                │                 │
│                │                    │                 │
│  5. Check against steam_dialogs.yaml│                 │
│     If match: get button coords     │                 │
│                │                    │                 │
│  6. Click button ────────────────────→ /action        │
│     {"type":"click","x":X,"y":Y}    │  Click coords   │
│                │                    │                 │
│  7. Handle result                   │                 │
│     - conflict: try alt account     │                 │
│     - api_select: continue          │                 │
└────────────────┘                    └─────────────────┘
```

### Configuration: steam_dialogs.yaml

Located at: `Gemma/config/steam_dialogs.yaml`

```yaml
dialogs:
  - id: account_conflict
    keywords: ["logged in on another computer", "disconnect the other session"]
    action: click
    button: "Cancel"
    handler: try_alternative_account

  - id: graphics_api
    keywords: ["which api", "directx 12", "vulkan"]
    action: click
    button: "DirectX 12"
    handler: continue
```

### Integration Point

In `automation_orchestrator.py`, between game launch and process detection:

```python
# After launching game
await launch_game_on_sut(...)

# Check for Steam dialogs (NEW)
dialog_result = await check_steam_dialogs(sut_ip)
if dialog_result.type == "conflict":
    # Try alternative Steam account
    return await retry_with_alternative_account()

# Continue with process detection
await wait_for_game_process(...)
```

---

## CPU Codename Mapping

**Date**: 2025-12-28

**Learning**: Display user-friendly CPU names instead of raw brand strings.

**Example**:
- Raw: `Intel(R) Core(TM) i5-14600KF`
- Display: `Raptor Lake - i5-14600KF`

**Implementation**: `Gemma/admin/src/utils/cpuCodenames.ts`

**Intel Codename Patterns**:
| Pattern | Codename | Generation |
|---------|----------|------------|
| `i[3579]-15xxx` | Arrow Lake | 15th |
| `i[3579]-14xxx` | Raptor Lake | 14th |
| `i[3579]-13xxx` | Raptor Lake | 13th |
| `i[3579]-12xxx` | Alder Lake | 12th |
| `Core Ultra [579] 2xx` | Arrow Lake | - |
| `Core Ultra [579] 1xx` | Meteor Lake | - |

**AMD Codename Patterns**:
| Pattern | Codename |
|---------|----------|
| `Ryzen [3579] 9xxx` | Granite Ridge |
| `Ryzen [3579] 7xxx` | Raphael |
| `Ryzen [3579] 5xxx` | Vermeer |
| `Ryzen [3579] 3xxx` | Matisse |

---

## Timestamp Field Naming

**Date**: 2025-12-28

**Learning**: Backend and frontend must agree on field names.

**Issue**: Backend used `start_time`/`end_time` but frontend expected `started_at`/`completed_at`.

**Fix**: Update `to_dict()` in `run_manager.py`:
```python
# Changed from:
'start_time': self.progress.start_time.isoformat() if ...
'end_time': self.progress.end_time.isoformat() if ...

# To:
'started_at': self.progress.start_time.isoformat() if ...
'completed_at': self.progress.end_time.isoformat() if ...
```

---

## WMI for Hardware Detection (Windows)

**Date**: 2025-12-28

**Learning**: Use WMI (Windows Management Instrumentation) for hardware info.

**SUT Client endpoint**: `GET /system_info`

**WMI queries used**:
```python
# BIOS info
wmi.WMI().Win32_BIOS()[0]

# OS info
platform.system(), platform.release(), platform.version()

# RAM
psutil.virtual_memory().total

# GPU/CPU from existing hardware.py functions
```

**Response format**:
```json
{
  "cpu": {"brand_string": "Intel Core i5-14600KF"},
  "gpu": {"name": "NVIDIA GeForce RTX 4070 SUPER"},
  "ram": {"total_gb": 32},
  "os": {"name": "Windows", "release": "11", "build": "10.0.26100"},
  "bios": {"name": "...", "version": "..."},
  "screen": {"width": 1920, "height": 1080},
  "hostname": "ZEL-X7",
  "device_id": "sut_ZEL-X7_..."
}
```
