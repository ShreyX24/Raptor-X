# Service Manager

Desktop GUI application for managing and monitoring all Gemma services.

## Architecture

- **Entry Point**: `service_manager/src/service_manager/main.py`
- **Framework**: PySide6 6.6+ (Qt 6)
- **CLI Commands**: `gemma-manager` or `gemma-manager-gui`
- **Package**: `gemma-service-manager` v1.0.0

## Key Files

| File | Purpose |
|------|---------|
| `src/service_manager/main.py` | Application entry point |
| `src/service_manager/config.py` | Service configurations |
| `src/service_manager/settings.py` | User settings persistence |

## UI Components (`src/service_manager/ui/`)

| File | Purpose |
|------|---------|
| `main_window.py` | Main application window |
| `sidebar.py` | Service selection sidebar |
| `log_panel.py` | Log viewer and display |
| `settings_dialog.py` | Configuration dialog |
| `setup_wizard.py` | Initial setup wizard |
| `dashboard_panel.py` | Service dashboard view |
| `flow_diagram.py` | Service architecture diagram |

## Services (`src/service_manager/services/`)

| File | Purpose |
|------|---------|
| `process_manager.py` | Start/stop/monitor service processes |

## Features

### Process Management
- **Location**: `services/process_manager.py`
- Start/stop individual services
- Monitor process status
- View stdout/stderr logs

### Service Dashboard
- **Location**: `ui/dashboard_panel.py`
- Overview of all services
- Health status indicators
- Quick actions

### Flow Diagram
- **Location**: `ui/flow_diagram.py`
- Visual service architecture
- Connection status between services
- Animated data flow indicators

### Log Viewer
- **Location**: `ui/log_panel.py`
- Real-time log streaming
- Filter by log level
- Search functionality

### Settings
- **Location**: `ui/settings_dialog.py`
- OmniParser server configuration
- Local instance management (0-5 instances)
- Remote server URLs

## Managed Services

| Service | Default Port | Start Command |
|---------|--------------|---------------|
| Gemma Backend | 5000 | `gemma` |
| SUT Discovery | 5001 | `sut-discovery` |
| Preset Manager | 5002 | `preset-manager` |
| Queue Service | 9000 | `queue-service` |
| OmniParser | 8000-8004 | (configurable) |

## Styling

- Dark theme (VS Code colors)
- Monospace font for logs (Consolas)
- High DPI scaling support
- Custom Qt widget styling

## Configuration Storage

Settings stored in:
- Windows: `%APPDATA%/GemmaServiceManager/settings.json`
- Contains: window position, service paths, OmniParser URLs

## Dependencies

- **Depends on**: None (manages other services)
- **Depended by**: None (user-facing tool)

## Common Modifications

### Add new service
1. Add service config in `config.py`
2. Update sidebar in `ui/sidebar.py`
3. Add to process manager

### Modify UI styling
1. Edit stylesheet in `ui/main_window.py`
2. Update widget-specific styles

### Add new settings
1. Add to `settings_dialog.py`
2. Persist in `settings.py`
3. Apply on startup

## Recent Changes

| Date | Change |
|------|--------|
| 2024-12-31 | Added dashboard with flow diagram |
| 2024-12-31 | Added OmniParser instance management |
| 2024-12-31 | Fixed terminal panel layout |
