"""
Main application entry point
"""

import argparse
import sys


# ---------------------------------------------------------------------------
# Windows elevation & scheduled-task helpers (no Qt dependency)
# ---------------------------------------------------------------------------

def _is_admin() -> bool:
    """Check if running with admin privileges on Windows."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _run_as_admin() -> bool:
    """Re-launch as admin via UAC.

    For the GUI entry-point (rpx-manager / pythonw.exe) we invoke the exe
    directly — no cmd.exe wrapper needed since PySide6 creates its own window.
    """
    if sys.platform != "win32":
        return False

    import ctypes
    import shutil

    # Prefer the gui-script exe so no console window flashes
    exe = shutil.which("rpx-manager") or shutil.which("rpx-manager-cli")
    if exe:
        params = " ".join(sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, None, 1  # SW_SHOWNORMAL
        )
        return ret > 32

    # Fallback: run via current interpreter
    params = f'"{sys.argv[0]}" {" ".join(sys.argv[1:])}'
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    return ret > 32


def _install_scheduled_task() -> bool:
    """Create a Windows Scheduled Task that auto-starts Service Manager
    at logon with highest privileges (no UAC prompt)."""
    if sys.platform != "win32":
        print("Scheduled task installation only supported on Windows")
        return False

    import subprocess
    import shutil

    task_name = "RPX-ServiceManager"

    exe = shutil.which("rpx-manager")
    if not exe:
        exe = shutil.which("rpx-manager-cli")
    if not exe:
        if sys.argv[0].lower().endswith(".exe"):
            exe = sys.argv[0]
        else:
            print("Error: Could not find rpx-manager executable")
            return False

    command = f'"{exe}"'

    # Delete any existing task (ignore errors if absent)
    subprocess.run(
        ["schtasks", "/Delete", "/TN", task_name, "/F"],
        capture_output=True, check=False,
    )

    result = subprocess.run(
        [
            "schtasks", "/Create",
            "/TN", task_name,
            "/TR", command,
            "/SC", "ONLOGON",
            "/RL", "HIGHEST",
            "/IT",
            "/F",
        ],
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        print(f"SUCCESS: Scheduled task '{task_name}' created!")
        print(f"Command: {command}")
        print()
        print("Service Manager will now:")
        print("  - Start automatically at user login")
        print("  - Run with admin privileges (no UAC prompt)")
        print()
        print("To start immediately without relogging:")
        print(f"  schtasks /Run /TN {task_name}")
        print()
        print("To uninstall:")
        print("  rpx-manager-cli --uninstall-service")
        return True
    else:
        print(f"Error creating scheduled task: {result.stderr}")
        return False


def _uninstall_scheduled_task() -> bool:
    """Remove the RPX-ServiceManager scheduled task."""
    if sys.platform != "win32":
        print("Scheduled task uninstallation only supported on Windows")
        return False

    import subprocess

    task_name = "RPX-ServiceManager"
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", task_name, "/F"],
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        print(f"SUCCESS: Scheduled task '{task_name}' removed!")
        return True
    else:
        print(f"Error removing scheduled task: {result.stderr}")
        return False


def _run_scheduled_task() -> bool:
    """Try to start Service Manager via its scheduled task (bypasses UAC)."""
    if sys.platform != "win32":
        return False

    import subprocess

    task_name = "RPX-ServiceManager"
    try:
        result = subprocess.run(
            ["schtasks", "/Run", "/TN", task_name],
            capture_output=True, text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _show_error(message: str):
    """Show an error to the user.  Works even from the gui-script entry
    point (no console) by falling back to a Win32 MessageBox."""
    print(message)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None, message, "RPX Service Manager", 0x10  # MB_ICONERROR
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    """Launch the Service Manager application"""
    # Parse CLI args before any Qt imports so --install/--uninstall work
    # without a display or PySide6 dependency issues.
    parser = argparse.ArgumentParser(
        description="RPX Service Manager - manage all Raptor X services",
    )
    parser.add_argument(
        "--install-service", action="store_true",
        help="Install as a Windows Scheduled Task (auto-start at login, elevated)",
    )
    parser.add_argument(
        "--uninstall-service", action="store_true",
        help="Remove the Windows Scheduled Task",
    )
    args, remaining = parser.parse_known_args()

    # --- Handle --install-service / --uninstall-service -----------------
    if args.install_service:
        if not _is_admin():
            print("Installing service requires administrator privileges.")
            print("Elevating...")
            if _run_as_admin():
                sys.exit(0)
            else:
                _show_error("Error: Could not elevate to admin")
                sys.exit(1)
        success = _install_scheduled_task()
        sys.exit(0 if success else 1)

    if args.uninstall_service:
        if not _is_admin():
            print("Uninstalling service requires administrator privileges.")
            print("Elevating...")
            if _run_as_admin():
                sys.exit(0)
            else:
                _show_error("Error: Could not elevate to admin")
                sys.exit(1)
        success = _uninstall_scheduled_task()
        sys.exit(0 if success else 1)

    # --- Normal launch: ensure we are elevated -------------------------
    if sys.platform == "win32" and not _is_admin():
        # Try the scheduled task first (silent, no UAC)
        if _run_scheduled_task():
            sys.exit(0)

        # Fall back to a UAC prompt
        if _run_as_admin():
            sys.exit(0)

        # If both fail, warn but continue un-elevated
        _show_error(
            "RPX Service Manager could not obtain admin privileges.\n"
            "Some features (firewall rules, service management) may not work.\n\n"
            "To fix, run: rpx-manager-cli --install-service"
        )

    # --- Elevated (or non-Windows): start Qt ---------------------------
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

    from .ui.main_window import MainWindow

    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(remaining)
    app.setApplicationName("RPX Service Manager")
    app.setOrganizationName("RaptorX")

    # Set default font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Apply dark theme stylesheet
    app.setStyleSheet(get_stylesheet())

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


def get_stylesheet() -> str:
    """Get the application stylesheet"""
    return """
        QMainWindow {
            background-color: #1e1e1e;
        }
        QWidget {
            background-color: #252526;
            color: #cccccc;
        }
        QTreeWidget {
            background-color: #252526;
            border: none;
            outline: none;
        }
        QTreeWidget::item {
            padding: 4px;
            border-radius: 3px;
        }
        QTreeWidget::item:selected {
            background-color: #094771;
        }
        QTreeWidget::item:hover {
            background-color: #2a2d2e;
        }
        QTreeWidget::branch {
            background-color: #252526;
        }
        QHeaderView::section {
            background-color: #333333;
            color: #cccccc;
            padding: 4px;
            border: none;
        }
        QToolBar {
            background-color: #333333;
            border: none;
            spacing: 4px;
            padding: 4px;
        }
        QToolButton {
            background-color: transparent;
            border: none;
            border-radius: 3px;
            padding: 4px 8px;
            color: #cccccc;
        }
        QToolButton:hover {
            background-color: #404040;
        }
        QToolButton:pressed {
            background-color: #505050;
        }
        QPushButton {
            background-color: #0e639c;
            border: none;
            border-radius: 3px;
            padding: 6px 14px;
            color: white;
        }
        QPushButton:hover {
            background-color: #1177bb;
        }
        QPushButton:pressed {
            background-color: #094771;
        }
        QPushButton:disabled {
            background-color: #3a3a3a;
            color: #6a6a6a;
        }
        QStatusBar {
            background-color: #007acc;
            color: white;
        }
        QSplitter::handle {
            background-color: #333333;
        }
        QSplitter::handle:horizontal {
            width: 2px;
        }
        QSplitter::handle:vertical {
            height: 2px;
        }
        QPlainTextEdit {
            background-color: #1e1e1e;
            color: #d4d4d4;
            border: none;
            font-family: Consolas, monospace;
            font-size: 9pt;
        }
        QLabel {
            color: #cccccc;
        }
        QMenu {
            background-color: #252526;
            border: 1px solid #454545;
        }
        QMenu::item {
            padding: 5px 25px;
        }
        QMenu::item:selected {
            background-color: #094771;
        }
        QScrollBar:vertical {
            background-color: #1e1e1e;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background-color: #424242;
            min-height: 20px;
            border-radius: 3px;
            margin: 2px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #525252;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
    """


if __name__ == "__main__":
    main()
