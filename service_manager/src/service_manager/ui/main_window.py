"""
Main Window - Assembles all components with clean fullscreen layout
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QToolBar, QStatusBar, QLabel, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence

from .log_panel import LogPanel, LogPanelContainer
from .setup_wizard import SetupWizard
from .settings_dialog import SettingsDialog
from .dashboard_panel import DashboardPanel
from .flow_diagram import FlowDiagramContainer
from ..services.process_manager import ProcessManager
from ..config import get_services, apply_settings_to_services
from ..settings import get_settings_manager


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RPX Service Manager")

        # Initialize settings
        self._init_settings()

        self.process_manager = ProcessManager(self)
        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_connections()
        self._init_log_panels()
        self._apply_service_settings()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_status_bar)
        self.status_timer.start(1000)

        # Launch fullscreen/maximized
        self.showMaximized()

    def _init_settings(self):
        """Initialize settings, show wizard if first run"""
        settings = get_settings_manager()

        if settings.is_first_run:
            # Show setup wizard
            wizard = SetupWizard(self)
            if wizard.exec() == SetupWizard.Accepted:
                settings.load()
            else:
                # User cancelled - create default config
                settings.create_default_config(get_services())
                settings.save()
        else:
            settings.load()

        # Apply settings to service configs
        apply_settings_to_services(get_services())

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main content area
        self.content_splitter = QSplitter(Qt.Vertical)

        # Dashboard container (hidden by default)
        self.dashboard_container = QWidget()
        dashboard_layout = QHBoxLayout(self.dashboard_container)
        dashboard_layout.setContentsMargins(4, 4, 4, 4)
        dashboard_layout.setSpacing(4)

        # Flow diagram
        self.flow_diagram = FlowDiagramContainer()
        self.flow_diagram.setMinimumWidth(350)

        # Dashboard panel
        self.dashboard_panel = DashboardPanel()
        self.dashboard_panel.setMinimumWidth(500)

        # Dashboard splitter for flow + stats
        self.dashboard_splitter = QSplitter(Qt.Horizontal)
        self.dashboard_splitter.addWidget(self.flow_diagram)
        self.dashboard_splitter.addWidget(self.dashboard_panel)
        self.dashboard_splitter.setSizes([400, 600])

        dashboard_layout.addWidget(self.dashboard_splitter)
        self.dashboard_container.setVisible(False)  # Hidden by default

        # Log container - fills the entire space
        self.log_container = LogPanelContainer()

        self.content_splitter.addWidget(self.dashboard_container)
        self.content_splitter.addWidget(self.log_container)
        self.content_splitter.setSizes([350, 550])

        # Add content to main layout (no tab bar)
        layout.addWidget(self.content_splitter)

        # Track dashboard visibility state
        self._dashboard_visible = False

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3d3d3d;
                spacing: 4px;
                padding: 2px 4px;
            }
            QToolBar QToolButton {
                background: transparent;
                border: none;
                padding: 4px 8px;
                color: #cccccc;
            }
            QToolBar QToolButton:hover {
                background-color: #3d3d3d;
            }
            QToolBar QToolButton:checked {
                background-color: #094771;
            }
        """)
        self.addToolBar(toolbar)

        self.start_all_action = QAction("Start All", self)
        self.start_all_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.start_all_action.triggered.connect(self._start_all_services)
        toolbar.addAction(self.start_all_action)

        self.stop_all_action = QAction("Stop All", self)
        self.stop_all_action.setShortcut(QKeySequence("Ctrl+Shift+X"))
        self.stop_all_action.triggered.connect(self._stop_all_services)
        toolbar.addAction(self.stop_all_action)

        self.restart_all_action = QAction("Restart All", self)
        self.restart_all_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.restart_all_action.triggered.connect(self._restart_all_services)
        toolbar.addAction(self.restart_all_action)

        toolbar.addSeparator()

        self.clear_logs_action = QAction("Clear All Logs", self)
        self.clear_logs_action.triggered.connect(self._clear_all_logs)
        toolbar.addAction(self.clear_logs_action)

        toolbar.addSeparator()

        self.dashboard_action = QAction("Dashboard", self)
        self.dashboard_action.setShortcut(QKeySequence("Ctrl+D"))
        self.dashboard_action.setCheckable(True)
        self.dashboard_action.setChecked(False)
        self.dashboard_action.triggered.connect(self._toggle_dashboard_view)
        toolbar.addAction(self.dashboard_action)

        toolbar.addSeparator()

        self.settings_action = QAction("Settings", self)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self.settings_action.triggered.connect(self._show_settings)
        toolbar.addAction(self.settings_action)

        toolbar.addSeparator()

        self.update_action = QAction("Check for Updates", self)
        self.update_action.setShortcut(QKeySequence("Ctrl+U"))
        self.update_action.triggered.connect(self._show_update_dialog)
        toolbar.addAction(self.update_action)

        # Add spacer to push SUT Client to the right
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy(), spacer.sizePolicy().verticalPolicy())
        from PySide6.QtWidgets import QSizePolicy
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # SUT Client status indicator in toolbar
        self.sut_client_label = QLabel("SUT Client:")
        self.sut_client_label.setStyleSheet("color: #888; margin-right: 4px;")
        toolbar.addWidget(self.sut_client_label)

        self.sut_client_status = QLabel("\u25CF Disconnected")
        self.sut_client_status.setStyleSheet("color: #808080;")
        toolbar.addWidget(self.sut_client_status)

    def _setup_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.running_label = QLabel("0/0 services running")
        self.ports_label = QLabel("")
        self.status_bar.addWidget(self.status_label)
        self.status_bar.addPermanentWidget(self.ports_label)
        self.status_bar.addPermanentWidget(self.running_label)

    def _setup_connections(self):
        # Process manager signals
        self.process_manager.output_received.connect(self._on_output_received)
        self.process_manager.error_received.connect(self._on_error_received)
        self.process_manager.status_changed.connect(self._on_status_changed)
        self.process_manager.status_changed.connect(self.flow_diagram.update_status)

        # Log container signals
        self.log_container.start_requested.connect(self._start_service)
        self.log_container.stop_requested.connect(self._stop_service)
        self.log_container.restart_requested.connect(self._restart_service)

        # Health check signals - blink indicators on log panels
        self.log_container.health_check_received.connect(self._on_health_check)

    def _init_log_panels(self):
        for config in get_services():
            # Only add panels for enabled services
            if config.enabled:
                self.log_container.add_panel(config.name, config.display_name)

        # Also add panels for OmniParser services
        for name in self.process_manager.get_omniparser_services():
            config = self.process_manager.configs.get(name)
            if config:
                self.log_container.add_panel(config.name, config.display_name)

        self.log_container.arrange_panels()

    def _on_health_check(self, service_name: str, success: bool):
        """Handle health check signal - blink indicator on log panel"""
        panel = self.log_container.get_panel(service_name)
        if panel:
            panel.blink_indicator(success)

    def _on_output_received(self, service_name: str, text: str):
        panel = self.log_container.get_panel(service_name)
        if panel:
            panel.append_output(text)

    def _on_error_received(self, service_name: str, text: str):
        panel = self.log_container.get_panel(service_name)
        if panel:
            panel.append_error(text)

    def _on_status_changed(self, service_name: str, status: str):
        panel = self.log_container.get_panel(service_name)
        if panel:
            panel.set_status(status)

        # Update SUT Client status in toolbar (special handling)
        # Note: SUT Client is remote, status comes from discovery service
        # For now we show the SUT Discovery service status as indicator
        if service_name == "sut-discovery":
            self._update_sut_client_status(status)

        self._update_status_bar()

    def _update_sut_client_status(self, status: str):
        """Update the SUT Client indicator in toolbar"""
        colors = {
            "running": ("#4ec9b0", "Connected"),
            "starting": ("#dcdcaa", "Connecting..."),
            "stopping": ("#dcdcaa", "Disconnecting..."),
            "stopped": ("#808080", "Disconnected"),
            "connected": ("#4ec9b0", "Connected"),
            "unreachable": ("#f48771", "Unreachable"),
        }
        color, text = colors.get(status, ("#808080", "Unknown"))
        self.sut_client_status.setText(f"\u25CF {text}")
        self.sut_client_status.setStyleSheet(f"color: {color};")

    def _start_service(self, service_name: str):
        self.status_label.setText(f"Starting {service_name}...")
        self.process_manager.start_service(service_name)

    def _stop_service(self, service_name: str):
        self.status_label.setText(f"Stopping {service_name}...")
        self.process_manager.stop_service(service_name)

    def _restart_service(self, service_name: str):
        self.status_label.setText(f"Restarting {service_name}...")
        self.process_manager.restart_service(service_name)

    def _start_selected(self):
        # No longer used - services controlled from log panel headers
        pass

    def _stop_selected(self):
        # No longer used - services controlled from log panel headers
        pass

    def _restart_selected(self):
        # No longer used - services controlled from log panel headers
        pass

    def _start_all_services(self):
        self.status_label.setText("Starting all services...")
        self.process_manager.start_all()

    def _stop_all_services(self):
        self.status_label.setText("Stopping all services...")
        self.process_manager.stop_all()

    def _restart_all_services(self):
        self.status_label.setText("Restarting all services...")
        self.process_manager.restart_all()

    def _clear_all_logs(self):
        for panel in self.log_container.panels.values():
            panel.clear_log()

    def _toggle_dashboard_view(self, checked: bool):
        """Toggle dashboard visibility and adjust log panel layout"""
        self._dashboard_visible = checked
        self.dashboard_container.setVisible(checked)

        if checked:
            # Load OmniParser instances into flow diagram
            settings = get_settings_manager()
            omniparser_servers = settings.get_omniparser_servers()
            instances = [{"name": s.name, "url": s.url, "enabled": s.enabled} for s in omniparser_servers]
            self.flow_diagram.set_omniparser_instances(instances)

            # Start dashboard refresh
            self.dashboard_panel.start_refresh()
            # Collapse frontend log panels to header only
            self._collapse_frontend_panels()
        else:
            # Stop dashboard refresh to save resources
            self.dashboard_panel.stop_refresh()
            # Restore frontend panels
            self._expand_frontend_panels()

    def _collapse_frontend_panels(self):
        """Collapse frontend log panels to header only when dashboard is shown"""
        frontend_services = ["rpx-frontend", "pm-frontend"]
        for name in frontend_services:
            panel = self.log_container.get_panel(name)
            if panel:
                # Hide the log text area, keep header visible
                panel.log_text.setVisible(False)
                panel.setMaximumHeight(45)

    def _expand_frontend_panels(self):
        """Restore frontend log panels to full size"""
        frontend_services = ["rpx-frontend", "pm-frontend"]
        for name in frontend_services:
            panel = self.log_container.get_panel(name)
            if panel:
                panel.log_text.setVisible(True)
                panel.setMaximumHeight(16777215)  # Qt default max

    def _apply_service_settings(self):
        """Apply settings to all log panels"""
        for config in get_services():
            # Update log panel
            panel = self.log_container.get_panel(config.name)
            if panel:
                panel.set_host_port(config.host, config.port)
                panel.set_remote(config.remote)

    def _show_settings(self):
        """Show settings dialog"""
        # Capture current OmniParser config before dialog
        settings = get_settings_manager()
        old_omniparser_urls = settings.get_omniparser_urls_env()

        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(lambda: self._on_settings_changed(old_omniparser_urls))
        dialog.exec()

    def _show_update_dialog(self):
        """Show the update dialog"""
        from .update_dialog import UpdateDialog

        settings = get_settings_manager()
        base_dir = settings.get_project_dir()

        if not base_dir:
            QMessageBox.warning(
                self,
                "Configuration Required",
                "Please set the Project Directory in Settings before checking for updates."
            )
            return

        dialog = UpdateDialog(base_dir, self.process_manager, self)
        dialog.exec()

    def _on_settings_changed(self, old_omniparser_urls: str = ""):
        """Handle settings change"""
        # Reload and apply settings
        apply_settings_to_services(get_services())
        self._apply_service_settings()

        # Refresh ProcessManager's cached configs (picks up new working directories, etc.)
        self.process_manager.refresh_service_configs()

        # Update OmniParser instances in process manager
        settings = get_settings_manager()
        instance_count = settings.get_omniparser_instance_count()
        old_omniparser = self.process_manager.get_omniparser_services()

        self.process_manager.register_omniparser_instances(instance_count)

        new_omniparser = self.process_manager.get_omniparser_services()

        # Remove log panels for removed OmniParser services
        for name in old_omniparser:
            if name not in new_omniparser:
                self.log_container.remove_panel(name)

        # Add log panels for new OmniParser services
        for name in new_omniparser:
            if name not in old_omniparser:
                config = self.process_manager.configs.get(name)
                if config:
                    self.log_container.add_panel(config.name, config.display_name)

        # Rearrange panels
        self.log_container.arrange_panels()

        # Check if OmniParser URLs changed - if so, restart queue-service
        new_omniparser_urls = settings.get_omniparser_urls_env()
        if old_omniparser_urls != new_omniparser_urls:
            if self.process_manager.is_running("queue-service"):
                panel = self.log_container.get_panel("queue-service")
                if panel:
                    panel.append_output(f"\n--- OmniParser URLs changed: {new_omniparser_urls or '(none)'} ---\n")
                    panel.append_output("--- Restarting to apply new configuration ---\n")
                self.process_manager.restart_service("queue-service")

        # Update flow diagram if dashboard is visible
        if self._dashboard_visible:
            omniparser_servers = settings.get_omniparser_servers()
            # If local instances are configured, show those instead
            if instance_count > 0:
                instances = [
                    {"name": f"OmniParser {8000 + i}", "url": f"http://localhost:{8000 + i}", "enabled": True}
                    for i in range(instance_count)
                ]
            else:
                instances = [{"name": s.name, "url": s.url, "enabled": s.enabled} for s in omniparser_servers]
            self.flow_diagram.set_omniparser_instances(instances)

    def _update_status_bar(self):
        running = self.process_manager.get_running_count()
        total = self.process_manager.get_total_count()
        self.running_label.setText(f"{running}/{total} services running")
        ports = []
        for config in get_services():
            if self.process_manager.is_running(config.name) and config.port:
                ports.append(f"{config.display_name}: {config.port}")
        if ports:
            self.ports_label.setText(" | ".join(ports[:4]))
        else:
            self.ports_label.setText("")
        if running > 0:
            self.status_label.setText("Services running")
        else:
            self.status_label.setText("Ready")

    def closeEvent(self, event):
        running = self.process_manager.get_running_count()
        if running > 0:
            reply = QMessageBox.question(
                self,
                "Stop Services?",
                f"There are {running} services running. Stop before exiting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.Yes:
                self.process_manager.stop_all()

        # Clean up all resources (background threads, timers, etc.)
        self.process_manager.cleanup()
        event.accept()
