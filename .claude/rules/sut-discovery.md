# SUT Discovery Service

Central gateway for all SUT (System Under Test) device communication and discovery.

## Architecture

- **Entry Point**: `sut_discovery_service/src/sut_discovery_service/main.py`
- **Port**: 5001 (HTTP/WebSocket), 9999 (UDP broadcast)
- **Framework**: FastAPI 0.104+ with Uvicorn, WebSockets
- **CLI Command**: `sut-discovery`

## Key Files

| File | Purpose |
|------|---------|
| `src/sut_discovery_service/main.py` | FastAPI app, startup events |
| `src/sut_discovery_service/config.py` | Configuration settings |

## API Routes (`src/sut_discovery_service/api/`)

| File | Purpose |
|------|---------|
| `suts.py` | SUT management endpoints |
| `proxy.py` | Request proxying to SUTs |
| `health.py` | Health check endpoints |

## Discovery (`src/sut_discovery_service/discovery/`)

| File | Purpose |
|------|---------|
| `device_registry.py` | Device tracking, persistence |
| `events.py` | Event system |
| `udp_announcer.py` | UDP broadcast handling |
| `websocket_manager.py` | WebSocket connection management |

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/suts` | List all discovered SUTs |
| GET | `/api/suts/<id>` | Get SUT details |
| POST | `/api/suts/<id>/pair` | Pair with SUT |
| DELETE | `/api/suts/<id>` | Remove SUT |
| POST | `/api/proxy/<sut_ip>/<path>` | Proxy request to SUT |
| GET | `/api/health` | Service health |
| WS | `/ws` | WebSocket for real-time updates |

## Features

### UDP Discovery
- **Location**: `discovery/udp_announcer.py`
- Listen on port 9999 for SUT announcements
- Broadcast discovery requests
- Auto-register discovered devices

### Device Registry
- **Location**: `discovery/device_registry.py`
- Track online/offline status
- Persist paired devices to `paired_devices.json`
- Device metadata (hostname, IP, hardware info)

### Request Proxying
- **Location**: `api/proxy.py`
- Route requests to SUTs through discovery service
- Handle connection failures gracefully
- Useful for cross-subnet communication

### WebSocket Updates
- **Location**: `discovery/websocket_manager.py`
- Real-time device status changes
- New device notifications
- Connection state tracking

## Dependencies

- **Depends on**: None (core service)
- **Depended by**: Gemma Backend, Preset Manager, SUT Client

## Data Files

| File | Purpose |
|------|---------|
| `paired_devices.json` | Persisted device registry |
| `sut_discovery.log` | Service logs |

## Common Modifications

### Add new device event
1. Add event type in `discovery/events.py`
2. Emit event in `device_registry.py`
3. Handle in WebSocket manager

### Add new API endpoint
1. Create route in `api/`
2. Register router in `main.py`

### Modify discovery behavior
1. Edit `discovery/udp_announcer.py`
2. Update device registration logic

## Recent Changes

| Date | Change |
|------|--------|
| 2024-12-31 | Added cross-subnet support via master override |
