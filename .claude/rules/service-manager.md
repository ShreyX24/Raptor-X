# Service Manager

Desktop GUI application for managing and monitoring all Gemma services.

## Architecture

- **Entry Point**: `service_manager/src/service_manager/main.py`
- **Framework**: PySide6 6.6+ (Qt 6)
- **CLI Commands**: `gemma-manager` or `gemma-manager-gui`
- **Package**: `gemma-service-manager` v1.0.0

## Key Files

| File | Purpose |
|------|---------|
| `src/service_manager/main.py` | Application entry point |
| `src/service_manager/config.py` | Service configurations with health paths |
| `src/service_manager/settings.py` | User settings persistence |

## UI Components (`src/service_manager/ui/`)

| File | Purpose |
|------|---------|
| `main_window.py` | Main application window |
| `sidebar.py` | Service selection sidebar |
| `log_panel.py` | Log viewer and display |
| `settings_dialog.py` | Configuration dialog |
| `setup_wizard.py` | Initial setup wizard |
| `dashboard_panel.py` | Service dashboard view |
| `flow_diagram.py` | Service architecture diagram |

## Services (`src/service_manager/services/`)

| File | Purpose |
|------|---------|
| `process_manager.py` | Optimized process lifecycle management (1050+ lines) |

## Process Manager Architecture

The `process_manager.py` is the core of Service Manager with these key classes:

### ProcessState (Enum)
Formal state machine for process lifecycle:
```
STOPPED → STARTING → HEALTH_CHECK → RUNNING → STOPPING → STOPPED
                                  ↘ FAILED
```

### ProcessWrapper (QObject)
Manages a single service process:
- State machine with proper transitions
- QTcpSocket-based async health checks (non-blocking)
- Signal lifecycle management (connect on start, disconnect on stop)
- Process tree termination with `taskkill /F /T /PID`

### ProcessManager (QObject)
Orchestrates all services:
- Timer consolidation (single 50ms timer for all callbacks)
- Log batching (buffers output, flushes every 50ms)
- Dependency-aware startup (waits for health checks)
- Auto-restart watchdog with exponential backoff
- Background file I/O for restart requests

## Key Features

### Process Tree Termination (Windows)
**Critical for npm/vite**: When stopping services, uses `taskkill /F /T /PID` to kill entire process tree, preventing "port busy" issues on restart.

```python
subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], ...)
```

### Async Health Checks
Uses QTcpSocket for non-blocking port connectivity checks:
- Doesn't block Qt event loop
- 500ms retry interval
- 60 attempts max (30 seconds)
- Triggers dependent service startup on success

### Dependency-Aware Startup
Services with `depends_on` wait for dependency health checks to pass:
```
gemma-frontend waits for gemma-backend
pm-frontend waits for preset-manager
```
Shows "Waiting for dependencies: X" in log panel.

### Service Health Paths
Each service has a `health_path` in config for proper health endpoint:

| Service | Health Path |
|---------|-------------|
| sut-discovery | `/health` |
| queue-service | `/health` |
| gemma-backend | `/api/status` |
| gemma-frontend | `/` |
| preset-manager | `/health` |
| pm-frontend | `/` |
| omniparser-* | `/probe/` |

### Log Batching
`LogBuffer` class batches stdout/stderr, flushes every 50ms for smooth UI updates.

### Timer Consolidation
Single main timer (50ms) manages all scheduled callbacks via `ScheduledCallback` dataclass. Avoids timer proliferation.

### Background File Worker
`BackgroundFileWorker` (QThread) monitors restart request file for Admin Panel integration.

## Managed Services

| Service | Default Port | Health Path | Start Command |
|---------|--------------|-------------|---------------|
| SUT Discovery | 5001 | `/health` | `sut-discovery` |
| Queue Service | 9000 | `/health` | `queue-service` |
| Gemma Backend | 5000 | `/api/status` | `gemma` |
| Gemma Frontend | 3000 | `/` | `npm run dev` |
| Preset Manager | 5002 | `/health` | `preset-manager` |
| PM Frontend | 3001 | `/` | `npm run dev` |
| OmniParser | 8000-8004 | `/probe/` | `python -m omniparserserver --no-reload` |

## OmniParser Configuration

- `--no-reload` flag disables uvicorn's reloader (logs visible in Service Manager)
- Without `--no-reload`, requests are handled by child process (logs not captured)

## Configuration Storage

Settings stored in:
- Windows: `%APPDATA%/GemmaServiceManager/settings.json`
- Contains: window position, service paths, OmniParser URLs, Steam accounts

## Styling

- Dark theme (VS Code colors)
- Monospace font for logs (Consolas)
- High DPI scaling support
- Stop button enabled during "starting" state (allows abort)

## Dependencies

- **Depends on**: None (manages other services)
- **Depended by**: None (user-facing tool)

## Common Modifications

### Add new service
1. Add `ServiceConfig` in `config.py` with `health_path`
2. Service auto-appears in sidebar and log panels
3. ProcessManager handles it automatically

### Change health endpoint
1. Update `health_path` in `config.py` for the service
2. Ensure endpoint returns 2xx status

### Modify startup dependencies
1. Add service names to `depends_on` list in `config.py`
2. Service will wait for dependencies' health checks

### Add new settings
1. Add to `settings_dialog.py`
2. Persist in `settings.py`
3. Apply on startup

## Gotchas

1. **Port busy on restart**: Fixed with `taskkill /F /T` - kills process tree
2. **Health check blocking**: Use QTcpSocket (async), not socket.connect (blocking)
3. **OmniParser logs missing**: Use `--no-reload` flag
4. **Service stuck on "Starting"**: Check health_path matches actual endpoint

## Recent Changes

| Date | Change |
|------|--------|
| 2026-01-05 | Complete process_manager.py rewrite with optimizations |
| 2026-01-05 | Added ProcessState enum (formal state machine) |
| 2026-01-05 | Added ProcessWrapper class with signal lifecycle |
| 2026-01-05 | Added QTcpSocket async health checks |
| 2026-01-05 | Added taskkill /F /T for process tree termination |
| 2026-01-05 | Added dependency-aware startup (waits for health checks) |
| 2026-01-05 | Added timer consolidation (single 50ms timer) |
| 2026-01-05 | Added log batching for smooth UI |
| 2026-01-05 | Added health_path to ServiceConfig |
| 2026-01-05 | Added --no-reload to OmniParser command |
| 2026-01-05 | Stop button now enabled during "starting" state |
| 2024-12-31 | Added dashboard with flow diagram |
| 2024-12-31 | Added OmniParser instance management |
