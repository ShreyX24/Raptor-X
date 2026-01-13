"""
SSH Setup Manager for Master Machine.
Handles automated OpenSSH Server installation and key management.
"""

import subprocess
import logging
import sys
from pathlib import Path
from typing import Tuple, Optional, Callable

logger = logging.getLogger(__name__)


class SSHSetupManager:
    """
    Automated OpenSSH Server setup for Master machine.

    Called when user clicks "Install Services" in Settings.
    Handles:
    - Installing OpenSSH Server Windows capability
    - Starting and enabling sshd service
    - Creating administrators_authorized_keys with proper ACL
    """

    # Windows stores admin SSH keys here (not user profile)
    AUTHORIZED_KEYS_PATH = Path("C:/ProgramData/ssh/administrators_authorized_keys")
    SSH_CONFIG_DIR = Path("C:/ProgramData/ssh")

    def __init__(self):
        self._progress_callback: Optional[Callable[[str], None]] = None

    def set_progress_callback(self, callback: Callable[[str], None]):
        """Set callback for progress updates"""
        self._progress_callback = callback

    def _emit_progress(self, message: str):
        """Emit progress message"""
        logger.info(message)
        if self._progress_callback:
            self._progress_callback(message)

    def _run_powershell(self, command: str, timeout: int = 120) -> Tuple[bool, str, str]:
        """
        Run a PowerShell command and return (success, stdout, stderr).
        """
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except FileNotFoundError:
            return False, "", "PowerShell not found"
        except Exception as e:
            return False, "", str(e)

    def is_ssh_server_installed(self) -> bool:
        """Check if OpenSSH Server capability is installed"""
        success, stdout, _ = self._run_powershell(
            "Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*' | Select-Object -ExpandProperty State"
        )
        return success and "Installed" in stdout

    def is_sshd_running(self) -> bool:
        """Check if sshd service is running"""
        success, stdout, _ = self._run_powershell(
            "(Get-Service sshd -ErrorAction SilentlyContinue).Status"
        )
        return success and "Running" in stdout

    def is_sshd_enabled(self) -> bool:
        """Check if sshd service is set to automatic startup"""
        success, stdout, _ = self._run_powershell(
            "(Get-Service sshd -ErrorAction SilentlyContinue).StartType"
        )
        return success and "Automatic" in stdout

    def setup_ssh_server(self) -> Tuple[bool, str]:
        """
        Complete SSH server setup:
        1. Install OpenSSH Server capability (if not installed)
        2. Start and enable sshd service
        3. Create authorized_keys with proper ACL
        4. Firewall is auto-configured by Windows on install

        Returns:
            (success, message)
        """
        if sys.platform != "win32":
            return False, "SSH setup only supported on Windows"

        try:
            # Step 1: Install OpenSSH Server if not installed
            if not self.is_ssh_server_installed():
                self._emit_progress("Installing OpenSSH Server...")
                success, stdout, stderr = self._run_powershell(
                    "Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0",
                    timeout=300  # Installation can take a while
                )
                if not success:
                    return False, f"Failed to install OpenSSH Server: {stderr}"
                self._emit_progress("OpenSSH Server installed")
            else:
                self._emit_progress("OpenSSH Server already installed")

            # Step 2: Start sshd service
            if not self.is_sshd_running():
                self._emit_progress("Starting sshd service...")
                success, stdout, stderr = self._run_powershell("Start-Service sshd")
                if not success:
                    return False, f"Failed to start sshd: {stderr}"
                self._emit_progress("sshd service started")
            else:
                self._emit_progress("sshd service already running")

            # Step 3: Set sshd to automatic startup
            if not self.is_sshd_enabled():
                self._emit_progress("Enabling sshd automatic startup...")
                success, stdout, stderr = self._run_powershell(
                    "Set-Service -Name sshd -StartupType 'Automatic'"
                )
                if not success:
                    return False, f"Failed to enable sshd: {stderr}"
                self._emit_progress("sshd set to automatic startup")

            # Step 4: Create authorized_keys file if it doesn't exist
            if not self.AUTHORIZED_KEYS_PATH.exists():
                self._emit_progress("Creating authorized_keys file...")
                self._create_authorized_keys_file()
            else:
                self._emit_progress("authorized_keys file exists")

            # Step 5: Fix ACL permissions on authorized_keys
            self._emit_progress("Setting file permissions...")
            self._fix_authorized_keys_acl()

            return True, "OpenSSH Server setup complete"

        except Exception as e:
            logger.error(f"SSH setup failed: {e}")
            return False, str(e)

    def _create_authorized_keys_file(self):
        """Create empty authorized_keys file with proper permissions"""
        # Ensure directory exists
        self.SSH_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Create empty file
        self.AUTHORIZED_KEYS_PATH.touch()
        logger.info(f"Created {self.AUTHORIZED_KEYS_PATH}")

    def _fix_authorized_keys_acl(self) -> bool:
        """
        Set proper ACL on authorized_keys file.
        Only Administrators and SYSTEM should have access.
        Uses SID for internationalization support.
        """
        if not self.AUTHORIZED_KEYS_PATH.exists():
            return False

        # Use SID for Administrators group (*S-1-5-32-544) for i18n support
        result = subprocess.run([
            "icacls.exe",
            str(self.AUTHORIZED_KEYS_PATH),
            "/inheritance:r",  # Remove inherited permissions
            "/grant", "*S-1-5-32-544:F",  # Administrators: Full
            "/grant", "SYSTEM:F"  # SYSTEM: Full
        ], capture_output=True, text=True)

        if result.returncode != 0:
            logger.warning(f"Failed to set ACL: {result.stderr}")
            return False

        logger.info("Set proper ACL on authorized_keys")
        return True

    def add_authorized_key(self, public_key: str, comment: str = "") -> Tuple[bool, str]:
        """
        Add a public key to administrators_authorized_keys.
        Handles ACL permissions automatically.

        Args:
            public_key: Full public key line (ssh-ed25519 AAAA... comment)
            comment: Optional additional comment

        Returns:
            (success, message)
        """
        if not public_key or not public_key.strip():
            return False, "Empty public key"

        public_key = public_key.strip()

        # Validate key format (basic check)
        if not (public_key.startswith("ssh-") or public_key.startswith("ecdsa-")):
            return False, "Invalid public key format"

        try:
            # Check if key already exists
            if self.AUTHORIZED_KEYS_PATH.exists():
                existing = self.AUTHORIZED_KEYS_PATH.read_text()
                # Extract key data (second field) for comparison
                key_data = public_key.split()[1] if len(public_key.split()) >= 2 else public_key
                if key_data in existing:
                    return True, "Key already registered"

            # Ensure file exists
            if not self.AUTHORIZED_KEYS_PATH.exists():
                self._create_authorized_keys_file()

            # Append key to file (with newline)
            with open(self.AUTHORIZED_KEYS_PATH, "a", encoding="utf-8", newline="\n") as f:
                # Ensure we start on a new line
                if self.AUTHORIZED_KEYS_PATH.stat().st_size > 0:
                    f.write("\n")
                f.write(public_key)

            # Fix ACL after adding key
            self._fix_authorized_keys_acl()

            logger.info(f"Added SSH key: {public_key[:50]}...")
            return True, "Key added successfully"

        except Exception as e:
            logger.error(f"Failed to add key: {e}")
            return False, str(e)

    def get_ssh_status(self) -> dict:
        """Get current SSH server status"""
        authorized_keys_count = 0
        if self.AUTHORIZED_KEYS_PATH.exists():
            content = self.AUTHORIZED_KEYS_PATH.read_text()
            # Count non-empty, non-comment lines
            authorized_keys_count = len([
                line for line in content.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ])

        return {
            "installed": self.is_ssh_server_installed(),
            "running": self.is_sshd_running(),
            "enabled": self.is_sshd_enabled(),
            "authorized_keys_path": str(self.AUTHORIZED_KEYS_PATH),
            "authorized_keys_count": authorized_keys_count,
        }

    def get_registered_keys(self) -> list:
        """Get list of registered public keys (fingerprints only for display)"""
        if not self.AUTHORIZED_KEYS_PATH.exists():
            return []

        keys = []
        for line in self.AUTHORIZED_KEYS_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 2:
                    key_type = parts[0]
                    key_comment = parts[2] if len(parts) >= 3 else "unknown"
                    # Get fingerprint
                    result = subprocess.run(
                        ["ssh-keygen", "-lf", "-"],
                        input=line,
                        capture_output=True,
                        text=True
                    )
                    fingerprint = result.stdout.split()[1] if result.returncode == 0 else "unknown"
                    keys.append({
                        "type": key_type,
                        "comment": key_comment,
                        "fingerprint": fingerprint,
                    })
        return keys
