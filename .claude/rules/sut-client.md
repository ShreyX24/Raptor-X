# SUT Client

System Under Test agent - runs on gaming machines to receive and execute commands.

## Architecture

- **Entry Point**: `sut_client/src/sut_client/service.py`
- **Port**: 8080 (configurable)
- **Framework**: Flask 2.3+ with Waitress WSGI (8 threads)
- **CLI Commands**: `sut-client` or `pml-sut`
- **Package**: `pml-sut-client` v0.3.0 (KATANA Edition)

## Key Files

| File | Purpose |
|------|---------|
| `src/sut_client/service.py` | Flask app, API endpoints |
| `src/sut_client/applier.py` | Apply preset configurations |
| `src/sut_client/launcher.py` | Game launching logic |
| `src/sut_client/input_controller.py` | Keyboard/mouse automation |
| `src/sut_client/window.py` | Window detection (pywinauto) |
| `src/sut_client/hardware.py` | Hardware detection, DPI |
| `src/sut_client/steam.py` | Steam game detection |
| `src/sut_client/display.py` | Display/monitor detection |
| `src/sut_client/discovery.py` | UDP discovery listener |
| `src/sut_client/ws_client.py` | WebSocket to Discovery Service |
| `src/sut_client/backup.py` | Config backup/restore |

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Health check with system info |
| POST | `/screenshot` | Capture screenshot |
| POST | `/launch` | Launch game |
| POST | `/kill` | Kill process |
| POST | `/focus` | Focus window (optional process_name) |
| POST | `/click` | Click at coordinates |
| POST | `/key` | Send keypress |
| POST | `/apply-preset` | Apply game preset |
| GET | `/installed-games` | List installed Steam games |
| GET | `/processes` | List running processes |

## Features

### Game Launching
- **Location**: `launcher.py`
- Steam game launch via app ID
- Process detection after launch
- Window focus for reliable input

### Input Automation
- **Location**: `input_controller.py`
- Keyboard input (keys, text, hotkeys)
- Mouse clicks at coordinates
- DPI-aware coordinate handling

### Window Management
- **Location**: `window.py`
- Find windows by title/process
- Focus and bring to foreground
- Uses pywinauto (KATANA v0.2)

### Hardware Detection
- **Location**: `hardware.py`
- CPU, GPU, RAM detection
- Screen resolution
- DPI awareness for accurate coordinates

### Steam Integration
- **Location**: `steam.py`
- Detect installed Steam games
- Parse Steam VDF configs
- Launch via Steam protocol

## Special Features

### Windows Admin Elevation
- Auto-requests UAC elevation on startup
- Required for some game interactions

### DPI Awareness
- Handles high-DPI displays correctly
- Coordinate translation for accurate clicks

### Master Server Override
- `--master IP:PORT` for cross-subnet discovery
- Useful when SUT is on different network

## Command Line Options

```bash
sut-client --port 8080 --debug --master 192.168.0.100:5001
```

| Option | Purpose |
|--------|---------|
| `--port` | Service port (default 8080) |
| `--debug` | Enable debug logging |
| `--master` | Master server override for discovery |

## Dependencies

- **Depends on**: SUT Discovery Service (for registration)
- **Depended by**: Gemma Backend, Preset Manager

## Key Libraries

- `pywin32` - Windows API access
- `pyautogui` - Input automation
- `pywinauto` - Window detection
- `wmi`, `psutil` - System info
- `vdf` - Steam config parsing
- `waitress` - Production WSGI server

## Deployment Location

On SUT machines (e.g., ZEL-X7):
- Path: `D:\Code\Gemma\sut_client`
- Start: `sut-client` or batch file

## Common Modifications

### Add new endpoint
1. Add route in `service.py`
2. Implement handler function
3. Update health response if needed

### Add new input action
1. Add method in `input_controller.py`
2. Expose via API endpoint

### Modify game detection
1. Edit `steam.py` for Steam games
2. Add custom detection for non-Steam

## Recent Changes

| Date | Change |
|------|--------|
| 2024-12-31 | Added Waitress WSGI (8 threads) |
| 2024-12-31 | Added focus by process_name |
| 2024-12-31 | Added auto firewall rule on startup |
