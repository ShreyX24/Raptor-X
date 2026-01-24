"""
RPX SUT Client
System Under Test client for receiving and applying game configuration presets
Game launch and input automation for Raptor X platform
"""

import argparse
import sys
import logging

__version__ = "0.3.0"
__author__ = "RPX Team"

# RAPTOR X ASCII Banner (with purple-to-white gradient)
RPX_BANNER_LINES = [
    "██████╗  █████╗ ██████╗ ████████╗ ██████╗ ██████╗     ██╗  ██╗",
    "██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗    ╚██╗██╔╝",
    "██████╔╝███████║██████╔╝   ██║   ██║   ██║██████╔╝     ╚███╔╝",
    "██╔══██╗██╔══██║██╔═══╝    ██║   ██║   ██║██╔══██╗     ██╔██╗",
    "██║  ██║██║  ██║██║        ██║   ╚██████╔╝██║  ██║    ██╔╝ ██╗",
    "╚═╝  ╚═╝╚═╝  ╚═╝╚═╝        ╚═╝    ╚═════╝ ╚═╝  ╚═╝    ╚═╝  ╚═╝",
]

# ANSI 256-color gradient: purple (93) -> light purple -> white (231)
GRADIENT_COLORS = [93, 135, 141, 183, 189, 231]
RESET = "\033[0m"


def _enable_windows_ansi():
    """Enable ANSI escape sequences on Windows Command Prompt"""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # Get handle to stdout
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        # Get current console mode
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        # Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004)
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        return True
    except Exception:
        return False


def print_banner(version: str):
    """Print the RAPTOR X banner with purple-to-white gradient"""
    # Enable ANSI colors on Windows
    _enable_windows_ansi()

    print()  # Empty line before banner
    for i, line in enumerate(RPX_BANNER_LINES):
        color_code = GRADIENT_COLORS[i] if i < len(GRADIENT_COLORS) else 231
        print(f"\033[38;5;{color_code}m{line}{RESET}")
    print()
    # Version line in white
    version_text = f"SUT Client v{version}"
    padding = (len(RPX_BANNER_LINES[0]) - len(version_text)) // 2
    print(f"\033[97m{' ' * padding}{version_text}{RESET}")
    print()


def _set_window_title(title: str):
    """Set the console window title (Windows)"""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(title)


def _is_admin() -> bool:
    """Check if running with admin privileges on Windows"""
    if sys.platform != "win32":
        return True  # Not applicable on non-Windows
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _run_as_admin() -> bool:
    """Re-launch the current script with admin privileges via UAC prompt"""
    if sys.platform != "win32":
        return False

    import ctypes
    import shutil

    # For pip-installed entry points, we need to run via cmd.exe to get a proper
    # console window that stays open. ShellExecuteW with an .exe directly may not
    # create a visible console.
    sut_client_exe = shutil.which('sut-client')
    if not sut_client_exe:
        # Fallback: try sys.argv[0] if it's an exe
        if sys.argv[0].lower().endswith('.exe'):
            sut_client_exe = sys.argv[0]
        else:
            # Last resort: run as python module
            executable = sys.executable
            params = f'-m sut_client {" ".join(sys.argv[1:])}'
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", executable, params, None, 1
            )
            return ret > 32

    # Use cmd.exe to run the sut-client, which ensures a console window stays open
    # Pass along any command-line arguments (like --master)
    executable = "cmd.exe"
    extra_args = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else ''
    params = f'/k "{sut_client_exe}" {extra_args}'.strip()

    # ShellExecute with "runas" verb triggers UAC
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,           # hwnd
        "runas",        # lpOperation (triggers UAC)
        executable,     # lpFile
        params,         # lpParameters
        None,           # lpDirectory
        1               # nShowCmd (SW_SHOWNORMAL)
    )

    # Return value > 32 means success
    return ret > 32


def _install_scheduled_task(master_override: str = None) -> bool:
    """
    Install SUT client as a Windows Scheduled Task with highest privileges.
    This allows running elevated without UAC prompts after initial setup.

    Args:
        master_override: Optional master server IP:PORT to pass to the task

    Returns:
        True if task was created successfully
    """
    if sys.platform != "win32":
        print("Scheduled task installation only supported on Windows")
        return False

    import subprocess
    import shutil
    import os

    task_name = "SUT-Client"

    # Find the sut-client executable
    sut_client_exe = shutil.which('sut-client')
    if not sut_client_exe:
        if sys.argv[0].lower().endswith('.exe'):
            sut_client_exe = sys.argv[0]
        else:
            print("Error: Could not find sut-client executable")
            return False

    # Build the command with optional master override
    extra_args = f"--master {master_override}" if master_override else ""
    command = f'"{sut_client_exe}" {extra_args}'.strip()

    # Create the scheduled task using schtasks
    # /RL HIGHEST = Run with highest privileges (no UAC)
    # /SC ONLOGON = Run at user logon
    # /IT = Interactive only (shows console window)
    try:
        # First, delete any existing task
        subprocess.run(
            ['schtasks', '/Delete', '/TN', task_name, '/F'],
            capture_output=True,
            check=False  # Don't fail if task doesn't exist
        )

        # Create the new task
        result = subprocess.run([
            'schtasks', '/Create',
            '/TN', task_name,
            '/TR', command,
            '/SC', 'ONLOGON',
            '/RL', 'HIGHEST',
            '/IT',
            '/F'  # Force overwrite
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print(f"SUCCESS: Scheduled task '{task_name}' created!")
            print(f"Command: {command}")
            print()
            print("The SUT client will now:")
            print("  - Start automatically at user login")
            print("  - Run with admin privileges (no UAC prompt)")
            print()
            print("To start immediately without relogging:")
            print(f"  schtasks /Run /TN {task_name}")
            print()
            print("To uninstall:")
            print("  sut-client --uninstall-service")
            return True
        else:
            print(f"Error creating scheduled task: {result.stderr}")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False


def _uninstall_scheduled_task() -> bool:
    """
    Remove the SUT client scheduled task.

    Returns:
        True if task was removed successfully
    """
    if sys.platform != "win32":
        print("Scheduled task uninstallation only supported on Windows")
        return False

    import subprocess

    task_name = "SUT-Client"

    try:
        result = subprocess.run(
            ['schtasks', '/Delete', '/TN', task_name, '/F'],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"SUCCESS: Scheduled task '{task_name}' removed!")
            return True
        else:
            print(f"Error removing scheduled task: {result.stderr}")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False


def _run_scheduled_task() -> bool:
    """
    Run the SUT client via the scheduled task (bypasses UAC).

    Returns:
        True if task was started successfully
    """
    if sys.platform != "win32":
        return False

    import subprocess

    task_name = "SUT-Client"

    try:
        result = subprocess.run(
            ['schtasks', '/Run', '/TN', task_name],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"Started SUT client via scheduled task (elevated, no UAC)")
            return True
        else:
            # Task might not exist
            return False

    except Exception:
        return False


def main():
    """Main entry point for the SUT client"""
    # Parse arguments first (before admin elevation so args are passed through)
    parser = argparse.ArgumentParser(
        description="Raptor X SUT Client - System Under Test client for preset management and game automation",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--master",
        type=str,
        metavar="IP:PORT",
        help="Connect directly to master server at IP:PORT (e.g., 10.48.95.166:5000). "
             "Bypasses UDP discovery. Useful for cross-subnet deployments."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging for verbose output"
    )
    parser.add_argument(
        "--install-service",
        action="store_true",
        help="Install as a Windows Scheduled Task (runs at login with admin, no UAC prompt)"
    )
    parser.add_argument(
        "--uninstall-service",
        action="store_true",
        help="Remove the Windows Scheduled Task"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update SUT client from Master server via SSH"
    )
    parser.add_argument(
        "--master-ip",
        type=str,
        metavar="IP",
        help="Master server IP for updates (used with --update)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"sut-client {__version__}"
    )
    args = parser.parse_args()

    # Handle update command
    if args.update:
        # Enable ANSI colors on Windows
        _enable_windows_ansi()
        print_banner(__version__)

        # Get master IP from args or try to extract from --master
        master_ip = args.master_ip
        if not master_ip and args.master:
            master_ip = args.master.split(':')[0]

        if not master_ip:
            print("\033[91mError: --master-ip or --master required for updates\033[0m")
            print()
            print("Usage: sut-client --update --master-ip 192.168.0.100")
            print("   or: sut-client --update --master 192.168.0.100:5001")
            sys.exit(1)

        from .update_handler import UpdateHandler
        handler = UpdateHandler(__version__)
        success = handler.execute_update(master_ip)
        sys.exit(0 if success else 1)

    # Handle install/uninstall service commands (requires admin)
    if args.install_service:
        if not _is_admin():
            print("Installing service requires administrator privileges.")
            print("Elevating...")
            # Re-run with admin, keeping the --install-service flag
            if _run_as_admin():
                sys.exit(0)
            else:
                print("Error: Could not elevate to admin")
                sys.exit(1)
        else:
            success = _install_scheduled_task(args.master)
            sys.exit(0 if success else 1)

    if args.uninstall_service:
        if not _is_admin():
            print("Uninstalling service requires administrator privileges.")
            print("Elevating...")
            if _run_as_admin():
                sys.exit(0)
            else:
                print("Error: Could not elevate to admin")
                sys.exit(1)
        else:
            success = _uninstall_scheduled_task()
            sys.exit(0 if success else 1)

    # Check for admin and elevate if needed (Windows only)
    if sys.platform == "win32" and not _is_admin():
        # First, try to run via scheduled task (no UAC)
        if _run_scheduled_task():
            print("SUT client started via scheduled task (elevated, no UAC)")
            sys.exit(0)

        # Fall back to UAC elevation
        print("Requesting administrator privileges...")
        if _run_as_admin():
            # Successfully launched elevated process, exit this one
            sys.exit(0)
        else:
            print("Warning: Could not elevate to admin. Some features (PC rename, registry) may not work.")
            print("To get full functionality, right-click and 'Run as administrator'")
            print("Or install as service: sut-client --install-service")
            print()

    # Set window title
    _set_window_title("sut-client")

    # Print RAPTOR X banner with gradient
    print_banner(__version__)

    # Set up logging level based on --debug flag
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        print("[DEBUG MODE ENABLED]")
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # Set DPI awareness for accurate screen coordinates (Windows)
    from .hardware import set_dpi_awareness
    set_dpi_awareness()

    from .service import start_service
    start_service(master_override=args.master)


__all__ = [
    "__version__",
    "main",
]
