# RP-X API Cookbook

Complete API reference for all RP-X services. This document covers **316+ API endpoints** across 8 services.

---

## Table of Contents

1. [RPX Core Backend](#1-rpx-core-backend) - 91 endpoints
2. [SUT Client](#2-sut-client) - 30 endpoints
3. [SUT Discovery Service](#3-sut-discovery-service) - 33 endpoints
4. [Preset Manager](#4-preset-manager) - 79 endpoints
5. [Queue Service](#5-queue-service) - 7 endpoints
6. [Omniparser Server](#6-omniparser-server) - 5 endpoints
7. [Service Ports Reference](#7-service-ports-reference)

---

## 1. RPX Core Backend

**Base URL:** `http://localhost:5050`
**Framework:** Flask (Python)
**Description:** Main orchestration backend for automation runs, device management, and system coordination.

### 1.1 System Status & Health

#### GET `/api/status`
Get comprehensive system status.

**Response:**
```json
{
  "status": "online",
  "uptime": 3600,
  "websocket_clients": 2,
  "device_stats": {...},
  "mode": "external_services"
}
```

#### GET `/api/health`
Basic health check.

**Response:**
```json
{"status": "healthy", "mode": "external_services"}
```

---

### 1.2 Device Management

#### GET `/api/devices`
Get all discovered SUT devices.

**Response:**
```json
[{
  "device_id": "sut-123",
  "ip": "192.168.1.100",
  "port": 8080,
  "hostname": "gaming-pc",
  "status": "online",
  "capabilities": ["screenshot", "game_control"],
  "is_paired": true,
  "ssh_fingerprint": "SHA256:...",
  "master_key_installed": true
}]
```

#### GET `/api/devices/<device_id>`
Get specific device details.

---

### 1.3 Discovery Management

#### POST `/api/discovery/scan`
Force immediate discovery scan.

**Response:**
```json
{"status": "success", "devices_found": 3}
```

#### GET `/api/discovery/status`
Get discovery service status.

#### POST `/api/discovery/targets`
Add IP to discovery targets.

**Request:**
```json
{"ip": "192.168.1.100"}
```

#### DELETE `/api/discovery/targets/<ip>`
Remove IP from discovery targets.

#### GET `/api/discovery/network-info`
Get network interfaces and IP ranges.

#### POST `/api/discovery/rediscover-networks`
Force rediscovery of network ranges.

---

### 1.4 SUT Communication

#### GET `/api/sut/<device_id>/status`
Get SUT status.

#### GET `/api/sut/<device_id>/system_info`
Get detailed system information (CPU, GPU, RAM, OS).

#### GET `/api/sut/by-ip/<ip>/system_info`
Get system info by IP address.

#### GET `/api/sut/<device_id>/screenshot`
Take screenshot from SUT.

**Response:** PNG image

#### GET `/api/sut/<device_id>/display/resolutions`
Get supported display resolutions.

**Query Parameters:**
- `common_only` (bool, default: true)

#### POST `/api/sut/<device_id>/action`
Perform action on SUT.

**Request:**
```json
{
  "type": "click|key|type|scroll|drag",
  "x": 100,
  "y": 200,
  "button": "left"
}
```

#### POST `/api/sut/<device_id>/launch`
Launch application on SUT.

**Request:**
```json
{
  "path": "/path/to/app.exe",
  "process_id": "optional"
}
```

---

### 1.5 OmniParser Integration

#### GET `/api/omniparser/status`
Get OmniParser server status.

#### POST `/api/omniparser/analyze`
Analyze screenshot for UI elements.

**Request (multipart form):**
- `screenshot` (file)
- `use_paddleocr` (bool)
- `box_threshold` (float)
- `iou_threshold` (float)
- `text_threshold` (float)
- `include_annotation` (bool)

**Response:**
```json
{
  "elements": [...],
  "annotated_image": "base64..."
}
```

---

### 1.6 Game Configuration

#### GET `/api/games`
Get all game configurations.

#### GET `/api/games/<game_name>`
Get specific game config.

#### POST `/api/games`
Create new game configuration.

**Request:**
```json
{
  "name": "game-name",
  "yaml": "...yaml content..."
}
```

#### PUT `/api/games/<game_name>/yaml`
Update game YAML config.

**Request:**
```json
{"yaml": "...yaml content..."}
```

#### DELETE `/api/games/<game_name>`
Delete game configuration.

#### POST `/api/games/<game_name>/validate`
Validate YAML without saving.

#### GET `/api/games/<game_name>/check-availability`
Check if game is installed on SUT.

**Query Parameters:**
- `sut_ip` (required)

**Response:**
```json
{
  "available": true,
  "game_name": "Cyberpunk 2077",
  "steam_app_id": "1091500",
  "install_path": "D:/Steam/...",
  "match_method": "steam_app_id"
}
```

#### GET `/api/workflows`
Get all workflow summaries.

#### GET `/api/games/stats`
Get game statistics.

#### POST `/api/games/reload`
Reload configs from disk.

---

### 1.7 Preset Application

#### POST `/api/presets/apply`
Apply PPG presets to SUTs.

**Request:**
```json
{
  "sut_ips": ["192.168.0.102"],
  "games": ["cyberpunk-2077"],
  "preset": {
    "resolution": "1920x1080",
    "graphics": "high"
  }
}
```

**Response:**
```json
{
  "successful": [...],
  "failed": [...],
  "summary": {
    "total": 1,
    "successful": 1,
    "failed": 0
  }
}
```

#### POST `/api/presets/validate`
Validate preset availability (read-only check).

---

### 1.8 Automation Runs

#### POST `/api/runs`
Start new automation run.

**Request:**
```json
{
  "sut_ip": "192.168.0.102",
  "game_name": "cyberpunk-2077",
  "iterations": 3,
  "quality": "high",
  "resolution": "1080p",
  "skip_steam_login": false,
  "disable_tracing": false,
  "cooldown_seconds": 120,
  "tracing_agents": ["socwatch", "ptat"]
}
```

**Response:**
```json
{
  "status": "success",
  "run_id": "run-abc123",
  "message": "Run started"
}
```

#### GET `/api/runs`
Get all runs with pagination.

**Query Parameters:**
- `page` (default: 1)
- `per_page` (default: 50, max: 100)

#### GET `/api/runs/<run_id>`
Get specific run status.

#### POST `/api/runs/<run_id>/stop`
Stop automation run.

**Request (optional):**
```json
{"kill_game": true}
```

#### GET `/api/runs/<run_id>/logs`
Get run logs.

**Query Parameters:**
- `limit` (max: 2000)
- `offset`

#### GET `/api/runs/<run_id>/timeline`
Get run timeline events.

#### GET `/api/runs/<run_id>/screenshots/<filename>`
Get screenshot from run.

#### GET `/api/runs/stats`
Get run statistics.

---

### 1.9 Campaign Management (Multi-Game Runs)

#### POST `/api/campaigns`
Create multi-game campaign.

**Request:**
```json
{
  "sut_ip": "192.168.0.102",
  "games": ["Black Myth: Wukong", "Cyberpunk 2077"],
  "iterations": 3,
  "name": "Full Benchmark Suite",
  "quality": "high",
  "resolution": "1080p"
}
```

#### GET `/api/campaigns`
Get all campaigns.

#### GET `/api/campaigns/<campaign_id>`
Get campaign details.

#### POST `/api/campaigns/<campaign_id>/stop`
Stop all runs in campaign.

---

### 1.10 SUT Pairing

#### POST `/api/suts/pair`
Pair a SUT device.

**Request:**
```json
{"device_id": "sut-123", "paired_by": "user"}
```

#### POST `/api/suts/unpair/<device_id>`
Unpair a SUT.

#### GET `/api/suts/paired`
Get all paired SUTs.

---

### 1.11 Steam Account Management

#### GET `/api/accounts/status`
Get Steam account lock status.

**Response:**
```json
{
  "accounts": {
    "af": {"locked": true, "holder_sut": "192.168.1.100"},
    "gz": {"locked": false}
  }
}
```

---

### 1.12 Discovery Settings

#### GET `/api/settings/discovery`
Get discovery settings.

#### PUT `/api/settings/discovery`
Update discovery settings.

**Request:**
```json
{
  "discovery_interval": 60,
  "discovery_timeout": 5,
  "paired_devices_scan_interval": 0.5,
  "enable_priority_scanning": true
}
```

#### POST `/api/settings/discovery/reset`
Reset to defaults.

---

### 1.13 Tracing Configuration

#### GET `/api/tracing/config`
Get tracing configuration.

#### PUT `/api/tracing/config`
Update tracing config.

#### GET `/api/tracing/agents`
Get all tracing agents (socwatch, ptat, nvidia-nsight, etc.).

#### PUT `/api/tracing/agents/<agent_name>`
Update agent configuration.

#### POST `/api/tracing/agents/<agent_name>/toggle`
Enable/disable agent.

#### PUT `/api/tracing/output-dir`
Update tracing output directory.

**Request:**
```json
{"output_dir": "/path/to/traces"}
```

#### POST `/api/tracing/reload`
Reload tracing config from disk.

---

### 1.14 SSH Management

#### GET `/api/ssh/public-key`
Get Master's SSH public key.

**Response:**
```json
{
  "status": "success",
  "public_key": "ssh-ed25519 AAAA...",
  "key_file": "/path/to/id_ed25519.pub"
}
```

#### GET `/api/tracing/ssh/diagnose/<sut_ip>`
Diagnose SSH connectivity.

#### GET `/api/tracing/ssh/test/<sut_ip>`
Quick SSH connection test.

---

### 1.15 Admin Routes (Prefix: `/api/admin`)

#### GET `/api/admin/config`
Get full configuration.

#### PUT `/api/admin/config`
Update configuration.

#### POST `/api/admin/config/reset`
Reset to defaults.

#### GET `/api/admin/services`
Get all services with health status.

#### GET `/api/admin/services/<name>`
Get single service status.

#### PUT `/api/admin/services/<name>`
Update service configuration.

#### POST `/api/admin/services/<name>/restart`
Request service restart.

#### GET `/api/admin/services/<name>/status`
Get service health status.

#### GET `/api/admin/games`
List all game configs (admin).

**Query Parameters:**
- `include_hidden` (bool)

#### GET `/api/admin/games/<name>/yaml`
Get raw YAML content.

#### PUT `/api/admin/games/<name>/yaml`
Update YAML (creates backup).

#### POST `/api/admin/games`
Create new game config.

#### DELETE `/api/admin/games/<name>`
Delete game config (creates backup).

#### POST `/api/admin/validate-yaml`
Validate YAML syntax.

**Request:**
```json
{"content": "...yaml..."}
```

**Response:**
```json
{
  "valid": true,
  "warnings": [],
  "error": null,
  "line": null
}
```

#### GET `/api/admin/profiles`
Get configuration profiles.

#### PUT `/api/admin/profiles/<name>`
Create/update profile.

#### DELETE `/api/admin/profiles/<name>`
Delete profile.

#### POST `/api/admin/profiles/<name>/activate`
Activate profile.

#### GET `/api/admin/omniparser`
Get OmniParser settings.

#### PUT `/api/admin/omniparser`
Update OmniParser settings.

#### POST `/api/admin/omniparser/test`
Test OmniParser connection.

**Request:**
```json
{"url": "http://localhost:8000"}
```

#### GET `/api/admin/steam-accounts`
Get Steam account pairs.

#### PUT `/api/admin/steam-accounts`
Update Steam accounts.

#### GET `/api/admin/discovery`
Get discovery settings (admin).

#### PUT `/api/admin/discovery`
Update discovery settings.

#### GET `/api/admin/automation`
Get automation settings.

#### PUT `/api/admin/automation`
Update automation settings.

#### POST `/api/admin/games/<name>/image`
Upload custom game image (resizes to 460x215).

#### POST `/api/admin/games/<name>/image/steam`
Fetch game image from Steam CDN.

**Request:**
```json
{"steam_app_id": "750920"}
```

---

## 2. SUT Client

**Base URL:** `http://<sut_ip>:8080`
**Framework:** Flask (Python) + Waitress WSGI
**Description:** Service running on each SUT (System Under Test) for local control.

### 2.1 System Status & Health

#### GET `/status`
Get SUT status for discovery.

**Response:**
```json
{
  "status": "online",
  "unique_id": "device_id",
  "hostname": "gaming-pc",
  "version": "0.3.0",
  "rpx_sut_signature": "rpx_sut_v1",
  "capabilities": [
    "preset_application", "backup_restore", "game_launch",
    "input_automation", "screenshot", "steam_login",
    "process_control", "display_resolution"
  ],
  "screen": {"width": 1920, "height": 1080},
  "game": {...}
}
```

#### GET `/health`
Basic health check.

#### GET `/info`
Get SUT information.

#### GET `/system_info`
Get detailed hardware info.

**Response:**
```json
{
  "cpu": {"brand_string": "Intel Core i7-12700K"},
  "gpu": {"name": "NVIDIA GeForce RTX 4080"},
  "ram": {"total_gb": 32},
  "os": {"name": "Windows", "version": "11", "build": "22631"},
  "screen": {"width": 1920, "height": 1080}
}
```

#### GET `/screen_info`
Get screen resolution.

---

### 2.2 Logging

#### GET `/logs`
Retrieve SUT client logs.

**Query Parameters:**
- `lines` (int, default: 1000)
- `since` (ISO timestamp)
- `download` (bool)

#### POST `/logs/clear`
Clear/rotate log file.

---

### 2.3 Preset & Configuration

#### POST `/apply-preset`
Apply a preset from Master.

**Request:**
```json
{
  "game_short_name": "rdr2",
  "preset_level": "ultra",
  "files": [{"path": "...", "content": "..."}],
  "backup": true
}
```

#### POST `/restore-config`
Restore config from backup.

**Request:**
```json
{
  "game_slug": "rdr2",
  "backup_id": "optional_backup_id"
}
```

#### GET `/backups`
List all backups.

**Query Parameters:**
- `game` (filter by game)

#### POST `/flash_preset`
Flash preset file directly to game folder.

**Request:**
```json
{
  "game_folder": "D:/Steam/common/game",
  "preset_filename": "config.ini",
  "preset_content": "...ini content...",
  "create_backup": true
}
```

---

### 2.4 Display Resolution

#### GET `/display/current`
Get current resolution.

**Response:**
```json
{
  "status": "success",
  "resolution": {
    "width": 1920,
    "height": 1080,
    "refresh_rate": 60
  }
}
```

#### GET `/display/resolutions`
Get supported resolutions.

**Query Parameters:**
- `common_only` (bool)

#### POST `/display/resolution`
Set display resolution.

**Request:**
```json
{
  "width": 1920,
  "height": 1080,
  "refresh_rate": 60
}
```

#### POST `/display/restore`
Restore original resolution.

---

### 2.5 Game Management

#### GET `/installed_games`
Scan for installed games.

**Response:**
```json
{
  "success": true,
  "games": [{
    "steam_app_id": "1234567",
    "name": "Red Dead Redemption 2",
    "install_path": "D:/Steam/.../RDR2",
    "source": "steam"
  }],
  "count": 50
}
```

#### POST `/find_standalone_game`
Find standalone game by folder name.

**Request:**
```json
{
  "folder_names": ["ffxiv-dawntrail-bench_v11"],
  "exe_name": "ffxiv-dawntrail-bench.exe"
}
```

---

### 2.6 Game Launch & Control

#### POST `/launch`
Launch a game.

**Request:**
```json
{
  "steam_app_id": "1234567",
  "exe_path": "C:/path/to/game.exe",
  "process_name": "game.exe",
  "force_relaunch": false,
  "launch_args": "-benchmark",
  "startup_wait": 30
}
```

#### POST `/cancel_launch`
Cancel ongoing game launch.

#### POST `/terminate_game`
Terminate current game.

#### POST `/focus`
Focus a window.

**Request:**
```json
{
  "process_name": "steam",
  "minimize_others": false
}
```

---

### 2.7 Input Automation

#### POST `/action`
Unified input action endpoint.

**Request (click):**
```json
{
  "action": "click",
  "x": 100,
  "y": 200,
  "button": "left"
}
```

**Request (key):**
```json
{
  "action": "key",
  "key": "enter",
  "count": 1
}
```

**Request (type):**
```json
{
  "action": "type",
  "text": "Hello World",
  "interval": 0.02
}
```

**Request (hotkey):**
```json
{
  "action": "hotkey",
  "keys": ["ctrl", "c"]
}
```

**Request (scroll):**
```json
{
  "action": "scroll",
  "direction": "down",
  "clicks": 3
}
```

**Request (drag):**
```json
{
  "action": "drag",
  "x": 100,
  "y": 200,
  "end_x": 300,
  "end_y": 400
}
```

#### GET|POST `/screenshot`
Take screenshot.

**Query Parameters (GET) or Body (POST):**
- `region` (string): "x,y,width,height"
- `format` (string): "png" or "base64"
- `process_name` (string): focus before screenshot

---

### 2.8 Process Control

#### POST `/check_process`
Check if process is running.

**Request:**
```json
{"process_name": "game.exe"}
```

#### POST `/kill_process` or `/kill`
Kill process by name.

**Request:**
```json
{"process_name": "game.exe"}
```

---

### 2.9 Script Execution

#### POST `/execute`
Execute script or command.

**Request:**
```json
{
  "path": "C:\\Tools\\socwatch64.exe",
  "args": ["-f", "cpu", "-o", "output"],
  "working_dir": "C:\\Tools",
  "timeout": 300,
  "async": false,
  "shell": true
}
```

#### POST `/terminate`
Terminate process by PID.

**Request:**
```json
{"pid": 12345}
```

---

### 2.10 Steam

#### GET `/steam/current`
Get logged-in Steam user.

**Response:**
```json
{
  "status": "success",
  "logged_in": true,
  "username": "steam_user",
  "user_id": 123456789
}
```

#### POST `/login_steam`
Login to Steam.

**Request:**
```json
{
  "username": "steam_user",
  "password": "password",
  "timeout": 180
}
```

---

## 3. SUT Discovery Service

**Base URL:** `http://localhost:5001`
**Framework:** FastAPI (Python)
**Description:** Central gateway for SUT discovery and WebSocket-based registration.

### 3.1 Health & Service Info

#### GET `/`
Service information.

#### GET `/health`
Health check with device stats.

**Response:**
```json
{
  "status": "healthy",
  "service": "sut-discovery-service",
  "websocket_connections": 3,
  "devices": {
    "total_devices": 5,
    "online_devices": 3,
    "paired_devices": 1
  }
}
```

---

### 3.2 SUT Management

#### GET `/api/suts`
List all discovered SUTs.

**Query Parameters:**
- `status`: "online", "offline", or "paired"

#### GET `/api/suts/{unique_id}`
Get specific SUT details.

#### POST `/api/suts/{unique_id}/pair`
Pair a SUT.

**Request:**
```json
{"paired_by": "user"}
```

#### POST `/api/suts/{unique_id}/unpair`
Unpair a SUT.

#### POST `/api/suts/{unique_id}/display-name`
Set custom display name.

**Request:**
```json
{"display_name": "My Gaming PC"}
```

#### DELETE `/api/suts/{unique_id}`
Delete SUT from registry.

**Query Parameters:**
- `force` (bool): Force delete even if paired

---

### 3.3 Discovery

#### POST `/api/discover`
Trigger discovery scan.

#### GET `/api/discover/status` or `/api/discovery/status`
Get discovery status.

---

### 3.4 Real-Time Events

#### GET `/api/suts/events` (SSE)
Server-Sent Events for SUT updates.

**Events:**
- `sut_online`: SUT connected
- `sut_offline`: SUT disconnected
- `connected`: Initial connection

#### WebSocket `/api/ws/sut/{sut_id}`
WebSocket for SUT registration.

**Initial message from SUT:**
```json
{
  "ip": "192.168.1.100",
  "port": 8080,
  "hostname": "gaming-pc",
  "capabilities": [...],
  "ssh_public_key": "ssh-ed25519 AAAA..."
}
```

**Acknowledgment:**
```json
{
  "type": "register_ack",
  "sut_id": "sut-123",
  "master_public_key": "ssh-ed25519 AAAA...",
  "session_id": "session-xyz"
}
```

---

### 3.5 Stale Device Cleanup

#### GET `/api/suts/settings/stale-timeout`
Get stale timeout setting.

#### PUT `/api/suts/settings/stale-timeout`
Set stale timeout.

**Request:**
```json
{"timeout_seconds": 7200}
```

#### POST `/api/suts/cleanup`
Remove stale devices.

---

### 3.6 SSH Management

#### POST `/api/suts/{unique_id}/ssh/exchange`
Trigger SSH key exchange.

#### GET `/api/suts/{unique_id}/ssh/status`
Get SSH status.

#### GET `/api/suts/ssh/diagnose/{ip}`
Diagnose SSH connectivity.

#### GET `/api/ssh/master-key`
Get Master's SSH key info.

---

### 3.7 SUT Proxy Endpoints

These proxy requests to individual SUTs:

- `GET /api/suts/{unique_id}/games` - Installed games
- `POST /api/suts/{unique_id}/apply-preset` - Apply preset
- `GET /api/suts/{unique_id}/screenshot` - Screenshot
- `POST /api/suts/{unique_id}/action` - Input action
- `POST /api/suts/{unique_id}/launch` - Launch game
- `POST /api/suts/{unique_id}/check-process` - Check process
- `POST /api/suts/{unique_id}/kill-process` - Kill process
- `POST /api/suts/{unique_id}/terminate-game` - Terminate game
- `GET /api/suts/{unique_id}/status` - SUT status
- `GET /api/suts/{unique_id}/health` - SUT health
- `GET /api/suts/{unique_id}/screen-info` - Screen info
- `GET /api/suts/{unique_id}/performance` - Performance metrics

---

### 3.8 Update Broadcast

#### POST `/api/suts/broadcast-update`
Broadcast update to all SUTs.

**Request:**
```json
{
  "master_ip": "192.168.1.1",
  "version": "v6.0.0",
  "components": {
    "sut_client": "v1.5.0"
  }
}
```

---

## 4. Preset Manager

**Base URL:** `http://localhost:5002`
**Framework:** FastAPI (Python)
**Description:** Manages game presets, file storage, and SUT synchronization.

### 4.1 Root & Health

#### GET `/`
Service information.

#### GET `/health`
Health check.

#### GET `/api`
API root with endpoints map.

---

### 4.2 Games API

#### GET `/api/games`
List all games.

**Query Parameters:**
- `skip` (int, default: 0)
- `limit` (int, default: 100, max: 1000)
- `enabled_only` (bool, default: true)
- `search` (string)

#### GET `/api/games/stats`
Game statistics.

**Response:**
```json
{
  "total_games": 50,
  "enabled_games": 45,
  "total_presets": 200,
  "total_suts": 5
}
```

#### GET `/api/games/{game_slug}`
Get game details.

#### GET `/api/games/short-name/{short_name}`
Get game by short name.

#### GET `/api/games/{game_slug}/presets`
Get all preset levels for a game.

---

### 4.3 Presets API

#### GET `/api/presets/{game_short_name}/{level}/metadata`
Get preset metadata.

**Response:**
```json
{
  "game": {"name": "...", "short_name": "..."},
  "preset": {
    "level": "high-1080p",
    "target_gpu": "RTX 4080",
    "resolution": "1920x1080",
    "target_fps": "60"
  },
  "files": [{"filename": "config.ini", "size_bytes": 1024, "hash": "..."}]
}
```

#### GET `/api/presets/{game_short_name}/{level}/files`
Download preset files as ZIP.

#### GET `/api/presets/{game_short_name}/{level}/files/{filename}`
Download specific file.

#### GET `/api/presets/{game_short_name}/list`
List preset levels for a game.

#### POST `/api/presets/{game_slug}/upload`
Upload preset files.

**Form Data:**
- `level` (required)
- `files` (required)
- `description`
- `target_gpu`
- `resolution`
- `target_fps`
- `notes`

#### POST `/api/presets/{game_slug}/upload-zip`
Upload ZIP with presets.

#### DELETE `/api/presets/{game_slug}/{level}/files/{filename}`
Delete preset file.

#### GET `/api/presets/{game_slug}/{level}/list-files`
List files in preset level.

#### GET `/api/presets/{game_slug}/matrix`
Get preset availability matrix.

**Response:**
```json
{
  "game": "cyberpunk-2077",
  "quality_levels": ["low", "medium", "high", "ultra"],
  "resolutions": ["720p", "1080p", "1440p", "2160p"],
  "available": {
    "high": {
      "1080p": {"exists": true, "has_files": true, "status": "ready"}
    }
  }
}
```

#### GET `/api/presets/{game_slug}/{quality}/{resolution}/metadata`
Get preset by quality and resolution.

#### GET `/api/presets/{game_slug}/{level}/content`
Get preset file content as text.

**Query Parameters:**
- `filename` (optional)

#### GET `/api/constants`
Get system constants.

**Response:**
```json
{
  "quality_levels": ["low", "medium", "high", "ultra"],
  "resolutions": {
    "720p": {"width": 1280, "height": 720},
    "1080p": {"width": 1920, "height": 1080},
    "1440p": {"width": 2560, "height": 1440},
    "2160p": {"width": 3840, "height": 2160}
  }
}
```

---

### 4.4 SUTs API

#### WebSocket `/api/ws/sut/{sut_id}`
WebSocket for SUT communication.

#### GET `/api/suts/events` (SSE)
Real-time SUT updates.

#### GET `/api/suts`
List all SUTs.

**Query Parameters:**
- `status`: "online", "offline", "busy", "error"

#### GET `/api/suts/stats`
SUT statistics.

#### GET `/api/suts/discovered`
List discovered SUTs.

#### GET `/api/suts/discovered/{unique_id}`
Get discovered SUT details.

#### GET `/api/suts/{unique_id}`
Get SUT by ID.

#### POST `/api/suts/discovered/{unique_id}/pair`
Pair a SUT.

#### DELETE `/api/suts/discovered/{unique_id}/pair`
Unpair a SUT.

#### GET `/api/suts/discovery/status`
Discovery service status.

#### POST `/api/suts/discovery/scan`
Force discovery scan.

#### POST `/api/suts/discovered/{unique_id}/launch`
Launch game on SUT.

**Request:**
```json
{
  "steam_app_id": "1234567",
  "process_name": "optional"
}
```

#### GET `/api/suts/ws/connected`
List WebSocket-connected SUTs.

#### GET `/api/suts/ws/{sut_id}`
Get WebSocket SUT info.

#### POST `/api/suts/ws/{sut_id}/command`
Send command via WebSocket.

**Request:**
```json
{"type": "command_type", "data": {...}}
```

#### POST `/api/suts/ws/broadcast`
Broadcast to multiple SUTs.

**Request:**
```json
{
  "command": {...},
  "sut_ids": ["id1", "id2"]
}
```

#### POST `/api/suts/ws/{sut_id}/ping`
Ping SUT via WebSocket.

#### POST `/api/suts/ws/ping-all`
Ping all SUTs.

#### PUT `/api/suts/{unique_id}/display-name`
Set SUT display name.

**Request:**
```json
{"display_name": "My PC"}
```

#### POST `/api/suts/{unique_id}/rename-pc`
Rename Windows hostname (requires reboot).

**Request:**
```json
{"new_name": "GAMING-PC"}
```

#### GET `/api/suts/{unique_id}/suggest-name`
Get suggested name based on CPU.

---

### 4.5 Sync API

#### POST `/api/sync/push`
Push preset to SUTs.

**Request:**
```json
{
  "game_short_name": "cyberpunk-2077",
  "preset_level": "high-1080p",
  "sut_unique_ids": ["sut-1", "sut-2"]
}
```

#### POST `/api/sync/bulk`
Bulk sync operations.

**Request:**
```json
{
  "operations": [
    {
      "game_slug": "cyberpunk-2077",
      "preset_level": "high-1080p",
      "sut_unique_ids": ["sut-1"]
    }
  ]
}
```

#### GET `/api/sync/games`
List games with presets.

#### GET `/api/sync/presets/{game_slug}`
List presets for a game.

#### POST `/api/sync/rollback/{sut_unique_id}`
Rollback config from backup.

**Request:**
```json
{
  "game_slug": "cyberpunk-2077",
  "backup_id": "optional"
}
```

#### GET `/api/sync/stats`
Sync statistics.

#### POST `/api/sync/gemma-presets`
Apply presets before automation.

**Request:**
```json
{
  "sut_ips": ["192.168.1.100"],
  "games": ["cyberpunk-2077"],
  "preset": {
    "resolution": "1920x1080",
    "graphics": "high"
  },
  "run_id": "optional"
}
```

**Response:**
```json
{
  "successful": [{"sut_ip": "...", "game": "...", "preset_level": "..."}],
  "failed": [],
  "skipped": [],
  "summary": {"successful": 1, "failed": 0, "skipped": 0}
}
```

#### GET `/api/sync/sut-games/{sut_ip}`
Get installed games with preset availability.

**Query Parameters:**
- `port` (int, default: 8080)

---

### 4.6 Backups API

#### GET `/api/backups`
List all backups.

#### GET `/api/backups/{game_slug}`
List backups for a game.

#### GET `/api/backups/{game_slug}/latest`
Get latest backup.

#### GET `/api/backups/{game_slug}/{backup_id}`
Get backup details.

#### DELETE `/api/backups/{game_slug}/{backup_id}`
Delete backup.

#### POST `/api/backups/{game_slug}/cleanup`
Cleanup old backups.

**Query Parameters:**
- `keep_count` (int, default: 5)

#### GET `/api/backups/stats/summary`
Backup statistics.

#### POST `/api/backups/maintenance/cleanup-empty`
Remove empty backup directories.

---

## 5. Queue Service

**Base URL:** `http://localhost:8001`
**Framework:** FastAPI (Python)
**Description:** OmniParser request queue middleware with load balancing.

### 5.1 Health & Info

#### GET `/`
Service information.

**Response:**
```json
{
  "service": "Queue Service",
  "version": "1.0.0",
  "target_servers": ["http://server1:8000"],
  "server_count": 2,
  "load_balancing": "round-robin"
}
```

#### GET `/probe`
Comprehensive health check.

**Response:**
```json
{
  "service": "queue-service",
  "queue_service_status": "running",
  "omniparser_status": [
    {"url": "http://server1:8000", "status": "healthy"}
  ],
  "omniparser_healthy_count": 2,
  "stats": {...}
}
```

#### GET `/health`
Basic health check.

---

### 5.2 Parse (Main Processing)

#### POST `/parse/`
Parse image (queued).

**Request:**
```json
{
  "base64_image": "...",
  "box_threshold": 0.05,
  "iou_threshold": 0.1,
  "use_paddleocr": true,
  "text_threshold": 0.8,
  "use_local_semantics": true,
  "scale_img": false,
  "imgsz": null
}
```

**Response:**
```json
{
  "parsed_content_list": [...],
  "som_image_base64": "..."
}
```

**Error Codes:**
- `503`: Queue is full
- `504`: Request timed out
- `500`: Processing error

---

### 5.3 Statistics & Monitoring

#### GET `/stats`
Queue statistics.

**Response:**
```json
{
  "total_requests": 100,
  "successful_requests": 95,
  "failed_requests": 3,
  "timeout_requests": 2,
  "current_queue_size": 5,
  "worker_running": true,
  "num_workers": 2,
  "avg_processing_time": 2.5,
  "avg_queue_wait_time": 0.5,
  "requests_per_minute": 10.0
}
```

#### GET `/jobs`
Recent job history.

**Query Parameters:**
- `limit` (int, 1-100, default: 20)

**Response:**
```json
{
  "jobs": [{
    "job_id": "abc123",
    "timestamp": "2026-01-26T12:00:00",
    "status": "success",
    "processing_time": 2.5,
    "queue_wait_time": 0.5
  }],
  "count": 20
}
```

#### GET `/queue-depth`
Queue depth history.

**Query Parameters:**
- `limit` (int, 1-200, default: 50)

---

## 6. Omniparser Server

**Base URL:** `http://localhost:8000`
**Framework:** FastAPI (Python)
**Description:** AI-powered UI element detection using YOLO + OCR.

### 6.1 Parse

#### POST `/parse/`
Parse screenshot for UI elements.

**Request:**
```json
{
  "base64_image": "...",
  "box_threshold": 0.05,
  "iou_threshold": 0.1,
  "use_paddleocr": true,
  "text_threshold": 0.8,
  "use_local_semantics": true,
  "scale_img": false,
  "imgsz": null
}
```

**Response:**
```json
{
  "som_image_base64": "...",
  "parsed_content_list": [
    {"type": "text", "content": "Button", "bbox": [100, 200, 150, 230]},
    {"type": "icon", "content": "close_button", "bbox": [300, 50, 330, 80]}
  ],
  "latency": 2.5,
  "config_used": "defaults"
}
```

#### GET `/probe/`
Health check.

**Response:**
```json
{"message": "Omniparser API ready"}
```

---

### 6.2 Windows VM Control Server

**Base URL:** `http://<vm_ip>:5000`
**Framework:** Flask (Python)
**Description:** Remote control server for Windows VM (runs inside VM).

#### GET `/probe`
Health check.

**Response:**
```json
{
  "status": "Probe successful",
  "message": "Service is operational"
}
```

#### POST `/execute`
Execute shell command.

**Request:**
```json
{
  "command": "dir C:\\",
  "shell": true
}
```

**Response:**
```json
{
  "status": "success",
  "output": "...",
  "error": "",
  "returncode": 0
}
```

#### GET `/screenshot`
Capture VM screenshot.

**Response:** PNG image (binary)

---

## 7. Service Ports Reference

| Service | Default Port | Protocol |
|---------|-------------|----------|
| RPX Core Backend | 5050 | HTTP |
| SUT Client | 8080 | HTTP |
| SUT Discovery Service | 5001 | HTTP + WebSocket |
| Preset Manager | 5002 | HTTP + WebSocket + SSE |
| Queue Service | 8001 | HTTP |
| OmniParser Server | 8000 | HTTP |
| Windows VM Control | 5000 | HTTP |
| RPX Frontend | 5173 | HTTP (Vite dev) |
| Preset Manager Frontend | 5174 | HTTP (Vite dev) |

---

## Quick Reference: Common Workflows

### Start an Automation Run
```bash
curl -X POST http://localhost:5050/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "sut_ip": "192.168.1.100",
    "game_name": "cyberpunk-2077",
    "iterations": 3,
    "quality": "high",
    "resolution": "1080p"
  }'
```

### Apply Preset to SUT
```bash
curl -X POST http://localhost:5050/api/presets/apply \
  -H "Content-Type: application/json" \
  -d '{
    "sut_ips": ["192.168.1.100"],
    "games": ["cyberpunk-2077"],
    "preset": {"resolution": "1920x1080", "graphics": "high"}
  }'
```

### Take Screenshot from SUT
```bash
curl http://localhost:5050/api/sut/sut-123/screenshot -o screenshot.png
```

### Launch Game on SUT
```bash
curl -X POST http://localhost:5050/api/sut/sut-123/launch \
  -H "Content-Type: application/json" \
  -d '{"steam_app_id": "1091500"}'
```

### Parse UI Elements with OmniParser
```bash
curl -X POST http://localhost:8000/parse/ \
  -H "Content-Type: application/json" \
  -d '{"base64_image": "...", "use_paddleocr": true}'
```

### Check System Health
```bash
# RPX Core
curl http://localhost:5050/api/health

# SUT Discovery
curl http://localhost:5001/health

# Preset Manager
curl http://localhost:5002/health

# Queue Service
curl http://localhost:8001/probe

# OmniParser
curl http://localhost:8000/probe/
```

---

*Generated: 2026-01-26*
*Total Endpoints: 316+*
