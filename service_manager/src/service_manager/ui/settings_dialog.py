"""
Settings Dialog - Runtime configuration UI
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QLineEdit, QCheckBox, QPushButton, QComboBox,
    QGroupBox, QFormLayout, QListWidget, QListWidgetItem,
    QMessageBox, QInputDialog, QTextEdit, QSpinBox, QFrame,
    QFileDialog, QProgressBar
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, Signal, QProcess

from ..config import get_services
from ..settings import ServiceSettings, Profile, OmniParserServer, SteamAccountPair, get_settings_manager


class GeneralTab(QWidget):
    """Tab for general settings like project directory"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Project directory section
        project_group = QGroupBox("Project Directory")
        project_layout = QVBoxLayout(project_group)

        project_desc = QLabel(
            "Base directory containing all Raptor X services (RPX, preset-manager, queue_service, etc.).\n"
            "All service working directories are relative to this path."
        )
        project_desc.setWordWrap(True)
        project_desc.setStyleSheet("color: #888;")
        project_layout.addWidget(project_desc)

        project_path_layout = QHBoxLayout()
        self.project_dir_edit = QLineEdit()
        self.project_dir_edit.setPlaceholderText("e.g., C:/Users/user/Code/RPX")
        project_path_layout.addWidget(self.project_dir_edit)

        self.project_browse_btn = QPushButton("Browse...")
        self.project_browse_btn.clicked.connect(self._browse_project_dir)
        project_path_layout.addWidget(self.project_browse_btn)

        project_layout.addLayout(project_path_layout)
        layout.addWidget(project_group)

        # OmniParser directory section
        omni_group = QGroupBox("OmniParser Directory")
        omni_layout = QVBoxLayout(omni_group)

        omni_desc = QLabel(
            "Directory containing the OmniParser server (omniparserserver module).\n"
            "Used when running local OmniParser instances."
        )
        omni_desc.setWordWrap(True)
        omni_desc.setStyleSheet("color: #888;")
        omni_layout.addWidget(omni_desc)

        omni_path_layout = QHBoxLayout()
        self.omni_dir_edit = QLineEdit()
        self.omni_dir_edit.setPlaceholderText("e.g., C:/Code/Omniparser server/omnitool/omniparserserver")
        omni_path_layout.addWidget(self.omni_dir_edit)

        self.omni_browse_btn = QPushButton("Browse...")
        self.omni_browse_btn.clicked.connect(self._browse_omni_dir)
        omni_path_layout.addWidget(self.omni_browse_btn)

        omni_layout.addLayout(omni_path_layout)
        layout.addWidget(omni_group)

        # Install dependencies section
        install_group = QGroupBox("Install Dependencies")
        install_layout = QVBoxLayout(install_group)

        install_desc = QLabel(
            "Install all service packages in editable mode (pip install -e .).\n"
            "This is required for services to be importable as modules."
        )
        install_desc.setWordWrap(True)
        install_desc.setStyleSheet("color: #888;")
        install_layout.addWidget(install_desc)

        install_btn_layout = QHBoxLayout()
        self.install_btn = QPushButton("Install All Services")
        self.install_btn.clicked.connect(self._install_dependencies)
        install_btn_layout.addWidget(self.install_btn)
        install_btn_layout.addStretch()
        install_layout.addLayout(install_btn_layout)

        self.install_progress = QProgressBar()
        self.install_progress.setVisible(False)
        install_layout.addWidget(self.install_progress)

        self.install_output = QTextEdit()
        self.install_output.setReadOnly(True)
        self.install_output.setMaximumHeight(150)
        self.install_output.setVisible(False)
        self.install_output.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        install_layout.addWidget(self.install_output)

        layout.addWidget(install_group)

        # Spacer
        layout.addStretch()

        # Track installation state
        self._install_process = None
        self._install_queue = []
        self._install_current = ""

    def _load_settings(self):
        """Load settings from settings manager"""
        settings = get_settings_manager()
        self.project_dir_edit.setText(settings.get_project_dir())
        self.omni_dir_edit.setText(settings.get_omniparser_dir())

    def _browse_project_dir(self):
        """Open directory picker for project dir"""
        current = self.project_dir_edit.text() or ""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Project Directory", current
        )
        if directory:
            self.project_dir_edit.setText(directory)

    def _browse_omni_dir(self):
        """Open directory picker for OmniParser dir"""
        current = self.omni_dir_edit.text() or ""
        directory = QFileDialog.getExistingDirectory(
            self, "Select OmniParser Directory", current
        )
        if directory:
            self.omni_dir_edit.setText(directory)

    def get_project_dir(self) -> str:
        return self.project_dir_edit.text().strip()

    def get_omniparser_dir(self) -> str:
        return self.omni_dir_edit.text().strip()

    def _install_dependencies(self):
        """Install all services in editable mode and set up SSH server"""
        from pathlib import Path
        import sys

        project_dir = self.project_dir_edit.text().strip()
        if not project_dir:
            QMessageBox.warning(self, "Error", "Please set the project directory first.")
            return

        base_path = Path(project_dir)
        if not base_path.exists():
            QMessageBox.warning(self, "Error", f"Project directory does not exist:\n{project_dir}")
            return

        # Find all service directories with pyproject.toml
        self._install_queue = []
        services = get_services()
        for config in services:
            service_dir = base_path / config.working_dir.name
            pyproject = service_dir / "pyproject.toml"
            if pyproject.exists():
                self._install_queue.append((config.display_name, str(service_dir)))

        # Also check OmniParser directory
        omni_dir = self.omni_dir_edit.text().strip()
        if omni_dir:
            omni_path = Path(omni_dir)
            # Check for pyproject.toml in omniparser dir or parent
            if (omni_path / "pyproject.toml").exists():
                self._install_queue.append(("OmniParser Server", str(omni_path)))
            elif (omni_path.parent / "pyproject.toml").exists():
                self._install_queue.append(("OmniParser Server", str(omni_path.parent)))

        # Setup UI for installation
        self.install_btn.setEnabled(False)
        self.install_progress.setVisible(True)
        # +1 for SSH setup step
        total_steps = len(self._install_queue) + 1 if sys.platform == "win32" else len(self._install_queue)
        self.install_progress.setMaximum(total_steps)
        self.install_progress.setValue(0)
        self.install_output.setVisible(True)
        self.install_output.clear()

        # Step 1: Setup SSH Server (Windows only)
        if sys.platform == "win32":
            self._setup_ssh_server()
        else:
            self.install_output.append("SSH setup skipped (Windows only)\n")

        if not self._install_queue:
            self.install_output.append("No services found with pyproject.toml files.")
            self.install_btn.setEnabled(True)
            self.install_progress.setVisible(False)
            return

        self.install_output.append(f"\nInstalling {len(self._install_queue)} services...\n")

        # Start pip installations
        self._install_next()

    def _setup_ssh_server(self):
        """Set up OpenSSH Server on Windows for SUT update pull"""
        self.install_output.append("=== Setting up OpenSSH Server ===\n")

        try:
            from ..ssh import SSHSetupManager
            ssh_manager = SSHSetupManager()

            # Set progress callback to update UI
            def progress_callback(message: str):
                self.install_output.append(f"  {message}")
                # Scroll to bottom
                scrollbar = self.install_output.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
                # Process events to keep UI responsive
                from PySide6.QtCore import QCoreApplication
                QCoreApplication.processEvents()

            ssh_manager.set_progress_callback(progress_callback)

            # Run SSH setup
            success, message = ssh_manager.setup_ssh_server()

            if success:
                self.install_output.append(f"\n  OK - {message}")
                status = ssh_manager.get_ssh_status()
                self.install_output.append(f"  Authorized keys: {status['authorized_keys_count']} registered")
            else:
                self.install_output.append(f"\n  FAILED - {message}")

        except ImportError as e:
            self.install_output.append(f"  SKIPPED - SSH module not available: {e}")
        except Exception as e:
            self.install_output.append(f"  ERROR - {e}")

        # Update progress
        self.install_progress.setValue(1)
        self.install_output.append("")  # Empty line before pip installs

    def _install_next(self):
        """Install the next service in the queue"""
        if not self._install_queue:
            # All done
            self.install_output.append("\n--- Installation complete! ---")
            self.install_btn.setEnabled(True)
            self.install_progress.setVisible(False)
            return

        name, path = self._install_queue.pop(0)
        self._install_current = name

        self.install_output.append(f"\n>>> Installing {name}...")
        self.install_output.append(f"    Directory: {path}")

        self._install_process = QProcess(self)
        self._install_process.setWorkingDirectory(path)
        self._install_process.readyReadStandardOutput.connect(self._on_install_stdout)
        self._install_process.readyReadStandardError.connect(self._on_install_stderr)
        self._install_process.finished.connect(self._on_install_finished)

        self._install_process.start("pip", ["install", "-e", "."])

    def _on_install_stdout(self):
        """Handle stdout from pip install"""
        if self._install_process:
            data = self._install_process.readAllStandardOutput().data()
            text = data.decode("utf-8", errors="replace").strip()
            if text:
                # Only show important lines to avoid clutter
                for line in text.split("\n"):
                    if line.strip() and not line.startswith("  "):
                        self.install_output.append(f"    {line}")

    def _on_install_stderr(self):
        """Handle stderr from pip install"""
        if self._install_process:
            data = self._install_process.readAllStandardError().data()
            text = data.decode("utf-8", errors="replace").strip()
            if text:
                self.install_output.append(f"    [ERR] {text}")

    def _on_install_finished(self, exit_code, exit_status):
        """Handle pip install completion"""
        current = self.install_progress.value() + 1
        self.install_progress.setValue(current)

        if exit_code == 0:
            self.install_output.append(f"    OK - {self._install_current} installed")
        else:
            self.install_output.append(f"    FAILED - {self._install_current} (exit code {exit_code})")

        # Scroll to bottom
        scrollbar = self.install_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # Continue with next
        self._install_next()


class ServicesTab(QWidget):
    """Tab for configuring services"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Services table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Service", "Host", "Port", "Remote", "Enabled"
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table)

        # Environment variables section
        env_group = QGroupBox("Environment Variables")
        env_layout = QVBoxLayout(env_group)

        self.env_label = QLabel("Select a service to edit environment variables")
        env_layout.addWidget(self.env_label)

        self.env_text = QTextEdit()
        self.env_text.setPlaceholderText("KEY=value\nKEY2=value2")
        self.env_text.setMaximumHeight(100)
        self.env_text.setEnabled(False)
        env_layout.addWidget(self.env_text)

        layout.addWidget(env_group)

    def _load_settings(self):
        """Load settings into table"""
        settings = get_settings_manager()

        services = get_services()
        self.table.setRowCount(len(services))
        for row, config in enumerate(services):
            svc_settings = settings.get_service_settings(config.name)

            # Service name (read-only)
            name_item = QTableWidgetItem(config.display_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setData(Qt.UserRole, config.name)
            self.table.setItem(row, 0, name_item)

            # Host
            host_item = QTableWidgetItem(svc_settings.host)
            self.table.setItem(row, 1, host_item)

            # Port
            port_item = QTableWidgetItem(str(svc_settings.port) if svc_settings.port else "")
            self.table.setItem(row, 2, port_item)

            # Remote checkbox
            remote_widget = QWidget()
            remote_layout = QHBoxLayout(remote_widget)
            remote_layout.setContentsMargins(0, 0, 0, 0)
            remote_layout.setAlignment(Qt.AlignCenter)
            remote_check = QCheckBox()
            remote_check.setChecked(svc_settings.remote)
            remote_layout.addWidget(remote_check)
            self.table.setCellWidget(row, 3, remote_widget)

            # Enabled checkbox
            enabled_widget = QWidget()
            enabled_layout = QHBoxLayout(enabled_widget)
            enabled_layout.setContentsMargins(0, 0, 0, 0)
            enabled_layout.setAlignment(Qt.AlignCenter)
            enabled_check = QCheckBox()
            enabled_check.setChecked(svc_settings.enabled)
            enabled_layout.addWidget(enabled_check)
            self.table.setCellWidget(row, 4, enabled_widget)

    def _on_selection_changed(self):
        """Update env vars display when selection changes"""
        selected = self.table.selectedItems()
        if not selected:
            self.env_label.setText("Select a service to edit environment variables")
            self.env_text.clear()
            self.env_text.setEnabled(False)
            return

        row = selected[0].row()
        service_name = self.table.item(row, 0).data(Qt.UserRole)

        settings = get_settings_manager()
        svc_settings = settings.get_service_settings(service_name)

        config = next((c for c in get_services() if c.name == service_name), None)
        display_name = config.display_name if config else service_name

        self.env_label.setText(f"Environment Variables for {display_name}:")
        self.env_text.setEnabled(True)

        # Show env vars as KEY=value lines
        env_lines = [f"{k}={v}" for k, v in svc_settings.env_vars.items()]
        self.env_text.setPlainText("\n".join(env_lines))

    def get_settings(self) -> dict:
        """Get current settings from table"""
        result = {}

        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).data(Qt.UserRole)
            host = self.table.item(row, 1).text().strip() or "localhost"
            port_text = self.table.item(row, 2).text().strip()
            port = int(port_text) if port_text.isdigit() else 0

            remote_widget = self.table.cellWidget(row, 3)
            remote_check = remote_widget.findChild(QCheckBox)
            remote = remote_check.isChecked() if remote_check else False

            enabled_widget = self.table.cellWidget(row, 4)
            enabled_check = enabled_widget.findChild(QCheckBox)
            enabled = enabled_check.isChecked() if enabled_check else True

            # Get env vars from text if this row is selected
            env_vars = {}
            selected = self.table.selectedItems()
            if selected and selected[0].row() == row:
                for line in self.env_text.toPlainText().split("\n"):
                    if "=" in line:
                        key, _, value = line.partition("=")
                        env_vars[key.strip()] = value.strip()
            else:
                # Keep existing env vars
                settings = get_settings_manager()
                svc_settings = settings.get_service_settings(name)
                env_vars = svc_settings.env_vars

            result[name] = ServiceSettings(
                host=host,
                port=port,
                enabled=enabled,
                remote=remote,
                env_vars=env_vars,
            )

        return result


class ProfilesTab(QWidget):
    """Tab for managing profiles"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_profiles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Active profile selector
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Active Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(150)
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addStretch()
        layout.addLayout(profile_layout)

        # Profile list
        list_layout = QHBoxLayout()

        self.profile_list = QListWidget()
        self.profile_list.itemSelectionChanged.connect(self._on_selection_changed)
        list_layout.addWidget(self.profile_list)

        # Buttons
        btn_layout = QVBoxLayout()
        self.new_btn = QPushButton("New")
        self.new_btn.clicked.connect(self._new_profile)
        btn_layout.addWidget(self.new_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_profile)
        self.edit_btn.setEnabled(False)
        btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_profile)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()
        list_layout.addLayout(btn_layout)

        layout.addLayout(list_layout)

        # Description
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

    def _load_profiles(self):
        """Load profiles into list"""
        settings = get_settings_manager()

        self.profile_combo.clear()
        self.profile_list.clear()

        for name, profile in settings.get_profiles().items():
            self.profile_combo.addItem(name)
            item = QListWidgetItem(f"{name} - {profile.description}")
            item.setData(Qt.UserRole, name)
            self.profile_list.addItem(item)

        # Set active profile
        idx = self.profile_combo.findText(settings.active_profile)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)

    def _on_selection_changed(self):
        """Update buttons when selection changes"""
        selected = self.profile_list.selectedItems()
        if not selected:
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.desc_label.clear()
            return

        name = selected[0].data(Qt.UserRole)
        settings = get_settings_manager()
        profiles = settings.get_profiles()

        if name in profiles:
            profile = profiles[name]
            self.desc_label.setText(f"Description: {profile.description}")

        # Can't delete 'local' profile
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(name != "local")

    def _new_profile(self):
        """Create new profile"""
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if ok and name:
            settings = get_settings_manager()
            desc, ok = QInputDialog.getText(self, "New Profile", "Description:")
            if ok:
                profile = Profile(name=name, description=desc, overrides={})
                settings.add_profile(profile)
                self._load_profiles()

    def _edit_profile(self):
        """Edit selected profile"""
        selected = self.profile_list.selectedItems()
        if not selected:
            return

        name = selected[0].data(Qt.UserRole)
        settings = get_settings_manager()
        profiles = settings.get_profiles()

        if name in profiles:
            desc, ok = QInputDialog.getText(
                self, "Edit Profile",
                "Description:",
                text=profiles[name].description
            )
            if ok:
                profiles[name].description = desc
                self._load_profiles()

    def _delete_profile(self):
        """Delete selected profile"""
        selected = self.profile_list.selectedItems()
        if not selected:
            return

        name = selected[0].data(Qt.UserRole)
        if name == "local":
            return

        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Delete profile '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            settings = get_settings_manager()
            settings.delete_profile(name)
            self._load_profiles()

    def get_active_profile(self) -> str:
        return self.profile_combo.currentText()


class OmniParserServerDialog(QDialog):
    """Dialog for adding/editing an OmniParser server"""

    def __init__(self, parent=None, server: OmniParserServer = None):
        super().__init__(parent)
        self.server = server
        self.setWindowTitle("Edit Server" if server else "Add Server")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., GPU Server 1")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("e.g., http://192.168.1.100:8000")
        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)

        if self.server:
            self.name_edit.setText(self.server.name)
            self.url_edit.setText(self.server.url)
            self.enabled_check.setChecked(self.server.enabled)

        layout.addRow("Name:", self.name_edit)
        layout.addRow("URL:", self.url_edit)
        layout.addRow("", self.enabled_check)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("OK")
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self._validate_and_accept)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addRow(btn_layout)

    def _validate_and_accept(self):
        """Validate input before accepting"""
        name = self.name_edit.text().strip()
        url = self.url_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Validation Error", "Name is required.")
            return
        if not url:
            QMessageBox.warning(self, "Validation Error", "URL is required.")
            return
        if not url.startswith("http://") and not url.startswith("https://"):
            QMessageBox.warning(self, "Validation Error", "URL must start with http:// or https://")
            return

        self.accept()

    def get_server(self) -> OmniParserServer:
        return OmniParserServer(
            name=self.name_edit.text().strip(),
            url=self.url_edit.text().strip(),
            enabled=self.enabled_check.isChecked(),
        )


class OmniParserServersTab(QWidget):
    """Tab for managing OmniParser server instances"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._servers = []
        self._instance_count = 0
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Local instances section
        local_group = QGroupBox("Local OmniParser Instances")
        local_layout = QVBoxLayout(local_group)

        local_desc = QLabel(
            "Start and manage local OmniParser instances on ports 8000-8004.\n"
            "Set to 0 to disable local management and use remote servers instead."
        )
        local_desc.setWordWrap(True)
        local_desc.setStyleSheet("color: #888;")
        local_layout.addWidget(local_desc)

        instance_layout = QHBoxLayout()
        instance_layout.addWidget(QLabel("Number of instances:"))
        self.instance_spin = QSpinBox()
        self.instance_spin.setRange(0, 5)
        self.instance_spin.setValue(0)
        self.instance_spin.setToolTip("0 = disabled, 1-5 = start that many local OmniParser servers")
        self.instance_spin.valueChanged.connect(self._on_instance_count_changed)
        instance_layout.addWidget(self.instance_spin)
        instance_layout.addStretch()
        local_layout.addLayout(instance_layout)

        self.instance_info = QLabel("")
        self.instance_info.setStyleSheet("color: #4ec9b0;")
        local_layout.addWidget(self.instance_info)

        layout.addWidget(local_group)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Remote servers section
        remote_group = QGroupBox("Remote OmniParser Servers")
        remote_layout = QVBoxLayout(remote_group)

        # Description
        desc = QLabel(
            "Configure remote OmniParser servers (used when local instances = 0).\n"
            "Enabled servers are passed via OMNIPARSER_URLS environment variable."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888;")
        remote_layout.addWidget(desc)

        # Server list
        self.server_list = QListWidget()
        self.server_list.setSelectionMode(QListWidget.SingleSelection)
        self.server_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.server_list.itemDoubleClicked.connect(self._edit_server)
        remote_layout.addWidget(self.server_list)

        # Buttons
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._add_server)
        btn_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_server)
        self.edit_btn.setEnabled(False)
        btn_layout.addWidget(self.edit_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_server)
        self.remove_btn.setEnabled(False)
        btn_layout.addWidget(self.remove_btn)

        btn_layout.addStretch()
        remote_layout.addLayout(btn_layout)

        layout.addWidget(remote_group)

    def _load_settings(self):
        """Load settings from settings manager"""
        settings = get_settings_manager()
        self._servers = settings.get_omniparser_servers()
        self._instance_count = settings.get_omniparser_instance_count()
        self.instance_spin.setValue(self._instance_count)
        self._update_instance_info()
        self._refresh_list()
        self._update_remote_enabled()

    def _on_instance_count_changed(self, value: int):
        """Handle instance count spinbox change"""
        self._instance_count = value
        self._update_instance_info()
        self._update_remote_enabled()

    def _update_instance_info(self):
        """Update the instance info label"""
        if self._instance_count == 0:
            self.instance_info.setText("Local management disabled - using remote servers")
            self.instance_info.setStyleSheet("color: #888;")
        else:
            ports = ", ".join(str(8000 + i) for i in range(self._instance_count))
            self.instance_info.setText(f"Will start {self._instance_count} instance(s) on port(s): {ports}")
            self.instance_info.setStyleSheet("color: #4ec9b0;")

    def _update_remote_enabled(self):
        """Enable/disable remote server controls based on instance count"""
        remote_enabled = self._instance_count == 0
        self.server_list.setEnabled(remote_enabled)
        self.add_btn.setEnabled(remote_enabled)
        # edit and remove depend on selection too
        if not remote_enabled:
            self.edit_btn.setEnabled(False)
            self.remove_btn.setEnabled(False)

    def _load_servers(self):
        """Load servers from settings"""
        settings = get_settings_manager()
        self._servers = settings.get_omniparser_servers()
        self._refresh_list()

    def _refresh_list(self):
        """Refresh the list display"""
        self.server_list.clear()
        for server in self._servers:
            status = "\u2713" if server.enabled else "\u2717"  # checkmark or X
            color = "#4ec9b0" if server.enabled else "#808080"
            item = QListWidgetItem(f"{status} {server.name} - {server.url}")
            item.setForeground(Qt.GlobalColor.white if server.enabled else Qt.GlobalColor.gray)
            self.server_list.addItem(item)

    def _on_selection_changed(self):
        """Update buttons when selection changes"""
        has_selection = self.server_list.currentRow() >= 0
        self.edit_btn.setEnabled(has_selection)
        self.remove_btn.setEnabled(has_selection)

    def _add_server(self):
        """Add a new server"""
        dialog = OmniParserServerDialog(self)
        if dialog.exec() == QDialog.Accepted:
            server = dialog.get_server()
            self._servers.append(server)
            self._refresh_list()

    def _edit_server(self):
        """Edit selected server"""
        row = self.server_list.currentRow()
        if row < 0 or row >= len(self._servers):
            return

        server = self._servers[row]
        dialog = OmniParserServerDialog(self, server)
        if dialog.exec() == QDialog.Accepted:
            self._servers[row] = dialog.get_server()
            self._refresh_list()

    def _remove_server(self):
        """Remove selected server"""
        row = self.server_list.currentRow()
        if row < 0 or row >= len(self._servers):
            return

        server = self._servers[row]
        reply = QMessageBox.question(
            self, "Remove Server",
            f"Remove '{server.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._servers.pop(row)
            self._refresh_list()

    def get_servers(self):
        """Get current server list"""
        return self._servers.copy()

    def get_instance_count(self) -> int:
        """Get current instance count setting"""
        return self._instance_count


class SteamAccountPairDialog(QDialog):
    """Dialog for adding/editing a Steam account pair"""

    def __init__(self, parent=None, pair: SteamAccountPair = None):
        super().__init__(parent)
        self.pair = pair
        self.setWindowTitle("Edit Account Pair" if pair else "Add Account Pair")
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Description
        desc = QLabel(
            "Each pair has two accounts:\n"
            "• A-F Account: Used for games starting with A-F (e.g., Cyberpunk, BMW)\n"
            "• G-Z Account: Used for games starting with G-Z (e.g., RDR2, SOTR)"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888; margin-bottom: 10px;")
        layout.addWidget(desc)

        # Name field
        name_layout = QHBoxLayout()
        name_label = QLabel("Name:")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Pair 1")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # A-F Account section
        af_group = QGroupBox("A-F Games Account")
        af_layout = QFormLayout(af_group)
        self.af_username_edit = QLineEdit()
        self.af_username_edit.setPlaceholderText("Steam username")
        af_layout.addRow("Username:", self.af_username_edit)
        self.af_password_edit = QLineEdit()
        self.af_password_edit.setPlaceholderText("Steam password")
        self.af_password_edit.setEchoMode(QLineEdit.Password)
        af_layout.addRow("Password:", self.af_password_edit)
        layout.addWidget(af_group)

        # G-Z Account section
        gz_group = QGroupBox("G-Z Games Account")
        gz_layout = QFormLayout(gz_group)
        self.gz_username_edit = QLineEdit()
        self.gz_username_edit.setPlaceholderText("Steam username")
        gz_layout.addRow("Username:", self.gz_username_edit)
        self.gz_password_edit = QLineEdit()
        self.gz_password_edit.setPlaceholderText("Steam password")
        self.gz_password_edit.setEchoMode(QLineEdit.Password)
        gz_layout.addRow("Password:", self.gz_password_edit)
        layout.addWidget(gz_group)

        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)
        layout.addWidget(self.enabled_check)

        # Load existing values
        if self.pair:
            self.name_edit.setText(self.pair.name)
            self.af_username_edit.setText(self.pair.af_username)
            self.af_password_edit.setText(self.pair.af_password)
            self.gz_username_edit.setText(self.pair.gz_username)
            self.gz_password_edit.setText(self.pair.gz_password)
            self.enabled_check.setChecked(self.pair.enabled)

        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("OK")
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self._validate_and_accept)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _validate_and_accept(self):
        """Validate input before accepting"""
        name = self.name_edit.text().strip()
        af_user = self.af_username_edit.text().strip()
        af_pass = self.af_password_edit.text()
        gz_user = self.gz_username_edit.text().strip()
        gz_pass = self.gz_password_edit.text()

        if not name:
            QMessageBox.warning(self, "Validation Error", "Name is required.")
            return
        if not af_user or not af_pass:
            QMessageBox.warning(self, "Validation Error", "A-F account username and password are required.")
            return
        if not gz_user or not gz_pass:
            QMessageBox.warning(self, "Validation Error", "G-Z account username and password are required.")
            return

        self.accept()

    def get_pair(self) -> SteamAccountPair:
        return SteamAccountPair(
            name=self.name_edit.text().strip(),
            af_username=self.af_username_edit.text().strip(),
            af_password=self.af_password_edit.text(),
            gz_username=self.gz_username_edit.text().strip(),
            gz_password=self.gz_password_edit.text(),
            enabled=self.enabled_check.isChecked(),
        )


class SteamAccountsTab(QWidget):
    """Tab for managing Steam account pairs for multi-SUT automation"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pairs = []
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Description
        desc = QLabel(
            "Configure Steam account pairs for multi-SUT automation.\n\n"
            "Steam only allows one concurrent login per account. To run benchmarks on multiple SUTs "
            "simultaneously, each SUT needs a dedicated account pair. Games are split by first letter:\n"
            "• A-F: BMW, Cyberpunk, Far Cry, etc.\n"
            "• G-Z: Hitman, RDR2, SOTR, etc.\n\n"
            "This allows two games to run concurrently per SUT without login conflicts."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888;")
        layout.addWidget(desc)

        # Steam Login Timeout setting
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("Steam Login Timeout:")
        timeout_label.setToolTip("Maximum time to wait for Steam login (for slow internet connections)")
        timeout_layout.addWidget(timeout_label)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(30, 600)  # 30 seconds to 10 minutes
        self.timeout_spin.setSuffix(" seconds")
        self.timeout_spin.setValue(180)  # Default 3 minutes
        self.timeout_spin.setToolTip("Increase this for slow internet connections")
        timeout_layout.addWidget(self.timeout_spin)
        timeout_layout.addStretch()
        layout.addLayout(timeout_layout)

        layout.addSpacing(10)

        # Account pairs list
        self.pairs_list = QListWidget()
        self.pairs_list.setSelectionMode(QListWidget.SingleSelection)
        self.pairs_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.pairs_list.itemDoubleClicked.connect(self._edit_pair)
        layout.addWidget(self.pairs_list)

        # Buttons
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add Pair")
        self.add_btn.clicked.connect(self._add_pair)
        btn_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_pair)
        self.edit_btn.setEnabled(False)
        btn_layout.addWidget(self.edit_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_pair)
        self.remove_btn.setEnabled(False)
        btn_layout.addWidget(self.remove_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Info label
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #4ec9b0;")
        layout.addWidget(self.info_label)

    def _load_settings(self):
        """Load settings from settings manager"""
        settings = get_settings_manager()
        self._pairs = settings.get_steam_account_pairs()
        self.timeout_spin.setValue(settings.get_steam_login_timeout())
        self._refresh_list()

    def _refresh_list(self):
        """Refresh the list display"""
        self.pairs_list.clear()
        for pair in self._pairs:
            status = "\u2713" if pair.enabled else "\u2717"
            item = QListWidgetItem(
                f"{status} {pair.name}: {pair.af_username} (A-F) / {pair.gz_username} (G-Z)"
            )
            item.setForeground(Qt.GlobalColor.white if pair.enabled else Qt.GlobalColor.gray)
            self.pairs_list.addItem(item)

        # Update info label
        enabled_count = sum(1 for p in self._pairs if p.enabled)
        if enabled_count == 0:
            self.info_label.setText("No account pairs configured - multi-SUT automation will be limited")
            self.info_label.setStyleSheet("color: #f0ad4e;")
        else:
            self.info_label.setText(f"{enabled_count} account pair(s) available for {enabled_count} concurrent SUT(s)")
            self.info_label.setStyleSheet("color: #4ec9b0;")

    def _on_selection_changed(self):
        """Update buttons when selection changes"""
        has_selection = self.pairs_list.currentRow() >= 0
        self.edit_btn.setEnabled(has_selection)
        self.remove_btn.setEnabled(has_selection)

    def _add_pair(self):
        """Add a new account pair"""
        dialog = SteamAccountPairDialog(self)
        if dialog.exec() == QDialog.Accepted:
            pair = dialog.get_pair()
            self._pairs.append(pair)
            self._refresh_list()

    def _edit_pair(self):
        """Edit selected account pair"""
        row = self.pairs_list.currentRow()
        if row < 0 or row >= len(self._pairs):
            return

        pair = self._pairs[row]
        dialog = SteamAccountPairDialog(self, pair)
        if dialog.exec() == QDialog.Accepted:
            self._pairs[row] = dialog.get_pair()
            self._refresh_list()

    def _remove_pair(self):
        """Remove selected account pair"""
        row = self.pairs_list.currentRow()
        if row < 0 or row >= len(self._pairs):
            return

        pair = self._pairs[row]
        reply = QMessageBox.question(
            self, "Remove Account Pair",
            f"Remove '{pair.name}'?\n\nThis will also remove the stored credentials.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._pairs.pop(row)
            self._refresh_list()

    def get_pairs(self) -> list:
        """Get current account pairs list"""
        return self._pairs.copy()

    def get_timeout(self) -> int:
        """Get the Steam login timeout value"""
        return self.timeout_spin.value()


class SettingsDialog(QDialog):
    """Settings dialog with tabs"""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 450)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Tab widget
        self.tabs = QTabWidget()

        self.general_tab = GeneralTab()
        self.tabs.addTab(self.general_tab, "General")

        self.services_tab = ServicesTab()
        self.tabs.addTab(self.services_tab, "Services")

        self.profiles_tab = ProfilesTab()
        self.tabs.addTab(self.profiles_tab, "Profiles")

        self.omniparser_tab = OmniParserServersTab()
        self.tabs.addTab(self.omniparser_tab, "OmniParser Servers")

        self.steam_accounts_tab = SteamAccountsTab()
        self.tabs.addTab(self.steam_accounts_tab, "Steam Accounts")

        layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._apply)
        btn_layout.addWidget(self.apply_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def _apply(self):
        """Apply settings without closing"""
        self._save_settings()
        self.settings_changed.emit()

    def _save(self):
        """Save and close"""
        self._save_settings()
        self.settings_changed.emit()
        self.accept()

    def _save_settings(self):
        """Save current settings"""
        settings = get_settings_manager()

        # Save general settings (directories)
        settings.set_project_dir(self.general_tab.get_project_dir())
        settings.set_omniparser_dir(self.general_tab.get_omniparser_dir())

        # Save service settings
        for name, svc_settings in self.services_tab.get_settings().items():
            settings.set_service_settings(name, svc_settings)

        # Save active profile
        settings.active_profile = self.profiles_tab.get_active_profile()

        # Save OmniParser servers and instance count
        settings.set_omniparser_servers(self.omniparser_tab.get_servers())
        settings.set_omniparser_instance_count(self.omniparser_tab.get_instance_count())

        # Save Steam account pairs and timeout
        settings.set_steam_account_pairs(self.steam_accounts_tab.get_pairs())
        settings.set_steam_login_timeout(self.steam_accounts_tab.get_timeout())

        settings.save()
