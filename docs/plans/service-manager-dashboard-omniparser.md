# Service Manager Dashboard & OmniParser Integration Plan

## User Requirements (Confirmed)
1. **OmniParser IPs**: List with Add/Edit/Remove (full UI with name, URL, enabled checkbox)
2. **Frontend Panels**: Minimize to headers only when dashboard active (collapsible, one-click expand)
3. **Flow Diagram**: Live status indicators (connection lines change color based on service health)

---

## Implementation Plan

### Phase 1: Data Layer
**File: `settings.py`**
- Add `OmniParserServer` dataclass (name, url, enabled)
- Add to `SettingsManager`: `get_omniparser_servers()`, `set_omniparser_servers()`, `get_omniparser_urls_env()`
- Store in JSON under `"omniparser_servers": [...]`

### Phase 2: Settings UI
**File: `settings_dialog.py`**
- Add `OmniParserServersTab` with QListWidget + Add/Edit/Remove buttons
- Add `OmniParserServerDialog` for editing individual servers
- Update `SettingsDialog._save_settings()` to save servers

### Phase 3: Process Manager Update
**File: `process_manager.py`**
- In `start_service()`, inject `OMNIPARSER_URLS` env var for queue-service
- Get URLs from `settings.get_omniparser_urls_env()` (comma-separated enabled URLs)

### Phase 4: Dashboard Widgets
**New File: `dashboard_panel.py`**
Create these widgets:
- `StatsCard` - Single stat display (total requests, success, failed, rate)
- `QueueDepthBar` - Visual progress bar for queue depth
- `OmniParserHealthWidget` - List of OmniParser instances with status dots
- `JobsTable` - QTableWidget showing recent jobs
- `DashboardPanel` - Main container with QTimer for 2s refresh, uses QNetworkAccessManager to fetch `/stats`, `/jobs`, `/probe`

### Phase 5: Flow Diagram
**New File: `flow_diagram.py`**
- `FlowDiagramWidget` using QPainter custom drawing
- Nodes: Gemma, Preset Manager, SUT Discovery, SUT Client, Queue Service, OmniParser
- Connections with arrows between nodes
- Status colors: green (running), yellow (starting/stopping), gray (stopped), red (unreachable)
- Connect to `process_manager.status_changed` signal for live updates

### Phase 6: Main Window Integration
**File: `main_window.py`**
- Add `dashboard_container` with `FlowDiagramWidget` + `DashboardPanel` in horizontal splitter
- Add `content_splitter` (vertical) for dashboard_container + log_container
- Add toolbar "Dashboard View" toggle button (Ctrl+D)
- `_toggle_dashboard_view()`: Show/hide dashboard, collapse/expand frontend panels
- `_collapse_frontend_panels()`: Hide log_text, set maxHeight=45 for gemma-frontend, pm-frontend
- `_expand_frontend_panels()`: Restore log_text visibility and full height
- Connect `status_changed` to `flow_diagram.update_status()`

---

## File Changes Summary

| File | Action | Changes |
|------|--------|---------|
| `settings.py` | Modify | Add OmniParserServer dataclass, storage methods |
| `settings_dialog.py` | Modify | Add OmniParser Servers tab |
| `process_manager.py` | Modify | Inject OMNIPARSER_URLS env var |
| `dashboard_panel.py` | Create | Queue service dashboard with API polling |
| `flow_diagram.py` | Create | Live service flow visualization |
| `main_window.py` | Modify | Dashboard integration, layout toggle |

---

## Layout Structure

```
MainWindow
├── Toolbar: [Start All] [Stop All] [Restart All] [Clear All] | [Dashboard View] | [Settings]
├── main_splitter (Horizontal)
│   ├── sidebar (180-300px)
│   └── right_panel
│       └── content_splitter (Vertical)
│           ├── dashboard_container (hidden by default)
│           │   └── dashboard_splitter (Horizontal)
│           │       ├── FlowDiagramWidget (400px)
│           │       └── DashboardPanel (600px)
│           └── log_container (existing 2-column grid)
└── StatusBar
```

---

## Signal Connections

| Source | Signal | Target | Slot |
|--------|--------|--------|------|
| `ProcessManager` | `status_changed(str, str)` | `FlowDiagramWidget` | `update_status()` |
| `Toolbar.dashboard_action` | `toggled(bool)` | `MainWindow` | `_toggle_dashboard_view()` |
| `DashboardPanel` | QTimer (2s) | `DashboardPanel` | `refresh_data()` |

---

## Config JSON Structure Addition

```json
{
  "omniparser_servers": [
    {"name": "Local", "url": "http://localhost:8000", "enabled": true},
    {"name": "GPU Server", "url": "http://192.168.1.100:8000", "enabled": true}
  ]
}
```

---

## Implementation Order
1. `settings.py` - Data layer first
2. `settings_dialog.py` - OmniParser tab
3. `process_manager.py` - Env var injection
4. `dashboard_panel.py` - Dashboard widgets
5. `flow_diagram.py` - Flow visualization
6. `main_window.py` - Final integration
