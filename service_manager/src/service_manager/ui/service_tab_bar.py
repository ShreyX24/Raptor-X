"""
Service Tab Bar - Horizontal navbar with service tabs and health indicators
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QColor, QPainter, QBrush, QPen

from ..config import get_services, ServiceConfig


class HealthIndicator(QWidget):
    """Blinking health indicator dot"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor("#808080")  # Gray = stopped
        self._opacity = 1.0
        self._status = "stopped"
        self._blink_phase = 0  # 0 = not blinking, 1 = fading out, 2 = fading in

        # Animation for blinking
        self._blink_animation = QPropertyAnimation(self, b"opacity")
        self._blink_animation.setDuration(200)
        self._blink_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self._blink_animation.finished.connect(self._on_animation_finished)

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, value):
        self._opacity = value
        self.update()

    opacity = Property(float, get_opacity, set_opacity)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw the dot with current opacity
        color = QColor(self._color)
        color.setAlphaF(self._opacity)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(120), 1))
        painter.drawEllipse(1, 1, 10, 10)

    def set_status(self, status: str):
        """Set status and update color"""
        self._status = status
        colors = {
            "running": "#4ec9b0",    # Green
            "starting": "#dcdcaa",   # Yellow
            "stopping": "#dcdcaa",   # Yellow
            "stopped": "#808080",    # Gray
            "connected": "#4ec9b0",  # Green
            "unreachable": "#f48771", # Red
        }
        self._color = QColor(colors.get(status, "#808080"))
        self.update()

    def _on_animation_finished(self):
        """Handle animation phase transitions"""
        if self._blink_phase == 1:
            # Fade out complete, now fade back in
            self._blink_phase = 2
            self._blink_animation.setStartValue(0.3)
            self._blink_animation.setEndValue(1.0)
            self._blink_animation.start()
        else:
            # Fade in complete, done blinking
            self._blink_phase = 0

    def blink(self, success: bool = True):
        """Trigger a blink animation"""
        if self._status not in ("running", "connected", "starting"):
            return  # Only blink when running/starting

        # Set color based on success
        if success:
            self._color = QColor("#4ec9b0")  # Green
        else:
            self._color = QColor("#f48771")  # Red

        # Start fade out phase
        self._blink_animation.stop()
        self._blink_phase = 1
        self._blink_animation.setStartValue(1.0)
        self._blink_animation.setEndValue(0.3)
        self._blink_animation.start()


class ServiceTab(QFrame):
    """Individual service tab with indicator and controls"""

    clicked = Signal(str)
    start_requested = Signal(str)
    stop_requested = Signal(str)
    restart_requested = Signal(str)

    # Icon characters
    ICON_PLAY = "\u25B6"   # Play triangle
    ICON_STOP = "\u25A0"   # Stop square
    ICON_RESTART = "\u21BB"  # Circular arrow

    def __init__(self, service_name: str, display_name: str, port: int = None, parent=None):
        super().__init__(parent)
        self.service_name = service_name
        self.display_name = display_name
        self.port = port
        self._is_selected = False
        self._is_running = False
        self._is_remote = False

        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Health indicator
        self.indicator = HealthIndicator()
        layout.addWidget(self.indicator)

        # Service name (short version)
        self.name_label = QLabel(self._get_short_name())
        self.name_label.setStyleSheet("font-weight: bold; font-size: 9pt;")
        self.name_label.setToolTip(f"{self.display_name}" + (f" (:{self.port})" if self.port else ""))
        layout.addWidget(self.name_label)

        # Port label (small)
        if self.port:
            self.port_label = QLabel(f":{self.port}")
            self.port_label.setStyleSheet("color: #888; font-size: 8pt;")
            layout.addWidget(self.port_label)

        layout.addStretch()

        # Control buttons (compact)
        btn_style = """
            QPushButton {
                background: transparent;
                border: none;
                font-size: 10pt;
                padding: 2px;
                min-width: 20px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.1); border-radius: 3px; }
            QPushButton:disabled { color: #555; }
        """

        self.start_stop_btn = QPushButton(self.ICON_PLAY)
        self.start_stop_btn.setStyleSheet(btn_style + "QPushButton { color: #4ec9b0; }")
        self.start_stop_btn.setToolTip("Start")
        self.start_stop_btn.clicked.connect(self._on_start_stop)
        layout.addWidget(self.start_stop_btn)

        self.restart_btn = QPushButton(self.ICON_RESTART)
        self.restart_btn.setStyleSheet(btn_style + "QPushButton { color: #dcdcaa; }")
        self.restart_btn.setToolTip("Restart")
        self.restart_btn.setEnabled(False)
        self.restart_btn.clicked.connect(lambda: self.restart_requested.emit(self.service_name))
        layout.addWidget(self.restart_btn)

    def _get_short_name(self) -> str:
        """Get shortened service name for tab"""
        short_names = {
            "sut-discovery": "SUT",
            "queue-service": "Queue",
            "gemma-backend": "Gemma",
            "gemma-frontend": "Frontend",
            "preset-manager": "Presets",
            "pm-frontend": "PM-UI",
        }
        if self.service_name in short_names:
            return short_names[self.service_name]
        if self.service_name.startswith("omniparser-"):
            port = self.service_name.split("-")[-1]
            return f"Omni-{port}"
        return self.display_name[:8]

    def _update_style(self):
        """Update tab style based on state"""
        if self._is_selected:
            bg = "#37373d"
            border = "border-bottom: 2px solid #007acc;"
        else:
            bg = "#2d2d2d"
            border = "border-bottom: 2px solid transparent;"

        self.setStyleSheet(f"""
            ServiceTab {{
                background-color: {bg};
                {border}
            }}
            ServiceTab:hover {{
                background-color: #3c3c3c;
            }}
        """)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._update_style()

    def set_status(self, status: str):
        """Update status and controls"""
        self.indicator.set_status(status)
        self._is_running = status in ("running", "starting", "connected")

        if self._is_remote:
            self.start_stop_btn.setEnabled(False)
            self.start_stop_btn.setText("-")
            self.restart_btn.setEnabled(False)
        elif status == "running":
            self.start_stop_btn.setText(self.ICON_STOP)
            self.start_stop_btn.setStyleSheet(
                self.start_stop_btn.styleSheet().replace("color: #4ec9b0", "color: #f48771")
            )
            self.start_stop_btn.setToolTip("Stop")
            self.start_stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(True)
        elif status == "stopped":
            self.start_stop_btn.setText(self.ICON_PLAY)
            self.start_stop_btn.setStyleSheet(
                self.start_stop_btn.styleSheet().replace("color: #f48771", "color: #4ec9b0")
            )
            self.start_stop_btn.setToolTip("Start")
            self.start_stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(False)
        elif status == "starting":
            self.start_stop_btn.setText(self.ICON_STOP)
            self.start_stop_btn.setToolTip("Stop (abort)")
            self.start_stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(False)
        elif status == "stopping":
            self.start_stop_btn.setEnabled(False)
            self.restart_btn.setEnabled(False)

    def set_remote(self, is_remote: bool):
        self._is_remote = is_remote
        if is_remote:
            self.start_stop_btn.setEnabled(False)
            self.restart_btn.setEnabled(False)

    def blink_indicator(self, success: bool = True):
        """Trigger health indicator blink"""
        self.indicator.blink(success)

    def _on_start_stop(self):
        if self._is_running:
            self.stop_requested.emit(self.service_name)
        else:
            self.start_requested.emit(self.service_name)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.service_name)
        super().mousePressEvent(event)


class ServiceTabBar(QWidget):
    """Horizontal scrollable service tab bar"""

    service_selected = Signal(str)
    service_start_requested = Signal(str)
    service_stop_requested = Signal(str)
    service_restart_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs: dict[str, ServiceTab] = {}
        self._selected_service = None
        self._dynamic_configs = {}

        self._setup_ui()
        self._populate_tabs()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Container frame with dark background
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-bottom: 1px solid #3d3d3d;
            }
        """)
        container.setFixedHeight(44)

        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(4, 2, 4, 0)
        container_layout.setSpacing(2)

        # Scroll area for tabs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                height: 6px;
                background: #1e1e1e;
            }
            QScrollBar::handle:horizontal {
                background: #555;
                border-radius: 3px;
                min-width: 20px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)

        # Tab container widget
        self.tab_container = QWidget()
        self.tab_layout = QHBoxLayout(self.tab_container)
        self.tab_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_layout.setSpacing(2)
        self.tab_layout.addStretch()

        scroll.setWidget(self.tab_container)
        container_layout.addWidget(scroll)

        layout.addWidget(container)

    def _populate_tabs(self):
        """Add tabs for all services"""
        for config in get_services():
            if config.enabled:
                self._add_tab(config)

    def _add_tab(self, config: ServiceConfig):
        """Add a service tab"""
        tab = ServiceTab(config.name, config.display_name, config.port)
        tab.set_remote(config.remote)
        tab.clicked.connect(self._on_tab_clicked)
        tab.start_requested.connect(self.service_start_requested.emit)
        tab.stop_requested.connect(self.service_stop_requested.emit)
        tab.restart_requested.connect(self.service_restart_requested.emit)

        # Insert before the stretch
        self.tab_layout.insertWidget(self.tab_layout.count() - 1, tab)
        self.tabs[config.name] = tab

    def _on_tab_clicked(self, service_name: str):
        """Handle tab click - select/deselect"""
        if self._selected_service == service_name:
            # Deselect
            self.tabs[service_name].set_selected(False)
            self._selected_service = None
        else:
            # Select new, deselect old
            if self._selected_service and self._selected_service in self.tabs:
                self.tabs[self._selected_service].set_selected(False)
            self.tabs[service_name].set_selected(True)
            self._selected_service = service_name

        self.service_selected.emit(service_name)

    def update_status(self, service_name: str, status: str):
        """Update service status"""
        if service_name in self.tabs:
            self.tabs[service_name].set_status(status)

    def blink_indicator(self, service_name: str, success: bool = True):
        """Trigger health indicator blink for a service"""
        if service_name in self.tabs:
            self.tabs[service_name].blink_indicator(success)

    def add_dynamic_service(self, config: ServiceConfig):
        """Add a dynamically created service tab"""
        if config.name in self.tabs:
            return
        self._dynamic_configs[config.name] = config
        self._add_tab(config)

    def remove_dynamic_service(self, service_name: str):
        """Remove a dynamic service tab"""
        if service_name not in self.tabs:
            return

        tab = self.tabs.pop(service_name)
        self.tab_layout.removeWidget(tab)
        tab.deleteLater()
        self._dynamic_configs.pop(service_name, None)

    def get_selected_service(self) -> str:
        """Get currently selected service"""
        return self._selected_service

    def refresh_all(self):
        """Refresh all tabs"""
        # Re-apply any dynamic config changes
        pass
