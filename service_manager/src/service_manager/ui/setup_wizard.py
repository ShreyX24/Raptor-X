"""
First-time Setup Wizard
"""

from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QCheckBox, QScrollArea, QWidget,
    QFrame, QPushButton, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ..config import get_services
from ..settings import ServiceSettings, get_settings_manager


class WelcomePage(QWizardPage):
    """Welcome page with quick setup option"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Welcome to Gemma Service Manager")
        self.setSubTitle("Let's configure your services.")

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Welcome text
        welcome_label = QLabel(
            "This wizard will help you set up the service manager.\n\n"
            "You can configure where each service runs - locally or on remote machines.\n\n"
            "Choose an option below to get started:"
        )
        welcome_label.setWordWrap(True)
        layout.addWidget(welcome_label)

        layout.addStretch()

        # Quick setup option
        self.quick_setup_btn = QPushButton("Quick Setup (All on localhost)")
        self.quick_setup_btn.setFixedHeight(40)
        self.quick_setup_btn.clicked.connect(self._quick_setup)
        layout.addWidget(self.quick_setup_btn)

        # Custom setup option
        self.custom_setup_btn = QPushButton("Custom Setup (Configure IPs)")
        self.custom_setup_btn.setFixedHeight(40)
        self.custom_setup_btn.clicked.connect(self._custom_setup)
        layout.addWidget(self.custom_setup_btn)

        layout.addStretch()

        self._is_quick_setup = False

    def _quick_setup(self):
        self._is_quick_setup = True
        self.wizard().next()

    def _custom_setup(self):
        self._is_quick_setup = False
        self.wizard().next()

    def isComplete(self):
        return False  # Force button clicks

    @property
    def is_quick_setup(self):
        return self._is_quick_setup


class ServiceConfigPage(QWizardPage):
    """Page to configure individual services"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Configure Services")
        self.setSubTitle("Set the host and port for each service.")

        self.service_widgets = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for services - takes full height
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        self.services_layout = QVBoxLayout(container)
        self.services_layout.setSpacing(12)
        self.services_layout.setContentsMargins(10, 10, 10, 10)

        # Create config widget for each service
        for config in get_services():
            widget = self._create_service_widget(config)
            self.services_layout.addWidget(widget)

        self.services_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)  # stretch factor 1 to take available space

    def _create_service_widget(self, config):
        """Create config widget for a service"""
        group = QGroupBox(config.display_name)
        form_layout = QFormLayout(group)

        # Host input
        host_edit = QLineEdit("localhost")
        host_edit.setPlaceholderText("e.g., 192.168.1.100")
        form_layout.addRow("Host:", host_edit)

        # Port input
        port_edit = QLineEdit(str(config.port) if config.port else "")
        port_edit.setPlaceholderText("Port number")
        form_layout.addRow("Port:", port_edit)

        # Remote checkbox
        remote_check = QCheckBox("Remote (runs on different machine)")
        remote_check.setToolTip(
            "Check this if the service runs on a different machine.\n"
            "Remote services cannot be started/stopped from this manager."
        )
        form_layout.addRow("", remote_check)

        self.service_widgets[config.name] = {
            "host": host_edit,
            "port": port_edit,
            "remote": remote_check,
            "config": config,
        }

        return group

    def initializePage(self):
        """Called when page is shown"""
        # If quick setup was selected, skip this page
        welcome_page = self.wizard().page(0)
        if hasattr(welcome_page, 'is_quick_setup') and welcome_page.is_quick_setup:
            self.wizard().next()

    def get_settings(self) -> dict:
        """Get configured settings"""
        settings = {}
        for name, widgets in self.service_widgets.items():
            port_text = widgets["port"].text().strip()
            settings[name] = ServiceSettings(
                host=widgets["host"].text().strip() or "localhost",
                port=int(port_text) if port_text.isdigit() else 0,
                enabled=True,
                remote=widgets["remote"].isChecked(),
                env_vars=dict(widgets["config"].env_vars) if widgets["config"].env_vars else {},
            )
        return settings


class SummaryPage(QWizardPage):
    """Summary page showing configuration"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Configuration Summary")
        self.setSubTitle("Review your configuration before saving.")
        self.setCommitPage(True)  # This makes it a commit page with Finish button

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Summary content in a frame
        summary_frame = QFrame()
        summary_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        frame_layout = QVBoxLayout(summary_frame)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setFont(QFont("Consolas", 10))
        self.summary_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.summary_label.setStyleSheet("color: #d4d4d4;")
        frame_layout.addWidget(self.summary_label)

        layout.addWidget(summary_frame)
        layout.addStretch()

    def initializePage(self):
        """Build summary when page is shown"""
        welcome_page = self.wizard().page(0)
        config_page = self.wizard().page(1)

        local_services = []
        remote_services = []

        if hasattr(welcome_page, 'is_quick_setup') and welcome_page.is_quick_setup:
            # Quick setup - all localhost
            for config in get_services():
                port_str = f":{config.port}" if config.port else ""
                local_services.append(f"  - {config.display_name} (localhost{port_str})")
        else:
            # Custom setup
            settings = config_page.get_settings()
            for name, svc_settings in settings.items():
                config = next((c for c in get_services() if c.name == name), None)
                if config:
                    port_str = f":{svc_settings.port}" if svc_settings.port else ""
                    addr = f"{svc_settings.host}{port_str}"
                    if svc_settings.remote:
                        remote_services.append(f"  - {config.display_name} ({addr})")
                    else:
                        local_services.append(f"  - {config.display_name} ({addr})")

        summary = "Local Services:\n"
        summary += "\n".join(local_services) if local_services else "  (none)"
        summary += "\n\nRemote Services:\n"
        summary += "\n".join(remote_services) if remote_services else "  (none)"

        self.summary_label.setText(summary)


class SetupWizard(QWizard):
    """First-time setup wizard"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gemma Service Manager Setup")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(600, 700)
        self.resize(650, 750)

        # Add pages
        self.addPage(WelcomePage(self))
        self.addPage(ServiceConfigPage(self))
        self.addPage(SummaryPage(self))

        # Configure buttons
        self.setButtonText(QWizard.FinishButton, "Finish")
        self.setOption(QWizard.NoBackButtonOnStartPage, True)

    def accept(self):
        """Save configuration when wizard completes"""
        settings_manager = get_settings_manager()
        welcome_page = self.page(0)
        config_page = self.page(1)

        if hasattr(welcome_page, 'is_quick_setup') and welcome_page.is_quick_setup:
            # Quick setup - use defaults
            settings_manager.create_default_config(get_services())
        else:
            # Custom setup - apply wizard settings
            settings_manager.create_default_config(get_services())
            settings_manager.apply_wizard_config(config_page.get_settings())

        settings_manager.save()
        super().accept()
