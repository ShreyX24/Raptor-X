# -*- coding: utf-8 -*-
"""
Modular Backend System for Gemma SUT Communication Platform
"""

import argparse
import subprocess
import sys
import socket
from pathlib import Path

__version__ = "2.0.0"


def _set_window_title(title: str):
    """Set the console window title (Windows)"""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(title)


def _is_port_in_use(port: int) -> bool:
    """Check if a port is already in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect(('127.0.0.1', port))
            return True
        except (ConnectionRefusedError, OSError, socket.timeout):
            return False


def _find_admin_dir() -> Path | None:
    """Find the admin directory for the frontend"""
    import os

    # Option 1: Environment variable override
    if env_admin := os.environ.get("GEMMA_ADMIN_DIR"):
        admin_path = Path(env_admin)
        if admin_path.exists():
            return admin_path

    # Option 2: Current working directory
    cwd_admin = Path.cwd() / "admin"
    if cwd_admin.exists() and (cwd_admin / "package.json").exists():
        return cwd_admin

    # Option 3: Relative to this file (for editable installs)
    package_admin = Path(__file__).parent.parent / "admin"
    if package_admin.exists() and (package_admin / "package.json").exists():
        return package_admin

    # Option 4: Common project locations
    common_paths = [
        Path("D:/Code/Gemma/Gemma/admin"),
        Path.home() / "Code" / "Gemma" / "Gemma" / "admin",
    ]
    for path in common_paths:
        if path.exists() and (path / "package.json").exists():
            return path

    return None


def _launch_frontend():
    """Launch the admin frontend in a new terminal window"""
    if _is_port_in_use(3000):
        print("Frontend already running on port 3000, skipping launch")
        return

    admin_dir = _find_admin_dir()

    if not admin_dir:
        print("Warning: Admin directory not found. Set GEMMA_ADMIN_DIR environment variable.")
        return

    print(f"Launching frontend from: {admin_dir}")

    if sys.platform == "win32":
        subprocess.Popen(
            f'wt -w 0 nt --title "gemma [frontend]" --suppressApplicationTitle -d "{admin_dir}" cmd /k "npm run dev -- --host"',
            shell=True
        )
    else:
        terminals = [
            ["gnome-terminal", "--tab", "--title=gemma (frontend)", "--", "bash", "-c", "npm run dev -- --host; exec bash"],
            ["xterm", "-T", "gemma (frontend)", "-e", "npm run dev -- --host"],
        ]
        for terminal_cmd in terminals:
            try:
                subprocess.Popen(terminal_cmd, cwd=str(admin_dir))
                break
            except FileNotFoundError:
                continue


def main():
    """Main entry point for Gemma backend"""
    parser = argparse.ArgumentParser(
        description="Gemma - Game Automation Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run the service on (default: 5000)"
    )
    parser.add_argument(
        "--with-frontend",
        action="store_true",
        help="Also launch the React frontend in a separate terminal window"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Set window title
    _set_window_title("gemma (backend)")

    # Launch frontend if requested
    if args.with_frontend:
        _launch_frontend()

    # Import and run the actual main with parsed args
    from .main import main as backend_main

    # Patch sys.argv to pass args to backend_main
    sys.argv = ['gemma']
    if args.host != "0.0.0.0":
        sys.argv.extend(['--host', args.host])
    if args.port != 5000:
        sys.argv.extend(['--port', str(args.port)])
    if args.debug:
        sys.argv.append('--debug')
    if args.log_level != "INFO":
        sys.argv.extend(['--log-level', args.log_level])

    backend_main()


__all__ = ["main", "__version__"]