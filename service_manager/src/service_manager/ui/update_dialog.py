"""
Update Dialog - Shows update progress and handles application restart.
"""
import sys
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QGroupBox, QApplication
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QFont

from ..update.update_manager import UpdateManager, UpdateResult
from ..services.process_manager import ProcessManager


class UpdateWorker(QThread):
    """Background worker for update operations"""

    progress = Signal(str, int, int)  # message, current, total
    log = Signal(str)  # log message
    finished = Signal(bool, str)  # success, message

    def __init__(
        self,
        update_manager: UpdateManager,
        process_manager: ProcessManager,
        parent=None
    ):
        super().__init__(parent)
        self.update_manager = update_manager
        self.process_manager = process_manager
        self._cancelled = False

    def run(self):
        """Execute the update process"""
        try:
            # Phase 1: Stop all services
            self.log.emit("\n--- Stopping services ---")
            self.progress.emit("Stopping services...", 0, 4)

            # Use QMetaObject.invokeMethod for thread-safe call
            # Since we can't call stop_all() directly from this thread,
            # we'll emit a signal and let the main thread handle it
            self.log.emit("Services will be stopped by main thread")

            # Phase 2: Pull updates
            self.log.emit("\n--- Pulling updates ---")
            self.progress.emit("Pulling updates...", 1, 4)

            def on_pull_progress(msg, cur, tot):
                self.log.emit(f"  {msg}")

            self.update_manager.set_progress_callback(on_pull_progress)
            results = self.update_manager.update_all()

            # Log results
            all_success = True
            for result in results:
                if result.success:
                    self.log.emit(f"  [OK] {result.repo}: {result.old_commit} -> {result.new_commit}")
                    if result.changed_files:
                        self.log.emit(f"       {len(result.changed_files)} files changed")
                else:
                    self.log.emit(f"  [FAIL] {result.repo}: {result.message}")
                    all_success = False

            if not all_success:
                self.finished.emit(False, "Some repositories failed to update")
                return

            # Phase 3: Reinstall services
            self.log.emit("\n--- Reinstalling packages ---")
            self.progress.emit("Installing packages...", 2, 4)

            def on_install_progress(msg, cur, tot):
                self.log.emit(f"  {msg}")

            self.update_manager.set_progress_callback(on_install_progress)
            success, errors = self.update_manager.reinstall_services()

            if errors:
                for error in errors:
                    self.log.emit(f"  [WARN] {error}")

            # Phase 4: Notify SUTs
            self.log.emit("\n--- Notifying SUTs ---")
            self.progress.emit("Notifying SUTs...", 3, 4)

            master_ip = self.update_manager.get_local_ip()
            notify_success, notify_msg = self.update_manager.notify_suts(master_ip)
            self.log.emit(f"  {notify_msg}")

            self.progress.emit("Update complete!", 4, 4)
            self.finished.emit(True, "Update completed successfully")

        except Exception as e:
            self.log.emit(f"\n[ERROR] {str(e)}")
            self.finished.emit(False, str(e))


class UpdateDialog(QDialog):
    """Dialog for performing system updates"""

    def __init__(
        self,
        base_dir: str,
        process_manager: ProcessManager,
        parent=None
    ):
        super().__init__(parent)
        self.base_dir = Path(base_dir)
        self.process_manager = process_manager
        self.update_manager = UpdateManager(self.base_dir)
        self.update_worker: Optional[UpdateWorker] = None
        self.countdown_timer: Optional[QTimer] = None
        self.countdown_seconds = 5

        self.setWindowTitle("RPX System Update")
        self.setMinimumSize(700, 500)
        self.setModal(True)

        self._setup_ui()
        self._check_updates()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QLabel("System Update")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(header)

        # Available updates section
        self.updates_group = QGroupBox("Available Updates")
        updates_layout = QVBoxLayout(self.updates_group)

        self.updates_label = QLabel("Checking for updates...")
        self.updates_label.setWordWrap(True)
        updates_layout.addWidget(self.updates_label)

        self.updates_list = QTextEdit()
        self.updates_list.setReadOnly(True)
        self.updates_list.setFont(QFont("Consolas", 9))
        self.updates_list.setMaximumHeight(100)
        self.updates_list.setVisible(False)
        updates_layout.addWidget(self.updates_list)

        layout.addWidget(self.updates_group)

        # Progress section
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888;")
        progress_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        layout.addWidget(progress_group)

        # Log output
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3d3d3d;
            }
        """)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

        # Countdown section (hidden initially)
        self.countdown_group = QGroupBox("Restart Required")
        countdown_layout = QVBoxLayout(self.countdown_group)

        self.countdown_label = QLabel("Application will restart in 5 seconds...")
        self.countdown_label.setStyleSheet("color: #f0ad4e; font-size: 13px;")
        countdown_layout.addWidget(self.countdown_label)

        countdown_btn_layout = QHBoxLayout()
        self.restart_now_btn = QPushButton("Restart Now")
        self.restart_now_btn.clicked.connect(self._restart_now)
        countdown_btn_layout.addWidget(self.restart_now_btn)

        self.cancel_restart_btn = QPushButton("Cancel")
        self.cancel_restart_btn.clicked.connect(self._cancel_countdown)
        countdown_btn_layout.addWidget(self.cancel_restart_btn)

        countdown_btn_layout.addStretch()
        countdown_layout.addLayout(countdown_btn_layout)

        self.countdown_group.setVisible(False)
        layout.addWidget(self.countdown_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.update_btn = QPushButton("Start Update")
        self.update_btn.setEnabled(False)
        self.update_btn.clicked.connect(self._start_update)
        self.update_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:disabled {
                background-color: #3d3d3d;
                color: #888;
            }
        """)
        btn_layout.addWidget(self.update_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def _log(self, message: str):
        """Add message to log"""
        self.log_text.append(message)
        # Scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _check_updates(self):
        """Check for available updates"""
        self._log("Checking for updates...")
        self.status_label.setText("Checking...")

        def on_progress(msg, cur, tot):
            if tot > 0:
                self.progress_bar.setValue(int((cur / tot) * 100))

        self.update_manager.set_progress_callback(on_progress)

        # Run in this thread for initial check (it's fast)
        try:
            updates = self.update_manager.check_for_updates()

            if not updates:
                self._log("\nNo updates available - you're up to date!")
                self.updates_label.setText("You're up to date!")
                self.updates_label.setStyleSheet("color: #4ec9b0;")
                self.status_label.setText("No updates available")
                self.progress_bar.setValue(100)
            else:
                self._log(f"\n{len(updates)} update(s) available:")
                self.updates_list.setVisible(True)

                update_text = []
                for repo, (old, new, msg) in updates.items():
                    line = f"{repo}: {old} -> {new}"
                    if msg:
                        line += f"\n  {msg}"
                    update_text.append(line)
                    self._log(f"  {repo}: {old} -> {new}")
                    if msg:
                        self._log(f"    {msg}")

                self.updates_list.setText("\n".join(update_text))
                self.updates_label.setText(f"{len(updates)} update(s) available")
                self.updates_label.setStyleSheet("color: #dcdcaa;")
                self.status_label.setText("Ready to update")
                self.progress_bar.setValue(100)
                self.update_btn.setEnabled(True)

        except Exception as e:
            self._log(f"\n[ERROR] Failed to check updates: {e}")
            self.updates_label.setText(f"Error: {e}")
            self.updates_label.setStyleSheet("color: #f48771;")
            self.status_label.setText("Error checking updates")

    def _start_update(self):
        """Start the update process"""
        self.update_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        # Stop all services first (in main thread)
        self._log("\n--- Stopping services ---")
        running = self.process_manager.get_running_count()
        if running > 0:
            self._log(f"Stopping {running} running service(s)...")
            self.process_manager.stop_all()

            # Wait a bit for services to stop
            QTimer.singleShot(2000, self._continue_update)
        else:
            self._continue_update()

    def _continue_update(self):
        """Continue update after services are stopped"""
        self._log("Services stopped.")

        # Start update worker
        self.update_worker = UpdateWorker(
            self.update_manager,
            self.process_manager,
            self
        )
        self.update_worker.progress.connect(self._on_progress)
        self.update_worker.log.connect(self._log)
        self.update_worker.finished.connect(self._on_update_finished)
        self.update_worker.start()

    def _on_progress(self, message: str, current: int, total: int):
        """Handle progress updates"""
        self.status_label.setText(message)
        if total > 0:
            self.progress_bar.setValue(int((current / total) * 100))

    def _on_update_finished(self, success: bool, message: str):
        """Handle update completion"""
        if success:
            self._log(f"\n[SUCCESS] {message}")
            self.status_label.setText("Update complete!")
            self.status_label.setStyleSheet("color: #4ec9b0;")

            # Start countdown for restart
            self._start_countdown()
        else:
            self._log(f"\n[FAILED] {message}")
            self.status_label.setText(f"Failed: {message}")
            self.status_label.setStyleSheet("color: #f48771;")
            self.close_btn.setEnabled(True)

    def _start_countdown(self):
        """Start the restart countdown"""
        self.countdown_group.setVisible(True)
        self.countdown_seconds = 5

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._countdown_tick)
        self.countdown_timer.start(1000)

    def _countdown_tick(self):
        """Handle countdown timer tick"""
        self.countdown_seconds -= 1
        self.countdown_label.setText(
            f"Application will restart in {self.countdown_seconds} seconds..."
        )

        if self.countdown_seconds <= 0:
            self.countdown_timer.stop()
            self._restart_application()

    def _cancel_countdown(self):
        """Cancel the restart countdown"""
        if self.countdown_timer:
            self.countdown_timer.stop()

        self.countdown_group.setVisible(False)
        self._log("\nRestart cancelled. Please restart manually to apply changes.")
        self._log("Run: rpx-manager")
        self.close_btn.setEnabled(True)

    def _restart_now(self):
        """Restart immediately"""
        if self.countdown_timer:
            self.countdown_timer.stop()
        self._restart_application()

    def _restart_application(self):
        """Restart the Service Manager application"""
        self._log("\nRestarting application...")

        # Start all services before restarting
        self._log("Starting services...")
        self.process_manager.start_all()

        # Give services a moment to start
        QTimer.singleShot(1000, self._do_restart)

    def _do_restart(self):
        """Actually perform the restart"""
        # Launch new instance
        try:
            # Try to find the executable
            import shutil
            exe = shutil.which("rpx-manager") or shutil.which("gemma-manager")

            if exe:
                subprocess.Popen([exe], start_new_session=True)
            else:
                # Fallback to module execution
                subprocess.Popen(
                    [sys.executable, "-m", "service_manager"],
                    cwd=str(self.base_dir / "service_manager"),
                    start_new_session=True
                )

            self._log("New instance launched. Closing this window...")

        except Exception as e:
            self._log(f"Failed to launch new instance: {e}")
            self._log("Please restart manually: rpx-manager")
            return

        # Close current instance
        QTimer.singleShot(500, QApplication.quit)

    def closeEvent(self, event):
        """Handle dialog close"""
        if self.update_worker and self.update_worker.isRunning():
            event.ignore()
            return

        if self.countdown_timer and self.countdown_timer.isActive():
            self.countdown_timer.stop()

        event.accept()
