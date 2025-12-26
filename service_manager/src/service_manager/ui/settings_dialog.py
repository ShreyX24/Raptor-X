"""
Settings Dialog - Runtime configuration UI
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QLineEdit, QCheckBox, QPushButton, QComboBox,
    QGroupBox, QFormLayout, QListWidget, QListWidgetItem,
    QMessageBox, QInputDialog, QTextEdit
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, Signal

from ..config import SERVICES
from ..settings import ServiceSettings, Profile, OmniParserServer, get_settings_manager


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

        self.table.setRowCount(len(SERVICES))
        for row, config in enumerate(SERVICES):
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

        config = next((c for c in SERVICES if c.name == service_name), None)
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
        self._setup_ui()
        self._load_servers()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Description
        desc = QLabel(
            "Configure OmniParser servers for the Queue Service.\n"
            "Enabled servers are passed via OMNIPARSER_URLS environment variable."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888; margin-bottom: 10px;")
        layout.addWidget(desc)

        # Server list
        self.server_list = QListWidget()
        self.server_list.setSelectionMode(QListWidget.SingleSelection)
        self.server_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.server_list.itemDoubleClicked.connect(self._edit_server)
        layout.addWidget(self.server_list)

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
        layout.addLayout(btn_layout)

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

        self.services_tab = ServicesTab()
        self.tabs.addTab(self.services_tab, "Services")

        self.profiles_tab = ProfilesTab()
        self.tabs.addTab(self.profiles_tab, "Profiles")

        self.omniparser_tab = OmniParserServersTab()
        self.tabs.addTab(self.omniparser_tab, "OmniParser Servers")

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

        # Save service settings
        for name, svc_settings in self.services_tab.get_settings().items():
            settings.set_service_settings(name, svc_settings)

        # Save active profile
        settings.active_profile = self.profiles_tab.get_active_profile()

        # Save OmniParser servers
        settings.set_omniparser_servers(self.omniparser_tab.get_servers())

        settings.save()
