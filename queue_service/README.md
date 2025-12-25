# Queue Service

OmniParser request queue middleware with terminal dashboard.

## Installation

```bash
pip install -e .
```

## Usage

```bash
queue-service --host 0.0.0.0 --port 9000 --omniparser-url http://localhost:8000
```

### Dashboard

```bash
queue-dashboard
```

## CLI Options

- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to run on (default: 9000)
- `--omniparser-url`: OmniParser server URL (default: http://localhost:8000)
- `--timeout`: Request timeout in seconds (default: 120)
- `--log-level`: Logging level (default: INFO)
