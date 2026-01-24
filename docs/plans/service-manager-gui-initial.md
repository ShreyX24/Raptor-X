# Gemma Service Manager GUI

## Overview

A PySide6-based GUI application to manage all Gemma services with:
- Sidebar tree with service list
- Embedded log panels showing real-time output
- Start/Stop controls
- Status indicators (running/stopped)
- Split-pane layout like MobaXterm

## Services to Manage

| Service | Command | Working Dir | Port |
|---------|---------|-------------|------|
| Gemma Backend | `gemma --port 5000` | `Gemma/` | 5000 |
| Gemma Frontend | `npm run dev -- --host` | `Gemma/admin/` | 3000 |
| SUT Discovery | `sut-discovery --port 5001` | `sut_discovery_service/` | 5001 |
| Queue Service | `queue-service --port 9000` | `queue_service/` | 9000 |
| Queue Dashboard | `queue-dashboard --url http://localhost:9000` | `queue_service/` | - |
| Preset Manager | `preset-manager --port 5002` | `preset-manager/` | 5002 |
| PM Frontend | `npm run dev -- --host --port 3001` | `preset-manager/admin/` | 3001 |

---

## Directory Structure

```
D:\Code\Gemma\service_manager\
├── pyproject.toml
├── src/
│   └── service_manager/
│       ├── __init__.py
│       ├── __main__.py           # Entry point
│       ├── main.py               # Application launcher
│       ├── config.py             # Service definitions
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── main_window.py    # QMainWindow
│       │   ├── sidebar.py        # QTreeWidget for service list
│       │   ├── log_panel.py      # QPlainTextEdit with ANSI support
│       │   └── status_bar.py     # Bottom status bar
│       ├── services/
│       │   ├── __init__.py
│       │   ├── process_manager.py # QProcess wrapper
│       │   └── service.py         # Service model class
│       └── resources/
│           ├── icons/             # Status icons
│           └── styles.qss         # Qt stylesheet
```

---

## Core Components

### 1. Service Configuration (`config.py`)

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

BASE_DIR = Path("D:/Code/Gemma")

@dataclass
class ServiceConfig:
    name: str
    display_name: str
    command: list[str]
    working_dir: Path
    port: Optional[int] = None
    group: str = "Backends"
    depends_on: list[str] = None
    startup_delay: float = 0.0

SERVICES = [
    ServiceConfig(
        name="sut-discovery",
        display_name="SUT Discovery",
        command=["sut-discovery", "--port", "5001"],
        working_dir=BASE_DIR / "sut_discovery_service",
        port=5001,
        group="Core Services",
    ),
    ServiceConfig(
        name="queue-service",
        display_name="Queue Service",
        command=["queue-service", "--port", "9000"],
        working_dir=BASE_DIR / "queue_service",
        port=9000,
        group="Core Services",
    ),
    ServiceConfig(
        name="gemma-backend",
        display_name="Gemma Backend",
        command=["gemma", "--port", "5000"],
        working_dir=BASE_DIR / "Gemma",
        port=5000,
        group="Gemma",
        depends_on=["sut-discovery"],
    ),
    ServiceConfig(
        name="gemma-frontend",
        display_name="Gemma Frontend",
        command=["npm", "run", "dev", "--", "--host"],
        working_dir=BASE_DIR / "Gemma" / "admin",
        port=3000,
        group="Gemma",
        depends_on=["gemma-backend"],
        startup_delay=5.0,
    ),
    ServiceConfig(
        name="preset-manager",
        display_name="Preset Manager",
        command=["preset-manager", "--port", "5002"],
        working_dir=BASE_DIR / "preset-manager",
        port=5002,
        group="Preset Manager",
        depends_on=["sut-discovery"],
    ),
    ServiceConfig(
        name="pm-frontend",
        display_name="PM Frontend",
        command=["npm", "run", "dev", "--", "--host", "--port", "3001"],
        working_dir=BASE_DIR / "preset-manager" / "admin",
        port=3001,
        group="Preset Manager",
        depends_on=["preset-manager"],
        startup_delay=5.0,
    ),
]
```

### 2. Main Window (`ui/main_window.py`)

```python
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QToolBar, QStatusBar
)
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemma Service Manager")
        self.resize(1400, 900)

        # Main splitter: sidebar | log panels
        self.main_splitter = QSplitter(Qt.Horizontal)

        # Sidebar (service tree)
        self.sidebar = ServiceSidebar()
        self.sidebar.setMaximumWidth(250)

        # Log panel container (splittable)
        self.log_container = LogPanelContainer()

        self.main_splitter.addWidget(self.sidebar)
        self.main_splitter.addWidget(self.log_container)
        self.main_splitter.setSizes([200, 1200])

        self.setCentralWidget(self.main_splitter)

        # Toolbar
        self.setup_toolbar()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
```

### 3. Sidebar (`ui/sidebar.py`)

```python
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon

class ServiceSidebar(QTreeWidget):
    service_selected = Signal(str)  # service name
    service_start_requested = Signal(str)
    service_stop_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setHeaderLabel("Services")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.groups = {}  # group_name -> QTreeWidgetItem
        self.service_items = {}  # service_name -> QTreeWidgetItem

    def add_service(self, config: ServiceConfig):
        # Create group if needed
        if config.group not in self.groups:
            group_item = QTreeWidgetItem([config.group])
            group_item.setExpanded(True)
            self.addTopLevelItem(group_item)
            self.groups[config.group] = group_item

        # Add service under group
        item = QTreeWidgetItem([config.display_name])
        item.setData(0, Qt.UserRole, config.name)
        self.groups[config.group].addChild(item)
        self.service_items[config.name] = item

    def update_status(self, service_name: str, status: str):
        """Update status icon: running (green), stopped (red), starting (yellow)"""
        item = self.service_items.get(service_name)
        if item:
            # Set icon based on status
            icon = self.get_status_icon(status)
            item.setIcon(0, icon)
```

### 4. Log Panel (`ui/log_panel.py`)

```python
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Slot
from PySide6.QtGui import QTextCharFormat, QColor, QFont

class LogPanel(QWidget):
    """Embedded terminal-like log panel with ANSI color support."""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with service name
        self.header = QLabel(service_name)
        self.header.setStyleSheet("background: #2d2d2d; color: white; padding: 4px;")

        # Log text area
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
            }
        """)
        self.log_text.setMaximumBlockCount(10000)  # Limit lines

        layout.addWidget(self.header)
        layout.addWidget(self.log_text)

    @Slot(str)
    def append_output(self, text: str):
        """Append text with basic ANSI color parsing."""
        # Strip ANSI codes for now (can add full support later)
        clean_text = self.strip_ansi(text)
        self.log_text.appendPlainText(clean_text)

        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
```

### 5. Process Manager (`services/process_manager.py`)

```python
from PySide6.QtCore import QObject, QProcess, Signal
from typing import Dict
import os

class ProcessManager(QObject):
    """Manages QProcess instances for all services."""

    output_received = Signal(str, str)  # service_name, text
    status_changed = Signal(str, str)   # service_name, status

    def __init__(self):
        super().__init__()
        self.processes: Dict[str, QProcess] = {}
        self.configs: Dict[str, ServiceConfig] = {}

    def register_service(self, config: ServiceConfig):
        self.configs[config.name] = config

    def start_service(self, name: str):
        if name in self.processes:
            return  # Already running

        config = self.configs[name]

        process = QProcess()
        process.setWorkingDirectory(str(config.working_dir))

        # Set environment (inherit + add USE_EXTERNAL_DISCOVERY for PM)
        env = QProcess.systemEnvironment()
        if name == "preset-manager":
            env.append("USE_EXTERNAL_DISCOVERY=true")
        process.setEnvironment(env)

        # Connect signals
        process.readyReadStandardOutput.connect(
            lambda: self._handle_stdout(name, process)
        )
        process.readyReadStandardError.connect(
            lambda: self._handle_stderr(name, process)
        )
        process.started.connect(lambda: self.status_changed.emit(name, "running"))
        process.finished.connect(lambda: self._handle_finished(name))

        self.processes[name] = process
        self.status_changed.emit(name, "starting")

        # Start process
        process.start(config.command[0], config.command[1:])

    def stop_service(self, name: str):
        process = self.processes.get(name)
        if process:
            self.status_changed.emit(name, "stopping")
            process.terminate()
            if not process.waitForFinished(5000):
                process.kill()
            del self.processes[name]

    def _handle_stdout(self, name: str, process: QProcess):
        data = process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        self.output_received.emit(name, data)

    def _handle_stderr(self, name: str, process: QProcess):
        data = process.readAllStandardError().data().decode('utf-8', errors='replace')
        self.output_received.emit(name, data)

    def _handle_finished(self, name: str):
        if name in self.processes:
            del self.processes[name]
        self.status_changed.emit(name, "stopped")
```

---

## UI Layout

```
+------------------+------------------------------------------------+
| Services         | [Toolbar: Start All | Stop All | Clear Logs]   |
|------------------|------------------------------------------------|
| v Core Services  | +---------------------+----------------------+ |
|   * SUT Discovery|  | SUT Discovery       | Queue Service       | |
|   * Queue Service|  | 2025-12... INFO ... | 2025-12... INFO ... | |
|                  |  | ...                 | ...                 | |
| v Gemma          |  +---------------------+----------------------+ |
|   * Backend      |  | Gemma Backend       | Gemma Frontend      | |
|   * Frontend     |  | 2025-12... INFO ... | ready - started ... | |
|                  |  | ...                 | ...                 | |
| v Preset Manager |  +---------------------+----------------------+ |
|   * Backend      |  |                                            | |
|   * Frontend     |  |                                            | |
+------------------+------------------------------------------------+
| Status: 4/7 services running | SUT Discovery: 5001 | Gemma: 5000  |
+---------------------------------------------------------------+
```

---

## Features

### Toolbar Actions
- **Start All**: Start all services in dependency order
- **Stop All**: Stop all services (reverse order)
- **Start Selected**: Start only selected service
- **Stop Selected**: Stop only selected service
- **Clear Logs**: Clear log panels
- **Arrange 2x2**: Arrange 4 visible panels in 2x2 grid
- **Arrange 2x3**: Arrange 6 visible panels in 2x3 grid

### Context Menu (Right-click service)
- Start
- Stop
- Restart
- Show Logs
- Copy Logs
- Open Working Directory

### Status Indicators
- Green circle: Running
- Red circle: Stopped
- Yellow circle: Starting/Stopping
- Gray circle: Unknown

### Keyboard Shortcuts
- `Ctrl+S`: Start selected
- `Ctrl+X`: Stop selected
- `Ctrl+R`: Restart selected
- `Ctrl+A`: Start all
- `Ctrl+Shift+X`: Stop all
- `F5`: Refresh status

---

## Dependencies

```toml
[project]
name = "gemma-service-manager"
version = "1.0.0"
dependencies = [
    "PySide6>=6.6.0",
]

[project.scripts]
gemma-manager = "service_manager:main"

[project.gui-scripts]
gemma-manager-gui = "service_manager:main"
```

---

## Implementation Order

1. **Basic structure** - Package setup, pyproject.toml
2. **Config** - Service definitions
3. **Process Manager** - QProcess wrapper with signals
4. **Log Panel** - Terminal-like text display
5. **Sidebar** - Service tree with status icons
6. **Main Window** - Assemble components
7. **Toolbar** - Start/Stop actions
8. **Split layout** - 2x2 log panel arrangement
9. **Status bar** - Running service count, ports
10. **Polish** - Icons, stylesheet, keyboard shortcuts

---

## Files to Create

| File | Purpose |
|------|---------|
| `service_manager/pyproject.toml` | Package definition |
| `service_manager/src/service_manager/__init__.py` | Package init |
| `service_manager/src/service_manager/__main__.py` | Entry point |
| `service_manager/src/service_manager/main.py` | App launcher |
| `service_manager/src/service_manager/config.py` | Service configs |
| `service_manager/src/service_manager/ui/__init__.py` | UI package |
| `service_manager/src/service_manager/ui/main_window.py` | Main window |
| `service_manager/src/service_manager/ui/sidebar.py` | Service tree |
| `service_manager/src/service_manager/ui/log_panel.py` | Log display |
| `service_manager/src/service_manager/services/__init__.py` | Services package |
| `service_manager/src/service_manager/services/process_manager.py` | QProcess manager |

---

# Phase 2: Enhanced UI & Configuration System

## Overview

Phase 2 adds:
- Play/pause icons with colors instead of text buttons
- IP:Port display in terminal headers
- Redesigned flat sidebar with status dots
- JSON configuration file for IPs, ports, and settings
- First-time setup wizard
- Settings dialog for runtime configuration
- Distributed deployment support (services on different machines)

---

## 2.1 Play/Pause Icons

Replace text "Start/Stop" buttons with colored icons:

```
Running:  ⏹ (red #f48771) - Click to stop
Stopped:  ▶ (green #4ec9b0) - Click to start
Starting: ⏳ (yellow #dcdcaa) - Disabled
Stopping: ⏳ (yellow #dcdcaa) - Disabled
```

### Terminal Header Layout (New)
```
+------------------------------------------------------------------+
| [Service Name]  [Status Badge]  [IP:Port]     [▶/⏹] [Hide] [Clear]|
+------------------------------------------------------------------+
| Gemma Backend   Running         192.168.0.1:5000   ⏹   Hide  Clear|
+------------------------------------------------------------------+
```

---

## 2.2 Sidebar Redesign

Remove tree indentation. Show flat list with status dots and IP info.

### New Sidebar Layout
```
+---------------------------+
| Services           [⚙]    |  <- Settings button
|---------------------------|
| ● Gemma Backend           |  <- Green dot = running
|   192.168.0.1:5000        |  <- IP:Port below name
|---------------------------|
| ○ Gemma Frontend          |  <- Gray dot = stopped
|   localhost:3000          |
|---------------------------|
| ◐ SUT Discovery           |  <- Half dot = starting
|   192.168.0.100:5001      |
|---------------------------|
| ● Queue Service           |
|   192.168.0.101:9000      |
|---------------------------|
| ○ Preset Manager          |
|   localhost:5002          |
+---------------------------+
```

### Status Dots
- `●` Green (#4ec9b0): Running
- `○` Gray (#808080): Stopped
- `◐` Yellow (#dcdcaa): Starting/Stopping

---

## 2.3 JSON Configuration System

### Config File Location
```
~/.gemma/service_manager_config.json
```

### Config Schema
```json
{
  "version": "1.0",
  "default_host": "localhost",
  "services": {
    "sut-discovery": {
      "host": "192.168.0.100",
      "port": 5001,
      "enabled": true,
      "remote": true
    },
    "queue-service": {
      "host": "192.168.0.101",
      "port": 9000,
      "enabled": true,
      "remote": true
    },
    "gemma-backend": {
      "host": "localhost",
      "port": 5000,
      "enabled": true,
      "remote": false
    },
    "gemma-frontend": {
      "host": "localhost",
      "port": 3000,
      "enabled": true,
      "remote": false
    },
    "preset-manager": {
      "host": "localhost",
      "port": 5002,
      "enabled": true,
      "remote": false,
      "env_vars": {
        "USE_EXTERNAL_DISCOVERY": "true",
        "SUT_DISCOVERY_URL": "http://192.168.0.100:5001"
      }
    },
    "pm-frontend": {
      "host": "localhost",
      "port": 3001,
      "enabled": true,
      "remote": false
    }
  },
  "profiles": {
    "local": {
      "description": "All services on localhost",
      "overrides": {}
    },
    "office": {
      "description": "Distributed office setup",
      "overrides": {
        "sut-discovery": {"host": "192.168.1.50"},
        "queue-service": {"host": "192.168.1.51"}
      }
    }
  },
  "active_profile": "local"
}
```

### Config Fields
- `host`: IP address or hostname where service runs
- `port`: Port number
- `enabled`: Whether to show in UI
- `remote`: If true, service runs on different machine (no start/stop, just monitor)
- `env_vars`: Environment variables for the service
- `profiles`: Named configurations for different environments

---

## 2.4 First-Time Setup Wizard

Shows on first run (when config file doesn't exist).

### Wizard Steps

**Step 1: Welcome**
```
+-------------------------------------------+
|         Gemma Service Manager             |
|                                           |
|  Welcome! Let's configure your services.  |
|                                           |
|  [Quick Setup (localhost)]  [Custom Setup]|
+-------------------------------------------+
```

**Step 2: Service Configuration (if Custom)**
```
+-------------------------------------------+
|  Configure Services                       |
|-------------------------------------------|
|  SUT Discovery                            |
|    Host: [192.168.0.100    ]              |
|    Port: [5001             ]              |
|    [x] Remote (runs on different machine) |
|-------------------------------------------|
|  Queue Service                            |
|    Host: [192.168.0.101    ]              |
|    Port: [9000             ]              |
|    [x] Remote                             |
|-------------------------------------------|
|  ... (more services)                      |
|                                           |
|            [Back]  [Next]                 |
+-------------------------------------------+
```

**Step 3: Confirm**
```
+-------------------------------------------+
|  Configuration Summary                    |
|-------------------------------------------|
|  Local Services:                          |
|    - Gemma Backend (localhost:5000)       |
|    - Gemma Frontend (localhost:3000)      |
|                                           |
|  Remote Services:                         |
|    - SUT Discovery (192.168.0.100:5001)   |
|    - Queue Service (192.168.0.101:9000)   |
|                                           |
|            [Back]  [Finish]               |
+-------------------------------------------+
```

---

## 2.5 Settings Dialog

Accessible via toolbar button or `Ctrl+,`

### Settings Dialog Layout
```
+-------------------------------------------------------+
|  Settings                                    [X]      |
|-------------------------------------------------------|
| [Services] [Profiles] [General]                       |
|-------------------------------------------------------|
|                                                       |
|  Service Configuration                                |
|  +-------------------------------------------------+  |
|  | Service         | Host          | Port | Remote |  |
|  |-----------------|---------------|------|--------|  |
|  | SUT Discovery   | 192.168.0.100 | 5001 | [x]    |  |
|  | Queue Service   | 192.168.0.101 | 9000 | [x]    |  |
|  | Gemma Backend   | localhost     | 5000 | [ ]    |  |
|  | Gemma Frontend  | localhost     | 3000 | [ ]    |  |
|  | Preset Manager  | localhost     | 5002 | [ ]    |  |
|  | PM Frontend     | localhost     | 3001 | [ ]    |  |
|  +-------------------------------------------------+  |
|                                                       |
|  Environment Variables (Preset Manager):              |
|  +----------------------------------+                 |
|  | USE_EXTERNAL_DISCOVERY = true    |                 |
|  | SUT_DISCOVERY_URL = http://...   |                 |
|  +----------------------------------+                 |
|                                                       |
|                        [Cancel]  [Apply]  [Save]      |
+-------------------------------------------------------+
```

### Profile Tab
```
|-------------------------------------------------------|
|  Active Profile: [office        v]                    |
|                                                       |
|  Profiles:                                            |
|  +-------------------------+                          |
|  | local - All localhost   |  [Edit] [Delete]        |
|  | office - Distributed    |  [Edit] [Delete]        |
|  +-------------------------+                          |
|                                                       |
|  [New Profile]                                        |
+-------------------------------------------------------+
```

---

## 2.6 Remote Service Handling

For services marked as `remote: true`:
- **No Start/Stop**: Can't start/stop remote services
- **Status Check**: Periodic HTTP health check to service endpoint
- **Visual Indicator**: Different icon/badge for remote services
- **Connection Status**: Show "Connected" / "Unreachable"

### Remote Status Indicators
```
● Connected (green)
✕ Unreachable (red)
◌ Checking... (gray)
```

---

## Phase 2 Implementation Order

1. **settings.py** - Config manager (read/write JSON)
2. **config.py updates** - Merge defaults with JSON config
3. **setup_wizard.py** - First-time setup dialog
4. **settings_dialog.py** - Settings UI
5. **log_panel.py updates** - IP:Port display, play/stop icons
6. **sidebar.py updates** - Flat list with status dots
7. **main_window.py updates** - Wire settings, profile switcher
8. **process_manager.py updates** - Use dynamic config, remote service handling

---

## Phase 2 Files

| File | Action | Purpose |
|------|--------|---------|
| `settings.py` | Create | JSON config manager class |
| `ui/setup_wizard.py` | Create | First-time setup wizard |
| `ui/settings_dialog.py` | Create | Settings dialog UI |
| `config.py` | Modify | Merge with JSON config |
| `ui/log_panel.py` | Modify | Add IP:Port, play/stop icons |
| `ui/sidebar.py` | Modify | Flat list with status dots |
| `ui/main_window.py` | Modify | Settings menu, profile switcher |
| `services/process_manager.py` | Modify | Dynamic config, remote handling |

---

## Updated Directory Structure

```
D:\Code\Gemma\service_manager\
├── pyproject.toml
├── src/
│   └── service_manager/
│       ├── __init__.py
│       ├── __main__.py
│       ├── main.py
│       ├── config.py             # Updated: merge with JSON
│       ├── settings.py           # NEW: Config manager
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── main_window.py    # Updated: settings menu
│       │   ├── sidebar.py        # Updated: flat list
│       │   ├── log_panel.py      # Updated: icons, IP:Port
│       │   ├── setup_wizard.py   # NEW: First-time setup
│       │   └── settings_dialog.py # NEW: Settings UI
│       └── services/
│           ├── __init__.py
│           └── process_manager.py # Updated: dynamic config
```
