"""
Log Panel - Terminal-like log display widget
"""

import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QLabel, QPushButton, QSplitter, QFrame
)
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor


class LogPanel(QWidget):
    """Terminal-like log panel for a single service"""

    start_requested = Signal(str)
    stop_requested = Signal(str)
    restart_requested = Signal(str)
    hide_requested = Signal(str)

    # Icon characters
    ICON_PLAY = "\u25B6"   # Play triangle
    ICON_STOP = "\u25A0"   # Stop square
    ICON_WAIT = "\u23F3"   # Hourglass
    ICON_RESTART = "\u21BB"  # Circular arrow (restart)

    def __init__(self, service_name: str, display_name: str, parent=None):
        super().__init__(parent)
        self.service_name = service_name
        self.display_name = display_name
        self._is_running = False
        self._is_remote = False
        self._host = "localhost"
        self._port = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3d3d3d;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)

        self.title_label = QLabel(self.display_name)
        self.title_label.setStyleSheet("font-weight: bold; color: #ffffff;")

        self.status_label = QLabel("Stopped")
        self.status_label.setStyleSheet("color: #808080;")

        self.host_port_label = QLabel("")
        self.host_port_label.setStyleSheet("color: #888888; font-size: 9pt;")

        btn_style = """
            QPushButton {
                background-color: transparent;
                border: 1px solid #555;
                padding: 2px 6px;
                font-size: 10pt;
                min-width: 28px;
            }
            QPushButton:hover { background-color: #404040; }
            QPushButton:disabled { color: #555; border-color: #444; }
        """

        # Play/Stop button with icon
        self.start_stop_btn = QPushButton(self.ICON_PLAY)
        self.start_stop_btn.setFixedWidth(32)
        self.start_stop_btn.setStyleSheet(btn_style + "QPushButton { color: #4ec9b0; }")
        self.start_stop_btn.clicked.connect(self._on_start_stop_clicked)
        self.start_stop_btn.setToolTip("Start service")

        # Restart button
        self.restart_btn = QPushButton(self.ICON_RESTART)
        self.restart_btn.setFixedWidth(32)
        self.restart_btn.setStyleSheet(btn_style + "QPushButton { color: #dcdcaa; }")
        self.restart_btn.clicked.connect(lambda: self.restart_requested.emit(self.service_name))
        self.restart_btn.setToolTip("Restart service")

        self.hide_btn = QPushButton("Hide")
        self.hide_btn.setFixedWidth(50)
        self.hide_btn.setStyleSheet(btn_style)
        self.hide_btn.clicked.connect(lambda: self.hide_requested.emit(self.service_name))

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedWidth(50)
        self.clear_btn.setStyleSheet(btn_style)
        self.clear_btn.clicked.connect(self.clear_log)

        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.host_port_label)
        header_layout.addStretch()
        header_layout.addWidget(self.start_stop_btn)
        header_layout.addWidget(self.restart_btn)
        header_layout.addWidget(self.hide_btn)
        header_layout.addWidget(self.clear_btn)

        # Log text area
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMaximumBlockCount(5000)
        self.log_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                selection-background-color: #264f78;
            }
        """)

        layout.addWidget(header)
        layout.addWidget(self.log_text)

    def _on_start_stop_clicked(self):
        if self._is_running:
            self.stop_requested.emit(self.service_name)
        else:
            self.start_requested.emit(self.service_name)

    @Slot(str)
    def append_output(self, text: str):
        """Append text to log"""
        clean_text = self._strip_ansi(text)
        self.log_text.moveCursor(QTextCursor.End)
        self.log_text.insertPlainText(clean_text)
        self.log_text.moveCursor(QTextCursor.End)

    @Slot(str)
    def append_error(self, text: str):
        """Append error text (in red) to log"""
        clean_text = self._strip_ansi(text)
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#f48771"))
        cursor.setCharFormat(fmt)
        cursor.insertText(clean_text)

        self.log_text.moveCursor(QTextCursor.End)

    @Slot(str)
    def set_status(self, status: str):
        """Update status label and button with icons"""
        colors = {
            "running": "#4ec9b0",
            "starting": "#dcdcaa",
            "stopping": "#dcdcaa",
            "stopped": "#808080",
            "connected": "#4ec9b0",
            "unreachable": "#f48771",
        }
        color = colors.get(status, "#808080")
        self.status_label.setText(status.capitalize())
        self.status_label.setStyleSheet(f"color: {color};")

        # Update button icon and color based on status
        self._is_running = status in ("running", "starting", "connected")

        btn_base = """
            QPushButton {
                background-color: transparent;
                border: 1px solid #555;
                padding: 2px 6px;
                font-size: 10pt;
                min-width: 28px;
            }
            QPushButton:hover { background-color: #404040; }
            QPushButton:disabled { color: #555; border-color: #444; }
        """

        if self._is_remote:
            # Remote services can't be started/stopped
            self.start_stop_btn.setEnabled(False)
            self.start_stop_btn.setText("-")
            self.start_stop_btn.setToolTip("Remote service (cannot control)")
            self.restart_btn.setEnabled(False)
        elif status == "running":
            self.start_stop_btn.setText(self.ICON_STOP)
            self.start_stop_btn.setStyleSheet(btn_base + "QPushButton { color: #f48771; }")
            self.start_stop_btn.setToolTip("Stop service")
            self.start_stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(True)
        elif status == "stopped":
            self.start_stop_btn.setText(self.ICON_PLAY)
            self.start_stop_btn.setStyleSheet(btn_base + "QPushButton { color: #4ec9b0; }")
            self.start_stop_btn.setToolTip("Start service")
            self.start_stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(False)
        elif status == "starting":
            self.start_stop_btn.setText(self.ICON_STOP)
            self.start_stop_btn.setStyleSheet(btn_base + "QPushButton { color: #f48771; }")
            self.start_stop_btn.setToolTip("Stop (abort startup)")
            self.start_stop_btn.setEnabled(True)  # Allow stopping during startup
            self.restart_btn.setEnabled(False)
        elif status == "stopping":
            self.start_stop_btn.setText(self.ICON_WAIT)
            self.start_stop_btn.setStyleSheet(btn_base + "QPushButton { color: #dcdcaa; }")
            self.start_stop_btn.setToolTip("Stopping...")
            self.start_stop_btn.setEnabled(False)  # Can't stop while already stopping
            self.restart_btn.setEnabled(False)

    def set_host_port(self, host: str, port: int = None):
        """Set the host and port for display"""
        self._host = host
        self._port = port
        if port:
            self.host_port_label.setText(f"{host}:{port}")
        else:
            self.host_port_label.setText(host)

    def set_remote(self, is_remote: bool):
        """Set whether this is a remote service"""
        self._is_remote = is_remote
        if is_remote:
            self.start_stop_btn.setEnabled(False)
            self.start_stop_btn.setText("-")
            self.start_stop_btn.setToolTip("Remote service (cannot control)")

    @property
    def is_remote(self) -> bool:
        return self._is_remote

    def clear_log(self):
        """Clear log contents"""
        self.log_text.clear()

    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes"""
        ansi_escape = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)


class LogPanelContainer(QWidget):
    """Container for multiple log panels in a grid layout"""

    start_requested = Signal(str)
    stop_requested = Signal(str)
    restart_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.panels: dict = {}
        self.row_splitters = []
        self.hidden_panels = set()

        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Main splitter for rows
        self.main_splitter = QSplitter(Qt.Vertical)
        self.layout.addWidget(self.main_splitter)

    def add_panel(self, service_name: str, display_name: str) -> "LogPanel":
        """Add a new log panel (call arrange_panels after all are added)"""
        panel = LogPanel(service_name, display_name, self)
        panel.start_requested.connect(self.start_requested.emit)
        panel.stop_requested.connect(self.stop_requested.emit)
        panel.restart_requested.connect(self.restart_requested.emit)
        panel.hide_requested.connect(self._hide_panel)
        self.panels[service_name] = panel
        return panel

    def _hide_panel(self, service_name: str):
        """Hide a panel"""
        if service_name in self.panels:
            self.hidden_panels.add(service_name)
            self.panels[service_name].setVisible(False)

    def show_panel(self, service_name: str):
        """Show a hidden panel"""
        if service_name in self.hidden_panels:
            self.hidden_panels.discard(service_name)
            self.panels[service_name].setVisible(True)

    def arrange_panels(self):
        """Arrange all panels in 2-column grid - call after adding all panels"""
        panels = list(self.panels.values())
        if not panels:
            return

        # Clear existing row splitters
        for splitter in self.row_splitters:
            # Remove widgets from splitter (but don't delete - they're in self.panels)
            while splitter.count() > 0:
                widget = splitter.widget(0)
                if widget:
                    widget.setParent(None)
            splitter.setParent(None)
            splitter.deleteLater()
        self.row_splitters.clear()

        # Arrange in 2-column grid
        for i in range(0, len(panels), 2):
            row_splitter = QSplitter(Qt.Horizontal)
            row_splitter.setChildrenCollapsible(False)
            row_splitter.addWidget(panels[i])

            if i + 1 < len(panels):
                row_splitter.addWidget(panels[i + 1])
                # Equal horizontal split
                row_splitter.setSizes([500, 500])
            else:
                row_splitter.setSizes([1000])

            self.row_splitters.append(row_splitter)
            self.main_splitter.addWidget(row_splitter)

        # Set equal heights for all rows
        self.main_splitter.setChildrenCollapsible(False)
        row_count = len(self.row_splitters)
        if row_count > 0:
            equal_height = 300  # Base height per row
            self.main_splitter.setSizes([equal_height] * row_count)

    def get_panel(self, service_name: str) -> "LogPanel":
        """Get panel by service name"""
        return self.panels.get(service_name)

    def remove_panel(self, service_name: str):
        """Remove a panel"""
        if service_name in self.panels:
            panel = self.panels.pop(service_name)
            panel.setParent(None)
            panel.deleteLater()

    def show_single_panel(self, service_name: str):
        """Show only one panel maximized"""
        for name, panel in self.panels.items():
            panel.setVisible(name == service_name)

    def show_all_panels(self):
        """Show all panels except hidden ones"""
        for name, panel in self.panels.items():
            if name not in self.hidden_panels:
                panel.setVisible(True)
