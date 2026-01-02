# Gemma Backend

Central game automation orchestration platform.

## Architecture

- **Entry Point**: `Gemma/backend/__init__.py` → `main.py`
- **Port**: 5000
- **Framework**: Flask 3.0+ with Flask-SocketIO
- **CLI Command**: `gemma`

## Key Files

| File | Purpose |
|------|---------|
| `backend/api/routes.py` | All REST API endpoints |
| `backend/core/controller.py` | Main automation controller |
| `backend/core/automation_orchestrator.py` | Game automation logic |
| `backend/core/game_manager.py` | Game config management |
| `backend/core/run_manager.py` | Run lifecycle management |
| `backend/core/run_storage.py` | Run data persistence |
| `backend/core/timeline_manager.py` | Timeline event tracking |
| `backend/core/campaign_manager.py` | Campaign/batch run management |
| `backend/communication/sut_client.py` | SUT communication |
| `backend/communication/websocket_handler.py` | Real-time WebSocket updates |

## Modules Directory (`Gemma/modules/`)

| Module | Purpose |
|--------|---------|
| `simple_automation.py` | Core automation logic (66KB - largest file) |
| `omniparser_client.py` | OmniParser integration |
| `queue_service_client.py` | Queue Service client |
| `network.py` | Network utilities, HTTP requests |
| `game_launcher.py` | Game launch handling |

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/games` | List all games |
| GET | `/api/games/<name>` | Get game details |
| POST | `/api/games/reload` | Reload game configs |
| GET | `/api/runs` | List all runs |
| POST | `/api/runs` | Start new run |
| GET | `/api/runs/<id>` | Get run status |
| DELETE | `/api/runs/<id>` | Stop/cancel run |
| GET | `/api/runs/<id>/timeline` | Get run timeline |

## Features

### Automation Orchestration
- **Location**: `backend/core/automation_orchestrator.py`
- Game launch via SUT Client
- Screenshot capture and parsing
- UI element detection and interaction
- Step-by-step automation execution

### Timeline Events
- **Location**: `backend/core/timeline_manager.py`
- Real-time event tracking
- Event types: `game_launching`, `steam_dialog_checking`, `game_process_waiting`, etc.
- Countdown metadata for timed operations
- Event replacement with `replaces_event_id`

### Steam Dialog Detection
- **Location**: `modules/simple_automation.py:_check_steam_dialogs()`
- Focus Steam window before screenshot
- Parse via OmniParser for update/sync dialogs
- Auto-dismiss detected dialogs

### Process Detection
- **Location**: `modules/simple_automation.py:_wait_for_game_process()`
- Wait for game process with timeout (default 60s)
- Focus window by process name
- Countdown events for UI feedback

## Dependencies

- **Depends on**: Queue Service, SUT Discovery, SUT Client, OmniParser
- **Depended by**: Gemma Frontend

## Common Modifications

### Add new API endpoint
1. Edit `backend/api/routes.py`
2. Add route with Flask decorator
3. Call appropriate manager/controller method

### Add new timeline event type
1. Add to `backend/core/events.py` (EventType enum)
2. Emit event in automation code
3. Update frontend to handle new type

### Add new game config
1. Create YAML file in `Gemma/config/games/`
2. Reload configs via API or restart

## Config Directory

`Gemma/config/games/` - YAML files per game:
- `far-cry-6.yaml`
- `hitman-3.yaml`
- `ac-mirage.yaml`
- etc.

## Recent Changes

| Date | Change |
|------|--------|
| 2024-12-31 | Added Steam dialog detection via OmniParser |
| 2024-12-31 | Added GAME_PROCESS_WAITING/DETECTED events |
| 2024-12-31 | Added countdown metadata to timeline events |
