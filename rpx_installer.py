#!/usr/bin/env python3
"""
RPX Unified Installer

Single source of truth for installing all RPX services, dependencies, and SSH setup.
Run via: python rpx_installer.py
Or via: setup.bat (which calls this script)
"""

import subprocess
import sys
import os
from pathlib import Path
from typing import Tuple, Optional, Callable, List
import shutil


class Colors:
    """ANSI color codes for terminal output"""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"


def print_header(text: str):
    """Print a section header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")


def print_step(step: int, total: int, text: str):
    """Print a step indicator"""
    print(f"\n{Colors.BOLD}[{step}/{total}] {text}{Colors.RESET}")


def print_ok(text: str):
    """Print success message"""
    print(f"  {Colors.GREEN}[OK]{Colors.RESET} {text}")


def print_warning(text: str):
    """Print warning message"""
    print(f"  {Colors.YELLOW}[WARNING]{Colors.RESET} {text}")


def print_error(text: str):
    """Print error message"""
    print(f"  {Colors.RED}[ERROR]{Colors.RESET} {text}")


def print_info(text: str):
    """Print info message"""
    print(f"  {Colors.BLUE}[INFO]{Colors.RESET} {text}")


def run_command(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 300) -> Tuple[bool, str, str]:
    """
    Run a command and return (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except FileNotFoundError:
        return False, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, "", str(e)


def run_powershell(command: str, timeout: int = 120) -> Tuple[bool, str, str]:
    """Run a PowerShell command and return (success, stdout, stderr)"""
    return run_command(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        timeout=timeout
    )


class SSHSetup:
    """OpenSSH Server setup for Windows"""

    AUTHORIZED_KEYS_PATH = Path("C:/ProgramData/ssh/administrators_authorized_keys")
    SSH_CONFIG_DIR = Path("C:/ProgramData/ssh")

    @staticmethod
    def is_windows() -> bool:
        return sys.platform == "win32"

    @staticmethod
    def is_ssh_installed() -> bool:
        """Check if OpenSSH Server capability is installed"""
        success, stdout, _ = run_powershell(
            "Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*' | Select-Object -ExpandProperty State"
        )
        return success and "Installed" in stdout

    @staticmethod
    def is_sshd_running() -> bool:
        """Check if sshd service is running"""
        success, stdout, _ = run_powershell(
            "(Get-Service sshd -ErrorAction SilentlyContinue).Status"
        )
        return success and "Running" in stdout

    @staticmethod
    def is_sshd_enabled() -> bool:
        """Check if sshd service is set to automatic startup"""
        success, stdout, _ = run_powershell(
            "(Get-Service sshd -ErrorAction SilentlyContinue).StartType"
        )
        return success and "Automatic" in stdout

    @classmethod
    def setup(cls) -> Tuple[bool, str]:
        """
        Complete SSH server setup:
        1. Check if already installed and running -> skip if so
        2. Install OpenSSH Server capability if needed
        3. Start sshd service if stopped
        4. Enable automatic startup
        5. Create authorized_keys with proper ACL

        Returns:
            (success, message)
        """
        if not cls.is_windows():
            print_info("SSH setup skipped (Windows only)")
            return True, "Skipped (not Windows)"

        try:
            # Check current status
            installed = cls.is_ssh_installed()
            running = cls.is_sshd_running()
            enabled = cls.is_sshd_enabled()

            print_info(f"SSH Status: installed={installed}, running={running}, enabled={enabled}")

            # Step 1: Install OpenSSH Server if not installed
            if not installed:
                print_info("Installing OpenSSH Server (this may take a minute)...")
                success, stdout, stderr = run_powershell(
                    "Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0",
                    timeout=300
                )
                if not success:
                    return False, f"Failed to install OpenSSH Server: {stderr}"
                print_ok("OpenSSH Server installed")
            else:
                print_ok("OpenSSH Server already installed")

            # Step 2: Start sshd service if not running
            if not cls.is_sshd_running():
                print_info("Starting sshd service...")
                success, stdout, stderr = run_powershell("Start-Service sshd")
                if not success:
                    return False, f"Failed to start sshd: {stderr}"
                print_ok("sshd service started")
            else:
                print_ok("sshd service already running")

            # Step 3: Enable automatic startup if not enabled
            if not cls.is_sshd_enabled():
                print_info("Enabling sshd automatic startup...")
                success, stdout, stderr = run_powershell(
                    "Set-Service -Name sshd -StartupType 'Automatic'"
                )
                if not success:
                    return False, f"Failed to enable sshd: {stderr}"
                print_ok("sshd set to automatic startup (survives restart)")
            else:
                print_ok("sshd already set to automatic startup")

            # Step 4: Create authorized_keys file if it doesn't exist
            if not cls.AUTHORIZED_KEYS_PATH.exists():
                print_info("Creating authorized_keys file...")
                cls.SSH_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                cls.AUTHORIZED_KEYS_PATH.touch()
                print_ok("Created authorized_keys file")
            else:
                print_ok("authorized_keys file exists")

            # Step 5: Fix ACL permissions
            print_info("Setting file permissions...")
            cls._fix_authorized_keys_acl()
            print_ok("File permissions set")

            return True, "OpenSSH Server setup complete"

        except Exception as e:
            return False, str(e)

    @classmethod
    def _fix_authorized_keys_acl(cls) -> bool:
        """Set proper ACL on authorized_keys file (Administrators and SYSTEM only)"""
        if not cls.AUTHORIZED_KEYS_PATH.exists():
            return False

        result = subprocess.run([
            "icacls.exe",
            str(cls.AUTHORIZED_KEYS_PATH),
            "/inheritance:r",
            "/grant", "*S-1-5-32-544:F",  # Administrators
            "/grant", "SYSTEM:F"
        ], capture_output=True, text=True)

        return result.returncode == 0


class RPXInstaller:
    """Main installer class"""

    # Python services to install (relative to project root)
    PYTHON_SERVICES = [
        ("Gemma Backend", "Gemma/backend"),
        ("SUT Discovery Service", "sut_discovery_service"),
        ("Queue Service", "queue_service"),
        ("Service Manager", "service_manager"),
        ("Preset Manager", "preset-manager"),
        ("SUT Client", "sut_client"),
    ]

    # OmniParser package (separate due to special handling)
    OMNIPARSER_DIR = "omniparser-server"

    # Frontend packages to npm install
    FRONTEND_PACKAGES = [
        ("Gemma Admin", "Gemma/admin"),
        ("Preset Manager Admin", "preset-manager/admin"),
    ]

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def install_python_service(self, name: str, rel_path: str) -> bool:
        """Install a Python service in editable mode"""
        service_dir = self.project_dir / rel_path
        pyproject = service_dir / "pyproject.toml"

        if not service_dir.exists():
            print_warning(f"Directory not found: {service_dir}")
            return False

        if not pyproject.exists():
            print_warning(f"No pyproject.toml in {service_dir}")
            return False

        print_info(f"Installing {name}...")
        success, stdout, stderr = run_command(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            cwd=service_dir,
            timeout=120
        )

        if success:
            print_ok(f"{name} installed")
            return True
        else:
            print_error(f"Failed to install {name}: {stderr}")
            return False

    def install_frontend(self, name: str, rel_path: str) -> bool:
        """Install npm dependencies for a frontend"""
        frontend_dir = self.project_dir / rel_path
        package_json = frontend_dir / "package.json"

        if not package_json.exists():
            print_warning(f"No package.json in {frontend_dir}")
            return False

        print_info(f"Installing {name} dependencies...")

        # Check if npm is available
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"

        success, stdout, stderr = run_command(
            [npm_cmd, "install"],
            cwd=frontend_dir,
            timeout=300
        )

        if success:
            print_ok(f"{name} dependencies installed")
            return True
        else:
            print_error(f"Failed to install {name}: {stderr}")
            return False

    def install_omniparser(self) -> bool:
        """Install OmniParser server package"""
        # Try both naming conventions
        omni_dirs = [
            self.project_dir / "omniparser-server",
            self.project_dir / "Omniparser server",
        ]

        omni_dir = None
        for d in omni_dirs:
            if d.exists():
                omni_dir = d
                break

        if not omni_dir:
            print_warning("OmniParser directory not found")
            return False

        # Look for pyproject.toml in omnitool/omniparserserver or parent
        pyproject_locations = [
            omni_dir / "omnitool" / "omniparserserver" / "pyproject.toml",
            omni_dir / "pyproject.toml",
        ]

        for pyproject in pyproject_locations:
            if pyproject.exists():
                print_info(f"Installing OmniParser Server from {pyproject.parent}...")
                success, stdout, stderr = run_command(
                    [sys.executable, "-m", "pip", "install", "-e", "."],
                    cwd=pyproject.parent,
                    timeout=120
                )
                if success:
                    print_ok("OmniParser Server installed")
                    return True
                else:
                    print_error(f"Failed to install OmniParser: {stderr}")
                    return False

        print_warning("OmniParser pyproject.toml not found")
        return False

    def run_full_install(self, skip_ssh: bool = False, skip_npm: bool = False) -> bool:
        """Run the complete installation process"""
        print_header("RPX - Raptor X Unified Installer")

        # Calculate total steps
        total_steps = 1  # SSH
        if not skip_npm:
            total_steps += 1  # npm
        total_steps += 1  # Python services

        current_step = 0
        all_success = True

        # Step 1: SSH Setup (Windows only)
        current_step += 1
        print_step(current_step, total_steps, "OpenSSH Server Setup")

        if skip_ssh:
            print_info("SSH setup skipped (--skip-ssh flag)")
        elif not SSHSetup.is_windows():
            print_info("SSH setup skipped (Windows only)")
        else:
            success, message = SSHSetup.setup()
            if not success:
                print_error(f"SSH setup failed: {message}")
                all_success = False
            else:
                print_ok(message)

        # Step 2: Frontend npm install
        if not skip_npm:
            current_step += 1
            print_step(current_step, total_steps, "Installing Frontend Dependencies (npm)")

            for name, rel_path in self.FRONTEND_PACKAGES:
                if not self.install_frontend(name, rel_path):
                    all_success = False

        # Step 3: Python services
        current_step += 1
        print_step(current_step, total_steps, "Installing Python Services")

        for name, rel_path in self.PYTHON_SERVICES:
            if not self.install_python_service(name, rel_path):
                all_success = False

        # Also install OmniParser
        self.install_omniparser()

        # Summary
        print_header("Installation Complete")

        if all_success:
            print_ok("All components installed successfully!")
        else:
            print_warning("Some components failed to install. Check the output above.")

        print()
        print(f"  {Colors.CYAN}To start RPX:{Colors.RESET}")
        print(f"    Double-click: start-rpx.bat")
        print(f"    Or run: rpx-manager")
        print()

        return all_success


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="RPX Unified Installer - Install all services and dependencies"
    )
    parser.add_argument(
        "--skip-ssh",
        action="store_true",
        help="Skip OpenSSH server setup"
    )
    parser.add_argument(
        "--skip-npm",
        action="store_true",
        help="Skip npm install for frontends"
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="Project root directory (defaults to script location)"
    )
    parser.add_argument(
        "--ssh-only",
        action="store_true",
        help="Only run SSH setup (useful for troubleshooting)"
    )

    args = parser.parse_args()

    # Determine project directory
    if args.project_dir:
        project_dir = args.project_dir.resolve()
    else:
        # Use script location as project root
        project_dir = Path(__file__).parent.resolve()

    if not project_dir.exists():
        print_error(f"Project directory not found: {project_dir}")
        sys.exit(1)

    # SSH-only mode
    if args.ssh_only:
        print_header("OpenSSH Server Setup")
        if not SSHSetup.is_windows():
            print_info("SSH setup only supported on Windows")
            sys.exit(0)

        success, message = SSHSetup.setup()
        if success:
            print_ok(message)
            sys.exit(0)
        else:
            print_error(message)
            sys.exit(1)

    # Full install
    installer = RPXInstaller(project_dir)
    success = installer.run_full_install(
        skip_ssh=args.skip_ssh,
        skip_npm=args.skip_npm
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
