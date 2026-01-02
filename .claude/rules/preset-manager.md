# Preset Manager

Filesystem-based game configuration preset management with network auto-discovery.

## Architecture

- **Entry Point**: `preset-manager/src/preset_manager/server.py`
- **Port**: 5002
- **Framework**: FastAPI 0.104+ with Uvicorn
- **CLI Command**: `preset-manager` or `pml-master`

## Key Files

| File | Purpose |
|------|---------|
| `src/preset_manager/server.py` | FastAPI app setup |
| `src/preset_manager/core/preset_manager.py` | Core preset logic |
| `src/preset_manager/core/sync_manager.py` | Preset synchronization |
| `src/preset_manager/core/backup_manager.py` | Backup/restore functionality |
| `src/preset_manager/core/config.py` | Configuration management |
| `src/preset_manager/core/schemas.py` | Pydantic models |

## API Routes (`src/preset_manager/api/`)

| File | Purpose |
|------|---------|
| `games.py` | Game management endpoints |
| `presets.py` | Preset CRUD operations |
| `suts.py` | SUT device endpoints |
| `sync.py` | Preset sync operations |
| `backups.py` | Backup management |

## Discovery (`src/preset_manager/discovery/`)

| File | Purpose |
|------|---------|
| `device_registry.py` | Device tracking |
| `scanner.py` | Network scanning |
| `websocket_manager.py` | WebSocket connections |
| `udp_announcer.py` | UDP broadcast handling |

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/games` | List all games |
| GET | `/api/presets` | List all presets |
| POST | `/api/presets` | Create preset |
| GET | `/api/suts` | List SUTs |
| POST | `/api/sync` | Sync presets to SUT |
| GET | `/api/backups` | List backups |

## Features

### Preset Management
- Filesystem-based storage (no external DB)
- Game-specific preset handlers
- Preset versioning

### Device Discovery
- Uses external SUT Discovery Service (via `USE_EXTERNAL_DISCOVERY` env var)
- Fallback to internal UDP discovery
- WebSocket for real-time device updates

### Sync Operations
- Push presets to SUTs
- Pull current settings from SUTs
- Backup before applying

## Frontend (`preset-manager/admin/`)

- React + Tailwind + Vite
- Port: 3001

Key components:
- `PresetManager.tsx` - Main UI
- `GamesTable.tsx` - Game list
- `SUTsTable.tsx` - Device management
- `SyncHistory.tsx` - Sync history

## Dependencies

- **Depends on**: SUT Discovery Service (optional)
- **Depended by**: Gemma Backend, SUT Client

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `USE_EXTERNAL_DISCOVERY` | Use external SUT Discovery Service |
| `DISCOVERY_SERVICE_URL` | SUT Discovery Service URL |

## Common Modifications

### Add new game support
1. Create handler in `src/preset_manager/handlers/`
2. Register in handler registry
3. Add game config

### Add new API endpoint
1. Create route in `src/preset_manager/api/`
2. Add business logic in `core/`
3. Register router in `server.py`

## Recent Changes

| Date | Change |
|------|--------|
| 2024-12-31 | Added external discovery service integration |
