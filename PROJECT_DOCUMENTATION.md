# Gemma & Preset-Manager Project Documentation

## Overview

This repository contains two interrelated projects designed for game automation and benchmarking:

1. **Gemma** - A game automation/benchmarking framework with a GUI controller
2. **Preset-Manager** - A game graphics settings management system with SUT auto-discovery

Both systems use a distributed architecture where a Master/Controller orchestrates operations on remote SUTs (Systems Under Test - gaming machines).

---

## Project 1: Gemma

### Purpose
Gemma is a game automation framework designed for automated benchmarking and UI testing of games. It uses vision AI models to detect UI elements and make decisions on what actions to take.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONTROLLER (Host Machine)                    │
├─────────────────────────────────────────────────────────────────┤
│  gui_app_multi_sut.py    - Multi-SUT GUI Controller (tkinter)  │
│  main.py                 - Main orchestration script            │
│  workflow_builder.py     - Workflow configuration tool          │
│  omniparser_queue_service.py - Vision model queue service       │
├─────────────────────────────────────────────────────────────────┤
│                         MODULES                                  │
├─────────────────────────────────────────────────────────────────┤
│  network.py          - HTTP communication with SUTs             │
│  screenshot.py       - Screenshot capture and management        │
│  config_parser.py    - Game YAML configuration parser           │
│  decision_engine.py  - FSM-based state machine decision engine  │
│  game_launcher.py    - Game launching with Steam integration    │
│  annotator.py        - Screenshot annotation with bounding boxes│
│  gemma_client.py     - Gemma/LLaMA vision model client         │
│  qwen_client.py      - Qwen VL vision model client             │
│  omniparser_client.py- OmniParser vision model client          │
│  simple_automation.py- Simple automation executor               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SUT (Gaming Machine)                        │
├─────────────────────────────────────────────────────────────────┤
│  gemma_client_0.2.py - SUT Agent (Flask service)                │
│  - Receives action commands from Controller                     │
│  - Captures screenshots                                          │
│  - Simulates mouse/keyboard input                               │
│  - Launches games via Steam                                      │
│  - Reports system status                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. gui_app_multi_sut.py - Multi-SUT GUI Controller
- **Purpose**: Tkinter-based GUI for managing multiple SUTs simultaneously
- **Features**:
  - SUT discovery and connection management
  - Screenshot viewing with annotations
  - Manual/automatic action modes
  - Game selection and launching
  - Decision engine control
  - Campaign/workflow management

#### 2. main.py - Main Orchestration Script
- **Purpose**: Command-line orchestration for single-SUT operation
- **Features**:
  - Game-specific logging to separate directories
  - Configurable via YAML files
  - Multi-game support
  - State machine based automation

#### 3. decision_engine.py - FSM-Based Decision Engine
- **Purpose**: State machine that determines what action to take based on current screen state
- **Features**:
  - Flexible UI element matching (exact, contains, regex)
  - State transition management
  - Action sequencing (click, drag, type, hotkey)
  - Game state tracking (menu, loading, benchmark, etc.)
  - Configurable via YAML game configs

#### 4. network.py - Network Communication Manager
- **Purpose**: Handles all HTTP communication with SUT agents
- **Features**:
  - Screenshot retrieval (`/screenshot`)
  - Action execution (`/action`)
  - Game launching (`/launch`)
  - Process control (`/check_process`, `/kill_process`)
  - Steam login automation (`/login_steam`)

#### 5. Vision Model Clients
Three interchangeable vision model clients for UI element detection:
- **gemma_client.py**: Gemma/LLaMA models via Ollama
- **qwen_client.py**: Qwen VL models via Ollama
- **omniparser_client.py**: OmniParser local model service

#### 6. gemma_client_0.2.py - SUT Agent
- **Purpose**: Flask service running on gaming machines
- **Endpoints**:
  - `GET /status` - Health check and capabilities
  - `GET /screenshot` - Capture screen (PNG or base64)
  - `POST /action` - Execute input actions (click, type, hotkey, etc.)
  - `POST /launch` - Launch game via Steam
  - `POST /check_process` - Check if process is running
  - `POST /kill_process` - Terminate a process
  - `POST /login_steam` - Automate Steam login
- **Capabilities**: basic_clicks, advanced_clicks, drag_drop, scroll, hotkeys, text_input, sequences, performance_monitoring, gaming_optimizations

### Configuration System

Games are configured via YAML files in `config/games/`:

```yaml
game:
  name: "Counter-Strike 2"
  steam_app_id: "730"
  process_name: "cs2.exe"

states:
  - name: main_menu
    conditions:
      - element: "PLAY"
        match_type: contains
    actions:
      - type: click
        target: "Settings"

  - name: settings_menu
    conditions:
      - element: "Video Settings"
    actions:
      - type: click
        target: "Video Settings"
```

---

## Project 2: Preset-Manager

### Purpose
Preset-Manager handles game graphics settings (resolution, quality presets) and can push configuration changes to multiple SUTs. It integrates with Gemma for complete benchmark automation.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MASTER SERVER (FastAPI)                      │
├─────────────────────────────────────────────────────────────────┤
│  server.py           - FastAPI application entry point          │
│  ├── api/                                                        │
│  │   ├── games.py    - Games REST API                           │
│  │   ├── presets.py  - Presets REST API                         │
│  │   ├── suts.py     - SUTs management API + WebSocket          │
│  │   ├── sync.py     - Preset sync operations                   │
│  │   └── backups.py  - Backup management                        │
│  ├── core/                                                       │
│  │   ├── config.py   - Server configuration                     │
│  │   ├── preset_manager.py - Preset upload/validation           │
│  │   ├── backup_manager.py - Backup/restore logic               │
│  │   ├── sync_manager.py   - Sync orchestration                 │
│  │   └── schemas.py  - Pydantic data models                     │
│  ├── discovery/                                                  │
│  │   ├── device_registry.py - SUT device tracking               │
│  │   ├── scanner.py  - Network discovery scanner                │
│  │   ├── udp_announcer.py - UDP broadcast for discovery         │
│  │   └── websocket_manager.py - WebSocket connection manager    │
│  ├── handlers/                                                   │
│  │   ├── base.py     - Abstract config handler                  │
│  │   ├── ini.py      - INI file handler                         │
│  │   ├── json.py     - JSON file handler                        │
│  │   ├── xml.py      - XML file handler                         │
│  │   └── registry.py - Windows Registry handler                 │
│  └── utils/                                                      │
│      ├── network.py  - Network utilities                        │
│      ├── path.py     - Path resolution                          │
│      └── steam.py    - Steam utilities                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                    UDP Broadcast / WebSocket / HTTP
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SUT CLIENT (Flask)                          │
├─────────────────────────────────────────────────────────────────┤
│  service.py          - Flask HTTP service                        │
│  applier.py          - Preset application logic                  │
│  backup.py           - Local backup management                   │
│  discovery.py        - UDP discovery listener                    │
│  ws_client.py        - WebSocket client to Master               │
│  input_controller.py - Mouse/keyboard input (merged from Gemma) │
│  launcher.py         - Game launching                           │
│  steam.py            - Steam integration                         │
│  hardware.py         - DPI awareness, resolution                │
│  window.py           - Window management                         │
│  system.py           - Process control utilities                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

#### Master Server (preset_manager/src/preset_manager/)

##### server.py - FastAPI Application
- **Purpose**: Main FastAPI server with all routes
- **Features**:
  - CORS support for admin UI
  - Static file serving
  - Device registry initialization
  - Discovery service management
  - WebSocket endpoint for real-time SUT communication

##### api/suts.py - SUT Management API
- **Purpose**: Manage SUT devices via REST and WebSocket
- **Endpoints**:
  - `GET /suts` - List all discovered SUTs
  - `GET /suts/{unique_id}` - Get specific SUT details
  - `POST /suts/{unique_id}/pair` - Pair a SUT for priority scanning
  - `DELETE /suts/{unique_id}/pair` - Unpair a SUT
  - `POST /suts/{unique_id}/launch` - Launch game on SUT
  - `PUT /suts/{unique_id}/display-name` - Set SUT display name
  - `POST /suts/{unique_id}/rename-pc` - Rename Windows hostname
  - `WS /ws/sut/{sut_id}` - WebSocket endpoint for real-time communication
  - `GET /suts/events` - SSE endpoint for frontend updates

##### api/sync.py - Preset Sync API
- **Purpose**: Push presets to SUTs
- **Endpoints**:
  - `POST /sync/push` - Push preset to specific SUTs
  - `POST /sync/bulk` - Bulk sync operations
  - `GET /sync/games` - List available games
  - `GET /sync/presets/{game_slug}` - List presets for a game
  - `POST /sync/rollback/{sut_id}` - Rollback to backup

##### discovery/device_registry.py - Device Registry
- **Purpose**: Track all discovered SUT devices
- **Features**:
  - Device registration and status tracking
  - Pairing mode for priority scanning
  - Persistence of paired devices to JSON
  - CPU model tracking for display name suggestions
  - Device statistics

##### discovery/scanner.py - Network Discovery Service
- **Purpose**: Actively scan network for SUT devices
- **Features**:
  - Threaded background scanning
  - Priority scanning for paired devices (every 5 seconds)
  - General network discovery (every 60 seconds)
  - Auto-discovery of network ranges from local interfaces
  - ThreadPoolExecutor for concurrent scanning

##### handlers/ - Configuration Handlers
Support for multiple configuration formats:
- **INI Handler**: ConfigParser-based INI file reading/writing
- **JSON Handler**: JSON configuration files
- **XML Handler**: XML configuration files
- **Registry Handler**: Windows Registry operations via winreg

#### SUT Client (sut_client/src/sut_client/)

##### service.py - Flask HTTP Service
- **Purpose**: HTTP API for receiving commands from Master
- **Features**:
  - Merged with Gemma v0.2 capabilities
  - Preset application
  - Game launching
  - Input automation
  - Screenshot capture
  - Process control
- **Endpoints**:
  - `GET /status` - Device status with capabilities
  - `POST /apply-preset` - Apply preset from Master
  - `POST /restore-config` - Restore from backup
  - `GET /backups` - List backups
  - `POST /launch` - Launch game
  - `POST /action` - Input action (click, type, hotkey, etc.)
  - `GET /screenshot` - Capture screen
  - `POST /check_process` - Check if process running
  - `POST /kill_process` - Kill process
  - `POST /login_steam` - Steam login automation

##### applier.py - Preset Applier
- **Purpose**: Apply received presets to local system
- **Features**:
  - Environment variable expansion (%USERPROFILE%, %STEAM_INSTALL%, etc.)
  - Dynamic Steam game path resolution via %STEAM_GAME_<appid>%
  - Automatic backup before applying
  - Registry preset support (via reg import)
  - Hardware config preservation (CPU/GPU info in XML configs)
  - Wildcard path support for multi-profile games
  - Multi-drive search for standalone apps

##### discovery.py - UDP Discovery
- **Purpose**: Listen for Master server broadcasts
- **Features**:
  - UDP socket listening on port 9999
  - Async/await support
  - Thread wrapper for Flask integration

##### ws_client.py - WebSocket Client
- **Purpose**: Maintain WebSocket connection to Master
- **Features**:
  - Auto-reconnection
  - Heartbeat/ping-pong
  - Command reception and execution
  - Registration with Master on connect

### Legacy Modules (preset-manager/modules/)

The legacy modules provide standalone functionality:
- **config_replacer.py** - Replace game configs with presets
- **config_verifier.py** - Verify config file integrity
- **game_detector.py** - Detect installed games
- **path_resolver.py** - Resolve environment variable paths
- **ppg_preset_applier.py** - PPG preset application logic
- **registry_handler.py** - Windows Registry operations
- **steam_cli_handler.py** - Steam command-line operations
- **steam_verifier.py** - Verify Steam installation
- **system_verifier.py** - System requirements verification

---

## SUT Discovery Mechanisms

### Gemma Discovery
- HTTP-based polling via `network.py`
- Configurable SUT IP addresses in settings
- Status check via `/status` endpoint

### Preset-Manager Discovery
1. **UDP Broadcast**: Master broadcasts `MASTER_ANNOUNCE` messages
2. **WebSocket**: SUTs connect to Master via WebSocket for real-time communication
3. **HTTP Polling**: Master actively scans network for SUT `/status` endpoints
4. **Priority Scanning**: Paired devices are scanned more frequently (5s vs 60s)

---

## Integration Points

### How Gemma Calls Preset-Manager

The goal is for Gemma to call Preset-Manager to apply PPG presets before running benchmarks:

1. **Before Benchmark**:
   - Gemma Controller calls Preset-Manager Master API
   - `POST /sync/push` with game_short_name, preset_level, sut_unique_ids
   - Master pushes preset to SUT client
   - SUT client applies preset via `applier.py`

2. **Shared SUT Client**:
   - SUT Client in preset-manager is merged with Gemma v0.2 capabilities
   - Same service handles both preset application AND input automation
   - Port: 8080 (default)

3. **API Flow**:
```
Gemma Controller                    Preset-Manager Master               SUT Client
      │                                      │                              │
      │─── POST /sync/push ──────────────────►                              │
      │    {game: "cs2", preset: "high"}     │                              │
      │                                      │─── POST /apply-preset ──────►│
      │                                      │    {files, config_files}     │
      │                                      │                              │
      │                                      │◄── {success: true} ──────────│
      │◄── {status: success} ────────────────│                              │
      │                                      │                              │
      │─── POST /action (to SUT directly) ──────────────────────────────────►
      │    {action: "click", x: 100, y: 200} │                              │
```

---

## File Structure Summary

```
D:\Code\Gemma/
├── Gemma/                              # Core Gemma automation framework
│   ├── main.py                         # Main orchestration script
│   ├── gui_app_multi_sut.py            # Multi-SUT GUI controller
│   ├── workflow_builder.py             # Workflow configuration tool
│   ├── omniparser_queue_service.py     # OmniParser vision model service
│   ├── config/                         # Configuration files
│   │   ├── games/                      # Game YAML configs
│   │   └── campaigns/                  # Campaign definitions
│   ├── modules/                        # Core modules
│   │   ├── network.py                  # SUT communication
│   │   ├── screenshot.py               # Screenshot handling
│   │   ├── config_parser.py            # YAML parsing
│   │   ├── decision_engine.py          # FSM decision engine
│   │   ├── game_launcher.py            # Game launching
│   │   ├── annotator.py                # Screenshot annotation
│   │   ├── gemma_client.py             # Gemma vision client
│   │   ├── qwen_client.py              # Qwen VL client
│   │   ├── omniparser_client.py        # OmniParser client
│   │   └── simple_automation.py        # Simple automation
│   └── sut_service_installer/
│       └── gemma_client_0.2.py         # SUT agent
│
└── preset-manager/                     # Preset management system
    ├── app.py                          # Legacy Flask app
    ├── add_game.py                     # Game addition utility
    ├── modules/                        # Legacy helper modules
    │   ├── config_replacer.py
    │   ├── config_verifier.py
    │   ├── game_detector.py
    │   ├── path_resolver.py
    │   ├── ppg_preset_applier.py
    │   ├── registry_handler.py
    │   ├── steam_cli_handler.py
    │   ├── steam_verifier.py
    │   └── system_verifier.py
    ├── src/preset_manager/             # Main package
    │   ├── server.py                   # FastAPI server
    │   ├── api/                        # REST API endpoints
    │   ├── core/                       # Business logic
    │   ├── discovery/                  # Device discovery
    │   ├── handlers/                   # Config handlers
    │   └── utils/                      # Utilities
    ├── sut_client/                     # SUT client package
    │   └── src/sut_client/
    │       ├── service.py              # Flask service
    │       ├── applier.py              # Preset application
    │       ├── backup.py               # Backup service
    │       ├── discovery.py            # UDP discovery
    │       ├── ws_client.py            # WebSocket client
    │       ├── input_controller.py     # Input simulation
    │       ├── launcher.py             # Game launching
    │       ├── steam.py                # Steam integration
    │       ├── hardware.py             # Hardware control
    │       ├── window.py               # Window management
    │       └── system.py               # System utilities
    ├── tools/                          # Utility tools
    │   ├── game_validator.py
    │   └── steam_api_helper.py
    ├── tests/                          # Test suite
    └── admin/                          # Admin web UI (React/TypeScript)
```

---

## Key Technologies

| Component | Technology |
|-----------|------------|
| Gemma GUI | Python tkinter |
| Gemma Backend | Python 3.10+ |
| Preset-Manager Master | FastAPI, Uvicorn |
| Preset-Manager SUT Client | Flask |
| Vision Models | Ollama (Gemma, Qwen VL), OmniParser |
| Configuration | YAML, JSON, INI, XML, Windows Registry |
| Networking | HTTP/REST, WebSocket, UDP |
| Input Simulation | pyautogui, pywin32 |
| Admin UI | React, TypeScript |

---

## Common Data Flows

### 1. Benchmark Automation Flow
```
1. User selects game and preset in Gemma GUI
2. Gemma calls Preset-Manager to apply preset
3. Preset-Manager Master pushes preset to SUT
4. SUT Client applies config files
5. Gemma launches game on SUT
6. Gemma's decision engine navigates to benchmark
7. Benchmark runs, results collected
8. Game closed, next iteration or game
```

### 2. SUT Discovery Flow
```
1. Master broadcasts UDP MASTER_ANNOUNCE on port 9999
2. SUT Client receives broadcast
3. SUT Client connects to Master via WebSocket
4. SUT sends registration message with device_id, hostname, CPU
5. Master registers SUT in device registry
6. SSE event sent to admin UI (sut_online)
7. SUT appears in dashboard
```

### 3. Preset Application Flow
```
1. API call: POST /sync/push {game, preset, sut_ids}
2. Master loads preset files from configs/presets/{game}/{preset}/
3. Master sends POST /apply-preset to each SUT
4. SUT Client:
   a. Optionally kills game process
   b. Creates backup of existing config
   c. Expands environment variables in paths
   d. Writes preset files to target locations
   e. For registry presets, uses reg import
5. Returns success/failure to Master
6. Master returns aggregate result to caller
```

---

## Configuration Examples

### Game Preset Configuration (configs/presets/{game}/metadata.json)
```json
{
  "name": "Counter-Strike 2",
  "short_name": "cs2",
  "steam_app_id": "730",
  "process_name": "cs2.exe",
  "config_files": [
    {
      "path": "%STEAM_GAME_730%\\game\\csgo\\cfg\\video.txt",
      "type": "ini",
      "filename": "video.txt"
    }
  ],
  "preset_levels": ["low", "medium", "high", "ultra"]
}
```

### Environment Variables Supported
- `%USERPROFILE%` - User home directory
- `%LOCALAPPDATA%` - Local app data
- `%APPDATA%` - Roaming app data
- `%PROGRAMFILES%` - Program Files
- `%PROGRAMFILES(X86)%` - Program Files (x86)
- `%STEAM_INSTALL%` - Steam installation directory
- `%STEAM_GAME_<appid>%` - Dynamic Steam game path

---

## Summary

Both Gemma and Preset-Manager work together to provide comprehensive game automation:

- **Gemma** handles the "intelligence" - knowing where to click, what to type, how to navigate game UIs
- **Preset-Manager** handles the "configuration" - applying graphics settings before benchmarks run
- **Shared SUT Client** executes actions on gaming machines - both input automation and config application

The systems use network discovery to find SUTs automatically, WebSocket for real-time communication, and HTTP for command execution. This architecture allows scaling to multiple gaming machines from a single controller.
