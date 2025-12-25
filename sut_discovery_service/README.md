# SUT Discovery Service

Central gateway for all SUT (System Under Test) communication.

## Installation

```bash
pip install -e .
```

## Usage

```bash
sut-discovery --host 0.0.0.0 --port 5001
```

## CLI Options

- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to run on (default: 5001)
- `--udp-port`: UDP broadcast port (default: 9999)
- `--log-level`: Logging level (default: INFO)

## Features

- UDP broadcast for SUT discovery
- WebSocket connections from SUT clients
- Device registry with pairing
- Proxy for all SUT API calls
