"""
Sidebar - Flat service list with status dots and IP:Port display
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QMenu, QLabel, QPushButton, QFrame, QStyledItemDelegate
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QBrush, QIcon, QPixmap, QPainter, QFont

from ..config import SERVICES, ServiceConfig


class ServiceItemDelegate(QStyledItemDelegate):
    """Custom delegate for service items with two-line display"""

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 50)


class ServiceSidebar(QWidget):
    """Flat list showing services with status dots and IP:Port"""

    service_selected = Signal(str)
    service_start_requested = Signal(str)
    service_stop_requested = Signal(str)
    service_restart_requested = Signal(str)
    settings_requested = Signal()

    # Status dot characters
    DOT_FILLED = "\u25CF"    # Filled circle
    DOT_EMPTY = "\u25CB"     # Empty circle
    DOT_HALF = "\u25D0"      # Half circle

    def __init__(self, parent=None):
        super().__init__(parent)

        self.service_items = {}
        self.service_statuses = {}
        self.service_host_ports = {}
        self._dynamic_configs = {}  # Store configs for dynamically added services

        self._setup_ui()
        self._populate_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with title and settings button
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3d3d3d;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 8, 8)

        title = QLabel("Services")
        title.setStyleSheet("font-weight: bold; font-size: 11pt; color: #fff;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.settings_btn = QPushButton("\u2699")  # Gear icon
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14pt;
                color: #888;
            }
            QPushButton:hover {
                color: #fff;
            }
        """)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        header_layout.addWidget(self.settings_btn)

        layout.addWidget(header)

        # Service list
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #3d3d3d;
            }
            QListWidget::item:selected {
                background-color: #37373d;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
            }
        """)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout.addWidget(self.list_widget)

    def _populate_list(self):
        """Populate list with services"""
        for config in SERVICES:
            self._add_service_item(config)

    def _add_service_item(self, config):
        """Add a service item to the list"""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, config.name)

        # Initialize with default values
        self.service_statuses[config.name] = "stopped"
        host_port = f"{config.host}:{config.port}" if config.port else config.host
        self.service_host_ports[config.name] = host_port

        self._update_item_text(item, config.name)

        self.list_widget.addItem(item)
        self.service_items[config.name] = item

    def _get_config(self, service_name: str) -> ServiceConfig:
        """Get config for a service (static or dynamic)"""
        # First check static SERVICES
        config = next((c for c in SERVICES if c.name == service_name), None)
        if config:
            return config
        # Then check dynamic configs
        return self._dynamic_configs.get(service_name)

    def _update_item_text(self, item: QListWidgetItem, service_name: str):
        """Update item text with status dot and host:port"""
        config = self._get_config(service_name)
        if not config:
            return

        status = self.service_statuses.get(service_name, "stopped")
        host_port = self.service_host_ports.get(service_name, "")

        # Get status dot and color
        dot, color = self._get_status_dot(status)

        # Build display text
        text = f"{dot} {config.display_name}\n   {host_port}"
        item.setText(text)

        # Set text color based on status
        item.setForeground(QBrush(QColor(color)))

    def _get_status_dot(self, status: str) -> tuple:
        """Get status dot character and color"""
        dots = {
            "running": (self.DOT_FILLED, "#4ec9b0"),
            "starting": (self.DOT_HALF, "#dcdcaa"),
            "stopping": (self.DOT_HALF, "#dcdcaa"),
            "stopped": (self.DOT_EMPTY, "#808080"),
            "connected": (self.DOT_FILLED, "#4ec9b0"),
            "unreachable": (self.DOT_FILLED, "#f48771"),
        }
        return dots.get(status, (self.DOT_EMPTY, "#808080"))

    def update_status(self, service_name: str, status: str):
        """Update status for a service"""
        self.service_statuses[service_name] = status
        item = self.service_items.get(service_name)
        if item:
            self._update_item_text(item, service_name)

    def update_host_port(self, service_name: str, host: str, port: int = None):
        """Update host:port display for a service"""
        if port:
            self.service_host_ports[service_name] = f"{host}:{port}"
        else:
            self.service_host_ports[service_name] = host

        item = self.service_items.get(service_name)
        if item:
            self._update_item_text(item, service_name)

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle item click"""
        service_name = item.data(Qt.UserRole)
        if service_name:
            self.service_selected.emit(service_name)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double click - toggle service"""
        service_name = item.data(Qt.UserRole)
        if service_name:
            status = self.service_statuses.get(service_name, "stopped")
            if status in ("running", "starting"):
                self.service_stop_requested.emit(service_name)
            else:
                self.service_start_requested.emit(service_name)

    def _show_context_menu(self, position):
        """Show context menu for service"""
        item = self.list_widget.itemAt(position)
        if not item:
            return

        service_name = item.data(Qt.UserRole)
        if not service_name:
            return

        # Check if service is remote
        config = self._get_config(service_name)
        is_remote = config.remote if config else False

        menu = QMenu(self)

        if not is_remote:
            start_action = menu.addAction("Start")
            stop_action = menu.addAction("Stop")
            restart_action = menu.addAction("Restart")

            action = menu.exec_(self.list_widget.mapToGlobal(position))

            if action == start_action:
                self.service_start_requested.emit(service_name)
            elif action == stop_action:
                self.service_stop_requested.emit(service_name)
            elif action == restart_action:
                self.service_restart_requested.emit(service_name)
        else:
            info_action = menu.addAction("Remote service (cannot control)")
            info_action.setEnabled(False)
            menu.exec_(self.list_widget.mapToGlobal(position))

    def get_selected_service(self) -> str:
        """Get currently selected service name"""
        items = self.list_widget.selectedItems()
        if items:
            return items[0].data(Qt.UserRole)
        return None

    def refresh_all(self):
        """Refresh all items"""
        for name, item in self.service_items.items():
            self._update_item_text(item, name)

    def add_dynamic_service(self, config: ServiceConfig):
        """Add a dynamically created service to the sidebar"""
        if config.name in self.service_items:
            return  # Already exists

        self._dynamic_configs[config.name] = config
        self._add_service_item(config)

    def remove_dynamic_service(self, service_name: str):
        """Remove a dynamically created service from the sidebar"""
        if service_name not in self.service_items:
            return

        # Remove from list widget
        item = self.service_items.pop(service_name)
        row = self.list_widget.row(item)
        if row >= 0:
            self.list_widget.takeItem(row)

        # Clean up data
        self._dynamic_configs.pop(service_name, None)
        self.service_statuses.pop(service_name, None)
        self.service_host_ports.pop(service_name, None)
