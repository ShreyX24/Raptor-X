# Queue Service

Middleware for OmniParser request queuing and load balancing.

## Architecture

- **Entry Point**: `queue_service/src/queue_service/main.py`
- **Port**: 9000
- **Framework**: FastAPI 0.104+ with Uvicorn, Rich (terminal UI)
- **CLI Commands**: `queue-service` (server), `queue-dashboard` (terminal UI)

## Key Files

| File | Purpose |
|------|---------|
| `src/queue_service/main.py` | FastAPI app setup |
| `src/queue_service/queue_manager.py` | Queue and load balancing logic |
| `src/queue_service/config.py` | Configuration (server URLs, timeouts) |

## API Routes (`src/queue_service/api/`)

| File | Purpose |
|------|---------|
| `parse.py` | Parse request handling |
| `stats.py` | Queue statistics |
| `health.py` | Health checks |

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/parse` | Submit parse request to OmniParser |
| GET | `/health` | Service health status |
| GET | `/probe` | OmniParser servers health |
| GET | `/stats` | Queue statistics |

## Features

### Load Balancing
- **Location**: `queue_manager.py`
- Round-robin distribution across OmniParser servers
- Per-server health tracking
- Automatic failover on server failure

### Request Queuing
- Queue requests when all servers busy
- Configurable queue size
- Request timeout handling

### Multi-Server Support
- Configure via `OMNIPARSER_URLS` environment variable
- Comma-separated list of server URLs
- Dynamic server health monitoring

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OMNIPARSER_URLS` | `http://localhost:8000` | Comma-separated OmniParser URLs |
| `QUEUE_SERVICE_PORT` | `9000` | Service port |
| `REQUEST_TIMEOUT` | `120` | Request timeout in seconds |

### Example Startup

```bash
# Single OmniParser
OMNIPARSER_URLS=http://localhost:8100 python -m queue_service

# Multiple OmniParser servers
OMNIPARSER_URLS=http://192.168.0.103:8000,http://192.168.0.103:8001 python -m queue_service
```

## Dependencies

- **Depends on**: OmniParser Server(s)
- **Depended by**: Gemma Backend

## Health Response

```json
{
  "status": "healthy",
  "worker_running": true,
  "queue_size": 0,
  "uptime_seconds": 123.45
}
```

## Probe Response

```json
{
  "servers": [
    {"url": "http://localhost:8100", "status": "healthy", "latency_ms": 15}
  ],
  "healthy_count": 1,
  "total_count": 1
}
```

## Common Modifications

### Add new OmniParser server
1. Update `OMNIPARSER_URLS` environment variable
2. Restart Queue Service

### Modify load balancing
1. Edit `queue_manager.py`
2. Update server selection logic

### Add new endpoint
1. Create route in `api/`
2. Register in `main.py`

## Recent Changes

| Date | Change |
|------|--------|
| 2024-12-31 | Added multi-server support with round-robin |
| 2024-12-31 | Added per-server health tracking |
