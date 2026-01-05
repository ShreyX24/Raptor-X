"""
Log Panel - Terminal-like log display widget with health check filtering
"""

import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QLabel, QPushButton, QSplitter, QFrame
)
from PySide6.QtCore import Qt, Slot, Signal, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor, QPainter, QBrush, QPen


# Health check patterns to filter out from main logs
# These match the actual log formats from various services
HEALTH_CHECK_PATTERNS = [
    # Uvicorn access logs format: "GET /health HTTP/1.1" 200
    r'"GET\s+[^"]*?/health[^"]*?"',
    r'"GET\s+[^"]*?/probe[^"]*?"',
    r'"GET\s+[^"]*?/api/status[^"]*?"',
    r'"GET\s+[^"]*?/api/health[^"]*?"',
    r'"POST\s+[^"]*?/parse[^"]*?"',  # OmniParser parse endpoint

    # Standard uvicorn log format: 127.0.0.1:58789 - "GET /health HTTP/1.1" 200
    r'- "GET\s+/health',
    r'- "GET\s+/probe',
    r'- "GET\s+/api/status',
    r'- "POST\s+/parse',

    # httpx logs (Queue Service probing OmniParser) - more flexible pattern
    r'httpx.*HTTP Request:.*?/probe',
    r'httpx.*HTTP Request:.*?/parse',
    r'HTTP Request:\s*GET\s+http[^"]*?/probe',
    r'HTTP Request:\s*POST\s+http[^"]*?/parse',

    # Health endpoint in URL (matches various formats)
    r'/health(?:[\s"\'/?]|$)',
    r'/probe/?(?:[\s"\'/?]|$)',
    r'/api/status(?:[\s"\'/?]|$)',
    r'/discovery/status',

    # Health check keywords in log messages
    r'health\s*check',
    r'healthcheck',
    r'liveness.?probe',
    r'readiness.?probe',

    # Vite/webpack dev server noise
    r'__vite_ping',
    r'/@vite/',
    r'@vite/client',
    r'/_next/',
    r'/sockjs-node/',
    r'\bhmr\b',  # Hot module replacement
    r'hot-update',
    r'\[vite\].*connected',
    r'\[vite\].*http proxy error.*?/health',  # Vite proxy errors for health endpoint
]

# Compile patterns for efficiency
HEALTH_CHECK_REGEX = re.compile('|'.join(HEALTH_CHECK_PATTERNS), re.IGNORECASE)


class HealthIndicator(QWidget):
    """Blinking health indicator dot for log panel headers"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)  # Larger size for better visibility
        self._base_color = QColor("#808080")  # Gray = stopped
        self._flash_color = QColor("#ffffff")  # White flash
        self._current_color = self._base_color
        self._status = "stopped"
        self._is_flashing = False
        self._flash_count = 0
        self._flash_success = True

        # Timer for flash effect - blink multiple times
        self._flash_timer = QTimer(self)
        self._flash_timer.timeout.connect(self._flash_step)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw outer glow when flashing (larger, more visible)
        if self._is_flashing and self._flash_count % 2 == 0:
            glow_color = QColor(self._current_color)
            glow_color.setAlpha(150)
            painter.setBrush(QBrush(glow_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 16, 16)

            # Draw the main dot (bright)
            painter.setBrush(QBrush(self._current_color))
            painter.setPen(QPen(self._current_color.lighter(120), 1))
            painter.drawEllipse(3, 3, 10, 10)
        else:
            # Draw normal dot (dimmed when flashing off-phase)
            color = self._base_color if not self._is_flashing else self._base_color.darker(150)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(120), 1))
            painter.drawEllipse(3, 3, 10, 10)

    def set_status(self, status: str):
        """Set status and update base color"""
        self._status = status
        colors = {
            "running": "#4ec9b0",    # Green
            "starting": "#dcdcaa",   # Yellow
            "stopping": "#dcdcaa",   # Yellow
            "stopped": "#808080",    # Gray
            "connected": "#4ec9b0",  # Green
            "unreachable": "#f48771", # Red
        }
        self._base_color = QColor(colors.get(status, "#808080"))
        if not self._is_flashing:
            self._current_color = self._base_color
        self.update()

    def _flash_step(self):
        """Step through flash animation"""
        self._flash_count += 1
        self.update()

        # Stop after 4 steps (2 blinks: bright-dim-bright-dim)
        if self._flash_count >= 4:
            self._flash_timer.stop()
            self._is_flashing = False
            self._current_color = self._base_color
            self.update()

    def blink(self, success: bool = True):
        """Trigger a visible flash/blink - blinks twice for better visibility"""
        if self._status not in ("running", "connected", "starting"):
            return  # Only blink when running/starting

        # Set flash color based on success
        if success:
            self._current_color = QColor("#00ff00")  # Bright green flash
        else:
            self._current_color = QColor("#ff0000")  # Bright red flash

        self._is_flashing = True
        self._flash_count = 0
        self._flash_success = success
        self.update()

        # Start blink animation - 100ms per step, 4 steps total (400ms)
        self._flash_timer.stop()
        self._flash_timer.start(100)


class LogPanel(QWidget):
    """Terminal-like log panel for a single service with health check filtering"""

    start_requested = Signal(str)
    stop_requested = Signal(str)
    restart_requested = Signal(str)
    hide_requested = Signal(str)
    health_check_received = Signal(str, bool)  # service_name, success

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
        self._filter_health_checks = True  # Filter health check logs by default

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

        # Health indicator (blinking dot)
        self.health_indicator = HealthIndicator()

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

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedWidth(50)
        self.clear_btn.setStyleSheet(btn_style)
        self.clear_btn.clicked.connect(self.clear_log)

        # Add widgets to header (health indicator first, then title)
        header_layout.addWidget(self.health_indicator)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.host_port_label)
        header_layout.addStretch()
        header_layout.addWidget(self.start_stop_btn)
        header_layout.addWidget(self.restart_btn)
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

    def _is_health_check_log(self, text: str) -> bool:
        """Check if text is a health check log line"""
        return bool(HEALTH_CHECK_REGEX.search(text))

    def _is_success_response(self, text: str) -> bool:
        """Check if health check response indicates success (2xx status)"""
        # Look for HTTP 2xx status codes
        if re.search(r'\b2\d{2}\b', text):
            return True
        # Look for "ok", "healthy", "success" keywords
        if re.search(r'\b(ok|healthy|success|passed)\b', text, re.IGNORECASE):
            return True
        return False

    def _is_error_response(self, text: str) -> bool:
        """Check if health check response indicates error (4xx, 5xx or error keywords)"""
        # Look for HTTP 4xx/5xx status codes
        if re.search(r'\b[45]\d{2}\b', text):
            return True
        # Look for error keywords
        if re.search(r'\b(error|fail|failed|timeout|refused|unavailable|unreachable)\b', text, re.IGNORECASE):
            return True
        return False

    @Slot(str)
    def append_output(self, text: str):
        """Append text to log, filtering successful health checks only (show errors)"""
        clean_text = self._strip_ansi(text)

        # Process each line separately to filter health checks
        lines = clean_text.split('\n')
        filtered_lines = []

        for line in lines:
            if self._filter_health_checks and line.strip() and self._is_health_check_log(line):
                # This line is a health check
                is_success = self._is_success_response(line)
                is_error = self._is_error_response(line)

                # Blink indicator directly (green for success, red for error)
                self.blink_indicator(is_success and not is_error)
                self.health_check_received.emit(self.service_name, is_success and not is_error)

                # Only filter out successful health checks - show errors
                if is_error or not is_success:
                    filtered_lines.append(line)
                # Successful health checks are filtered (not added)
            else:
                filtered_lines.append(line)

        # If we have remaining lines to show, display them
        remaining_text = '\n'.join(filtered_lines)
        if remaining_text.strip():
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)

            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#d4d4d4"))  # Light gray for normal output
            cursor.setCharFormat(fmt)
            cursor.insertText(remaining_text)

            self.log_text.moveCursor(QTextCursor.End)

    def _is_error_line(self, line: str) -> bool:
        """Check if a line is an actual error (not just stderr INFO logs)"""
        # Python logging writes everything to stderr, so we need to detect actual errors
        error_patterns = [
            r'\bERROR\b',
            r'\bCRITICAL\b',
            r'\bFATAL\b',
            r'\bException\b',
            r'\bTraceback\b',
            r'\bError[:\[]',  # Error: or Error[
            r'\bFailed\b',
            r'\bfailed\b',
            r'raise \w+Error',
            r'^\s*File ".*", line \d+',  # Python traceback
            r'^\s*at\s+\w+',  # Node.js stack trace: "at functionName"
            # Python errors
            r'ConnectionRefusedError',
            r'ConnectionResetError',
            r'TimeoutError',
            r'OSError',
            r'RuntimeError',
            r'ValueError',
            r'TypeError',
            r'KeyError',
            r'AttributeError',
            # Node.js errors
            r'AggregateError',
            r'ECONNREFUSED',
            r'ENOTFOUND',
            r'ETIMEDOUT',
            r'ECONNRESET',
            r'UnhandledPromiseRejection',
            # HTTP errors
            r'\b[45]\d{2}\s+\w+',  # 404 Not Found, 500 Internal Server Error
        ]
        for pattern in error_patterns:
            if re.search(pattern, line):
                return True
        return False

    @Slot(str)
    def append_error(self, text: str):
        """Append stderr text to log - only color actual errors red"""
        clean_text = self._strip_ansi(text)

        # Process each line separately
        lines = clean_text.split('\n')
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)

        for line in lines:
            # Check for health checks (only if filtering is enabled)
            if self._filter_health_checks and line.strip() and self._is_health_check_log(line):
                is_success = self._is_success_response(line)
                is_error = self._is_error_response(line)
                self.blink_indicator(is_success and not is_error)
                self.health_check_received.emit(self.service_name, is_success and not is_error)

                # Only show health check errors - filter out successful ones
                if is_error or not is_success:
                    fmt = QTextCharFormat()
                    fmt.setForeground(QColor("#f48771"))  # Red for errors
                    cursor.setCharFormat(fmt)
                    cursor.insertText(line + '\n')
                # Successful health checks are filtered (not shown)
            elif line.strip():
                # Determine if this line is an actual error
                fmt = QTextCharFormat()
                if self._is_error_line(line):
                    fmt.setForeground(QColor("#f48771"))  # Red for actual errors
                else:
                    fmt.setForeground(QColor("#d4d4d4"))  # Light gray for normal stderr
                cursor.setCharFormat(fmt)
                cursor.insertText(line + '\n')
            elif line == '':
                # Preserve empty lines
                cursor.insertText('\n')

        self.log_text.moveCursor(QTextCursor.End)

    @Slot(str)
    def set_status(self, status: str):
        """Update status label, button icons, and health indicator"""
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

        # Update health indicator
        self.health_indicator.set_status(status)

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

    def set_filter_health_checks(self, enabled: bool):
        """Enable or disable health check log filtering"""
        self._filter_health_checks = enabled

    def blink_indicator(self, success: bool = True):
        """Trigger the health indicator to blink"""
        self.health_indicator.blink(success)

    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes"""
        ansi_escape = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)


class LogPanelContainer(QWidget):
    """Container for multiple log panels in a grid layout"""

    start_requested = Signal(str)
    stop_requested = Signal(str)
    restart_requested = Signal(str)
    health_check_received = Signal(str, bool)  # Forward health check signals

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
        panel.health_check_received.connect(self.health_check_received.emit)
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
