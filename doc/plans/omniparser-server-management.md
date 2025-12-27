# Plan: Add OmniParser Server Management to Service Manager

## Overview
Add the ability to start/stop OmniParser server instances directly from the service manager, similar to how the batch file `start_omni_server.bat` works, but integrated into the UI.

## Current State
- OmniParser servers are tracked as URLs in settings (for passing to queue-service via `OMNIPARSER_URLS` env var)
- Flow diagram and dashboard display OmniParser status
- **OmniParser is NOT actually started/stopped by service manager** - user runs batch file separately

## Goal
- Dynamically manage 1-5 OmniParser instances on ports 8000, 8001, 8002, etc.
- Start/stop from service manager UI
- Show logs in log panel like other services

## OmniParser Command Details
From `start_omni_server.bat`:
```
Working dir: D:\Code\Gemma\Omniparser server\omnitool\omniparserserver
Command: python -m omniparserserver --use_paddleocr --port <PORT>
Ports: 8000, 8001, 8002, ... (base + instance index)
```

---

## Implementation Steps

### 1. Update `config.py` - Add OmniParser Constants
**File:** `service_manager/src/service_manager/config.py`

Add:
```python
OMNIPARSER_DIR = Path("D:/Code/Gemma/Omniparser server/omnitool/omniparserserver")
OMNIPARSER_BASE_PORT = 8000
OMNIPARSER_MAX_INSTANCES = 5
```

Add function to generate OmniParser service configs:
```python
def create_omniparser_config(instance: int) -> ServiceConfig:
    """Create config for an OmniParser instance (0-indexed)"""
    port = OMNIPARSER_BASE_PORT + instance
    return ServiceConfig(
        name=f"omniparser-{port}",
        display_name=f"OmniParser {port}",
        command=["python", "-m", "omniparserserver", "--use_paddleocr", "--port", str(port)],
        working_dir=OMNIPARSER_DIR,
        port=port,
        group="OmniParser",
        enabled=True,
    )
```

### 2. Update `settings.py` - Add Instance Count Setting
**File:** `service_manager/src/service_manager/settings.py`

Add to `SettingsManager`:
- `_omniparser_instance_count: int = 0` (0 = disabled)
- `get_omniparser_instance_count()` / `set_omniparser_instance_count()`
- Save/load in JSON config

Update `get_omniparser_urls_env()` to auto-generate URLs from instance count if no manual servers configured.

### 3. Update `process_manager.py` - Dynamic OmniParser Registration
**File:** `service_manager/src/service_manager/services/process_manager.py`

Add method:
```python
def register_omniparser_instances(self, count: int):
    """Register OmniParser instances based on settings"""
    # Remove old omniparser-* services
    # Create and register new configs based on count
```

Call this during initialization and when settings change.

### 4. Update `settings_dialog.py` - Add Instance Count Control
**File:** `service_manager/src/service_manager/ui/settings_dialog.py`

In `OmniParserServersTab`:
- Add spinbox for "Local Instances (0-5)"
- 0 = don't manage locally, use manual server URLs
- 1-5 = auto-create instances on ports 8000+
- When > 0, auto-populate the server list with localhost URLs

### 5. Update `main_window.py` - Refresh OmniParser on Settings Change
**File:** `service_manager/src/service_manager/ui/main_window.py`

When settings change:
- Call `process_manager.register_omniparser_instances()`
- Refresh sidebar to show new OmniParser services
- Update flow diagram with new instances

### 6. Update Sidebar - Show OmniParser Group
**File:** `service_manager/src/service_manager/ui/sidebar.py` (if exists) or `main_window.py`

Ensure OmniParser services appear in sidebar under "OmniParser" group with start/stop controls.

---

## Files to Modify
1. `service_manager/src/service_manager/config.py` - Add constants and config generator
2. `service_manager/src/service_manager/settings.py` - Add instance count setting
3. `service_manager/src/service_manager/services/process_manager.py` - Dynamic registration
4. `service_manager/src/service_manager/ui/settings_dialog.py` - Instance count UI
5. `service_manager/src/service_manager/ui/main_window.py` - Refresh on settings change

---

## Testing
1. Set instance count to 2 in settings
2. Verify OmniParser 8000 and 8001 appear in sidebar
3. Click "Start All" - verify both start
4. Check logs show OmniParser output
5. Verify queue-service receives correct OMNIPARSER_URLS
6. Stop individual instances
7. Change instance count and verify UI updates
