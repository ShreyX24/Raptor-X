#!/usr/bin/env python3
"""
SSH Operations CLI Tool for RPX SUT Client.

Standalone CLI that runs in a separate terminal for:
- Pulling updates from Master
- Pushing logs/traces to Master
- SSH key setup

Usage:
    ssh_ops update --master 192.168.0.100
    ssh_ops push-logs --master 192.168.0.100 --path ./logs/
    ssh_ops setup-keys

This tool is designed to be called via subprocess from SUT Client,
opening in a new terminal window with progress display.
"""

import argparse
import subprocess
import sys
import os
import time
import shutil
import socket
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

# ANSI color codes
class Colors:
    PURPLE = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def enable_windows_ansi():
    """Enable ANSI escape sequences on Windows"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def set_window_title(title: str):
    """Set console window title"""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except Exception:
            pass


def print_banner(operation: str):
    """Print operation banner"""
    banner = f"""
{Colors.PURPLE}╔══════════════════════════════════════════════════════════════╗
║{Colors.WHITE}                    RAPTOR X SSH OPERATIONS                    {Colors.PURPLE}║
╠══════════════════════════════════════════════════════════════╣
║{Colors.CYAN}  Operation: {Colors.WHITE}{operation:<49}{Colors.PURPLE}║
║{Colors.CYAN}  Time:      {Colors.WHITE}{datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<49}{Colors.PURPLE}║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)


def print_status(message: str, status: str = "info"):
    """Print colored status message"""
    colors = {
        "info": Colors.CYAN,
        "success": Colors.GREEN,
        "warning": Colors.YELLOW,
        "error": Colors.RED,
        "progress": Colors.WHITE,
    }
    color = colors.get(status, Colors.WHITE)
    symbol = {"info": "→", "success": "✓", "warning": "!", "error": "✗", "progress": "○"}
    print(f"{color}{symbol.get(status, '→')}{Colors.RESET} {message}")


def print_progress_bar(current: int, total: int, prefix: str = "", width: int = 40):
    """Print a progress bar"""
    if total == 0:
        percent = 100
    else:
        percent = int((current / total) * 100)

    filled = int(width * current / total) if total > 0 else width
    bar = "█" * filled + "░" * (width - filled)

    # Format size
    def format_size(size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    size_str = f"{format_size(current)} / {format_size(total)}"

    print(f"\r{Colors.CYAN}{prefix}{Colors.WHITE} [{Colors.GREEN}{bar}{Colors.WHITE}] {percent}% {size_str}  ", end="", flush=True)


def countdown_close(seconds: int = 5):
    """Countdown before closing terminal"""
    print()
    for i in range(seconds, 0, -1):
        print(f"\r{Colors.YELLOW}Closing in {i}...{Colors.RESET}  ", end="", flush=True)
        time.sleep(1)
    print(f"\r{Colors.GREEN}Done!{Colors.RESET}              ")


def get_ssh_key_path() -> Path:
    """Get path to SSH private key"""
    return Path.home() / ".ssh" / "id_ed25519"


def check_ssh_connection(master_ip: str, username: str = None, timeout: int = 10) -> Tuple[bool, str]:
    """Test SSH connection to Master"""
    if username is None:
        import getpass
        username = getpass.getuser()

    try:
        result = subprocess.run([
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", f"ConnectTimeout={timeout}",
            f"{username}@{master_ip}",
            "echo SSH_OK"
        ], capture_output=True, text=True, timeout=timeout + 5)

        if result.returncode == 0 and "SSH_OK" in result.stdout:
            return True, "Connection successful"
        else:
            return False, result.stderr.strip() or "Connection failed"
    except subprocess.TimeoutExpired:
        return False, "Connection timed out"
    except FileNotFoundError:
        return False, "SSH client not found"
    except Exception as e:
        return False, str(e)


def get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes"""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total


# =============================================================================
# UPDATE COMMAND
# =============================================================================

def cmd_update(args):
    """Pull updates from Master server"""
    set_window_title("RPX Update")
    print_banner("PULLING UPDATES FROM MASTER")

    master_ip = args.master
    username = args.user or os.getenv("USERNAME", "user")

    print_status(f"Master server: {master_ip}", "info")
    print_status(f"Username: {username}", "info")
    print()

    # Step 1: Check SSH connection
    print_status("Testing SSH connection...", "progress")
    success, msg = check_ssh_connection(master_ip, username)
    if not success:
        print_status(f"SSH connection failed: {msg}", "error")
        print()
        print_status("Make sure:", "info")
        print(f"  1. SSH key is registered with Master")
        print(f"  2. Master's OpenSSH server is running")
        print(f"  3. Network connectivity to {master_ip}")
        print()
        input("Press Enter to close...")
        return 1

    print_status("SSH connection OK", "success")
    print()

    # Step 2: Determine paths
    # SUT Client is installed at: D:\Code\Gemma\sut_client (or similar)
    local_sut_client = Path(__file__).parent.parent.parent  # Go up from ssh_ops.py
    remote_path = args.remote_path or "/Code/Gemma/RPX/sut_client"

    print_status(f"Local path: {local_sut_client}", "info")
    print_status(f"Remote path: {remote_path}", "info")
    print()

    # Step 3: Create backup of current installation
    backup_dir = local_sut_client.parent / f"sut_client_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print_status(f"Creating backup: {backup_dir.name}", "progress")
    try:
        shutil.copytree(local_sut_client, backup_dir, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
        print_status("Backup created", "success")
    except Exception as e:
        print_status(f"Backup failed: {e}", "warning")
    print()

    # Step 4: Pull updates using SCP
    print_status("Pulling updates from Master...", "progress")
    print()

    # Use SCP with progress display (-v for verbose, but native progress is shown automatically)
    scp_cmd = [
        "scp",
        "-r",  # Recursive
        "-o", "StrictHostKeyChecking=no",
        f"{username}@{master_ip}:{remote_path}/src",
        str(local_sut_client)
    ]

    print(f"{Colors.CYAN}Command: {' '.join(scp_cmd)}{Colors.RESET}")
    print()

    try:
        # Run SCP - it shows its own progress
        result = subprocess.run(scp_cmd, timeout=600)  # 10 minute timeout

        if result.returncode == 0:
            print()
            print_status("Update downloaded successfully!", "success")
        else:
            print()
            print_status(f"SCP failed with exit code {result.returncode}", "error")
            input("Press Enter to close...")
            return 1

    except subprocess.TimeoutExpired:
        print_status("Transfer timed out", "error")
        input("Press Enter to close...")
        return 1
    except Exception as e:
        print_status(f"Transfer error: {e}", "error")
        input("Press Enter to close...")
        return 1

    # Step 5: Clear cache
    print()
    print_status("Clearing Python cache...", "progress")
    cache_cleared = 0
    for cache_dir in local_sut_client.rglob("__pycache__"):
        try:
            shutil.rmtree(cache_dir)
            cache_cleared += 1
        except Exception:
            pass
    print_status(f"Cleared {cache_cleared} cache directories", "success")

    # Step 6: Reinstall package
    print()
    print_status("Reinstalling package...", "progress")
    try:
        result = subprocess.run(
            ["pip", "install", "-e", "."],
            cwd=str(local_sut_client),
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            print_status("Package reinstalled", "success")
        else:
            print_status(f"pip install warning: {result.stderr[:100]}", "warning")
    except Exception as e:
        print_status(f"pip install failed: {e}", "warning")

    # Step 7: Call restarter
    print()
    print_status("Scheduling restart...", "progress")

    restarter_path = local_sut_client / "restarter.bat"
    if restarter_path.exists():
        # Start restarter in background (it will wait and restart sut-client)
        subprocess.Popen(
            ["cmd", "/c", "start", "/min", str(restarter_path)],
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )
        print_status("Restarter scheduled - SUT client will restart in 5 seconds", "success")
    else:
        print_status("Restarter not found - please restart sut-client manually", "warning")

    print()
    print(f"{Colors.GREEN}{'═' * 60}{Colors.RESET}")
    print(f"{Colors.GREEN}  UPDATE COMPLETE!{Colors.RESET}")
    print(f"{Colors.GREEN}{'═' * 60}{Colors.RESET}")

    countdown_close(5)
    return 0


# =============================================================================
# PUSH-LOGS COMMAND
# =============================================================================

def cmd_push_logs(args):
    """Push logs/traces to Master server"""
    set_window_title("RPX Push Logs")
    print_banner("PUSHING LOGS TO MASTER")

    master_ip = args.master
    username = args.user or os.getenv("USERNAME", "user")
    log_path = Path(args.path)

    if not log_path.exists():
        print_status(f"Log path not found: {log_path}", "error")
        input("Press Enter to close...")
        return 1

    print_status(f"Master server: {master_ip}", "info")
    print_status(f"Log path: {log_path}", "info")

    # Calculate size
    if log_path.is_dir():
        total_size = get_directory_size(log_path)
    else:
        total_size = log_path.stat().st_size

    def format_size(size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    print_status(f"Total size: {format_size(total_size)}", "info")
    print()

    # Test SSH connection
    print_status("Testing SSH connection...", "progress")
    success, msg = check_ssh_connection(master_ip, username)
    if not success:
        print_status(f"SSH connection failed: {msg}", "error")
        input("Press Enter to close...")
        return 1
    print_status("SSH connection OK", "success")
    print()

    # Remote destination
    hostname = socket.gethostname()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    remote_dest = args.remote_path or f"/Code/Gemma/RPX/logs/{hostname}/{timestamp}"

    print_status(f"Remote destination: {remote_dest}", "info")
    print()

    # Create remote directory
    print_status("Creating remote directory...", "progress")
    ssh_mkdir = subprocess.run([
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        f"{username}@{master_ip}",
        f"mkdir -p {remote_dest}"
    ], capture_output=True)

    if ssh_mkdir.returncode != 0:
        print_status("Could not create remote directory", "warning")

    # Push logs using SCP
    print_status("Uploading logs...", "progress")
    print()

    scp_cmd = [
        "scp",
        "-r",
        "-o", "StrictHostKeyChecking=no",
        str(log_path),
        f"{username}@{master_ip}:{remote_dest}/"
    ]

    print(f"{Colors.CYAN}Command: {' '.join(scp_cmd)}{Colors.RESET}")
    print()

    try:
        result = subprocess.run(scp_cmd, timeout=1800)  # 30 minute timeout for large logs

        if result.returncode == 0:
            print()
            print_status("Logs uploaded successfully!", "success")
        else:
            print()
            print_status(f"SCP failed with exit code {result.returncode}", "error")
            input("Press Enter to close...")
            return 1

    except subprocess.TimeoutExpired:
        print_status("Transfer timed out", "error")
        input("Press Enter to close...")
        return 1
    except Exception as e:
        print_status(f"Transfer error: {e}", "error")
        input("Press Enter to close...")
        return 1

    print()
    print(f"{Colors.GREEN}{'═' * 60}{Colors.RESET}")
    print(f"{Colors.GREEN}  LOGS UPLOADED SUCCESSFULLY!{Colors.RESET}")
    print(f"{Colors.GREEN}  Location: {master_ip}:{remote_dest}{Colors.RESET}")
    print(f"{Colors.GREEN}{'═' * 60}{Colors.RESET}")

    countdown_close(5)
    return 0


# =============================================================================
# SETUP-KEYS COMMAND
# =============================================================================

def cmd_setup_keys(args):
    """Generate SSH keys and display for manual registration"""
    set_window_title("RPX SSH Key Setup")
    print_banner("SSH KEY SETUP")

    key_path = get_ssh_key_path()
    pub_key_path = key_path.with_suffix(".pub")

    # Check if key exists
    if key_path.exists() and pub_key_path.exists():
        print_status("SSH key pair already exists", "info")
        print_status(f"Private key: {key_path}", "info")
        print_status(f"Public key: {pub_key_path}", "info")
    else:
        # Generate new key
        print_status("Generating new SSH key pair...", "progress")

        ssh_dir = key_path.parent
        ssh_dir.mkdir(mode=0o700, exist_ok=True)

        hostname = socket.gethostname()
        comment = f"sut-client@{hostname}"

        result = subprocess.run([
            "ssh-keygen",
            "-t", "ed25519",
            "-N", "",  # No passphrase
            "-f", str(key_path),
            "-C", comment
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print_status("SSH key pair generated!", "success")
        else:
            print_status(f"Key generation failed: {result.stderr}", "error")
            input("Press Enter to close...")
            return 1

    # Display public key
    print()
    print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")
    print(f"{Colors.WHITE}Your public key:{Colors.RESET}")
    print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")

    try:
        public_key = pub_key_path.read_text().strip()
        print(f"{Colors.GREEN}{public_key}{Colors.RESET}")
    except Exception as e:
        print_status(f"Could not read public key: {e}", "error")
        input("Press Enter to close...")
        return 1

    print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")
    print()

    # Get fingerprint
    fp_result = subprocess.run(
        ["ssh-keygen", "-lf", str(key_path)],
        capture_output=True, text=True
    )
    if fp_result.returncode == 0:
        print_status(f"Fingerprint: {fp_result.stdout.strip()}", "info")

    print()
    print_status("This key will be automatically registered with Master", "info")
    print_status("when SUT Client connects via WebSocket.", "info")

    print()
    input("Press Enter to close...")
    return 0


# =============================================================================
# MAIN
# =============================================================================

def main():
    enable_windows_ansi()

    parser = argparse.ArgumentParser(
        description="RPX SSH Operations - Standalone CLI for SSH file transfers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    ssh_ops update --master 192.168.0.100
    ssh_ops push-logs --master 192.168.0.100 --path ./logs/
    ssh_ops setup-keys
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Update command
    update_parser = subparsers.add_parser("update", help="Pull updates from Master")
    update_parser.add_argument("--master", "-m", required=True, help="Master server IP")
    update_parser.add_argument("--user", "-u", help="SSH username (default: current user)")
    update_parser.add_argument("--remote-path", "-r", help="Remote sut_client path on Master")

    # Push-logs command
    logs_parser = subparsers.add_parser("push-logs", help="Push logs to Master")
    logs_parser.add_argument("--master", "-m", required=True, help="Master server IP")
    logs_parser.add_argument("--path", "-p", required=True, help="Local log path to push")
    logs_parser.add_argument("--user", "-u", help="SSH username (default: current user)")
    logs_parser.add_argument("--remote-path", "-r", help="Remote destination path")

    # Setup-keys command
    keys_parser = subparsers.add_parser("setup-keys", help="Generate/display SSH keys")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "update":
        return cmd_update(args)
    elif args.command == "push-logs":
        return cmd_push_logs(args)
    elif args.command == "setup-keys":
        return cmd_setup_keys(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
