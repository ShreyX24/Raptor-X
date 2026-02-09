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
    " ____   _    ____ _____ ___  ____    __  __",
    "|  _ \\ / \\  |  _ \\_   _/ _ \\|  _ \\   \\ \\/ /",
    "| |_) / _ \\ | |_) || || | | | |_) |   \\  / ",
    "|  _ < ___ \\|  __/ | || |_| |  _ <    /  \\ ",
    "|_| \\_\\_/ \\_\\_|    |_| \\___/|_| \\_\\  /_/\\_\\",
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


def _setup_ssh_server(master_url: str = None) -> bool:
    """
    Setup OpenSSH Server for bidirectional SSH with Master.

    Args:
        master_url: Optional Master server URL (e.g., "192.168.50.100:5000")
                   Used to fetch and install the Master's public SSH key.

    Returns:
        True if setup was successful
    """
    print()
    print("=" * 50)
    print("Setting up OpenSSH Server for Master connectivity...")
    print("=" * 50)
    print()

    try:
        from .ssh_setup import get_ssh_setup
        ssh_setup = get_ssh_setup(master_url=master_url)

        # Pass master_url to run_full_setup for key fetching
        result = ssh_setup.run_full_setup(master_url=master_url)

        # Print results
        for step in result.get("steps", []):
            status_icon = "\033[92m[OK]\033[0m" if step["success"] else "\033[91m[FAIL]\033[0m"
            print(f"  {status_icon} {step['step']}: {step['message']}")

        print()

        if result.get("success"):
            print("\033[92mSSH setup completed!\033[0m")
            status = result.get("status", {})
            print(f"  sshd running: {status.get('sshd_running', False)}")
            print(f"  sshd enabled: {status.get('sshd_enabled', False)}")
            print(f"  authorized_keys: {status.get('authorized_keys_path', 'N/A')}")
            print(f"  keys installed: {status.get('authorized_keys_count', 0)}")
            return True
        else:
            print(f"\033[93mSSH setup had issues: {result.get('error', 'Unknown')}\033[0m")
            print("  (SUT client will still work, but Master may not be able to SSH in)")
            return False

    except Exception as e:
        print(f"\033[93mSSH setup skipped: {e}\033[0m")
        print("  (SUT client will still work, but Master may not be able to SSH in)")
        return False


def _install_scheduled_task(master_override: str = None) -> bool:
    """
    Install SUT client as a Windows Scheduled Task with highest privileges.
    Also sets up OpenSSH Server for bidirectional SSH with Master.

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

    # Step 1: Setup SSH Server (while we have admin privileges)
    # Convert master_override (IP:PORT format) to URL for SSH setup
    master_url = None
    if master_override:
        # master_override is in IP:PORT format, convert to URL
        master_url = f"http://{master_override}"
    _setup_ssh_server(master_url=master_url)

    print()
    print("=" * 50)
    print("Creating Scheduled Task...")
    print("=" * 50)
    print()

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
            print(f"\033[92mSUCCESS: Scheduled task '{task_name}' created!\033[0m")
            print(f"Command: {command}")
            print()
            print("The SUT client will now:")
            print("  - Start automatically at user login")
            print("  - Run with admin privileges (no UAC prompt)")
            print("  - Accept SSH connections from Master (for trace pulling)")
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
        "--setup-ssh",
        action="store_true",
        help="Setup OpenSSH Server on this machine for bidirectional SSH with Master"
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

    # Handle SSH setup command
    if args.setup_ssh:
        # Enable ANSI colors on Windows
        _enable_windows_ansi()
        print_banner(__version__)
        print("[SSH SETUP MODE]")
        print()

        # Check for admin (required for OpenSSH setup)
        if sys.platform == "win32" and not _is_admin():
            print("\033[93mWarning: SSH setup requires administrator privileges.\033[0m")
            print("Some steps may fail without elevation.")
            print()

        from .ssh_setup import get_ssh_setup
        ssh_setup = get_ssh_setup()

        print("Running OpenSSH Server setup...")
        print()

        result = ssh_setup.run_full_setup()

        # Print results
        for step in result.get("steps", []):
            status_icon = "\033[92m[OK]\033[0m" if step["success"] else "\033[91m[FAIL]\033[0m"
            print(f"  {status_icon} {step['step']}: {step['message']}")

        print()

        if result.get("success"):
            print("\033[92mSSH setup completed successfully!\033[0m")
            print()
            # Print status
            status = result.get("status", {})
            print("Current status:")
            print(f"  OpenSSH installed: {status.get('openssh_installed', False)}")
            print(f"  sshd running: {status.get('sshd_running', False)}")
            print(f"  sshd enabled: {status.get('sshd_enabled', False)}")
            print(f"  Authorized keys: {status.get('authorized_keys_path', 'N/A')}")
            print(f"  Keys count: {status.get('authorized_keys_count', 0)}")
            print()
            print("Master can now connect to this SUT via SSH.")
            print("Run 'sut-client' normally to register with Master and exchange keys.")
        else:
            print(f"\033[91mSSH setup failed: {result.get('error', 'Unknown error')}\033[0m")

        sys.exit(0 if result.get("success") else 1)

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
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            force=True  # Override any prior basicConfig calls
        )
        # Ensure root logger and all child loggers are at DEBUG
        logging.getLogger().setLevel(logging.DEBUG)
        print("[DEBUG MODE ENABLED - verbose logging active for all modules]")
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
