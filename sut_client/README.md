# PML SUT Client

System Under Test (SUT) client for receiving and applying game configuration presets from the PML Preset Manager.

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# Run the SUT client
sut-client

# Or using Python module
python -m sut_client
```

The client will start on port 8080 by default.

## Configuration

Set environment variables or create a `.env` file:

```env
SUT_CLIENT_HOST=0.0.0.0
SUT_CLIENT_PORT=8080
SUT_CLIENT_LOG_LEVEL=INFO
SUT_CLIENT_BACKUP_DIR=data/backups
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Device status for discovery |
| `/health` | GET | Health check |
| `/apply-preset` | POST | Apply a preset |
| `/restore-config` | POST | Restore from backup |
| `/backups` | GET | List backups |
| `/info` | GET | Device information |

## Firewall

Ensure port 8080 is open for the Master Server to communicate:

```powershell
# Run as Administrator
New-NetFirewallRule -DisplayName "PML SUT Client" -LocalPort 8080 -Protocol TCP -Direction Inbound -Action Allow
```

## How It Works

1. The SUT Client advertises itself on the network
2. The Master Server discovers SUTs via network scanning
3. When a preset sync is triggered, Master sends preset files to the SUT
4. SUT creates a backup of existing config and applies the new preset
