"""
SSH Setup Module for SUT Client.
Handles Windows OpenSSH Server setup on SUTs for bidirectional SSH with Master.
"""

import subprocess
import logging
import sys
import getpass
import ctypes
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


def _is_admin() -> bool:
    """Check if running with administrator privileges."""
    if sys.platform != "win32":
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


class SSHSetup:
    """
    Windows OpenSSH Server setup and configuration for SUTs.

    Enables Master to connect to SUTs via SSH (for trace pulling, etc.).

    For Administrator users on Windows, OpenSSH uses a special location:
    C:\\ProgramData\\ssh\\administrators_authorized_keys

    For regular users, it uses: ~/.ssh/authorized_keys
    """

    def __init__(self, master_url: Optional[str] = None):
        """
        Initialize SSH Setup.

        Args:
            master_url: Optional Master server URL (e.g., "http://192.168.50.100:5000")
                       Used to fetch the Master's public SSH key.
        """
        self._master_url = master_url
        self._username = getpass.getuser()

        # Determine the correct authorized_keys path based on user type
        # For admin users (like Administrator), Windows OpenSSH uses a special location
        if self._is_admin_user():
            self._ssh_dir = Path(r"C:\ProgramData\ssh")
            self._authorized_keys_path = self._ssh_dir / "administrators_authorized_keys"
            logger.info(f"Admin user detected, using: {self._authorized_keys_path}")
        else:
            self._ssh_dir = Path.home() / ".ssh"
            self._authorized_keys_path = self._ssh_dir / "authorized_keys"
            logger.info(f"Regular user, using: {self._authorized_keys_path}")

    def _is_admin_user(self) -> bool:
        """
        Check if current user is an administrator account.

        Windows OpenSSH treats members of the Administrators group specially,
        using C:\\ProgramData\\ssh\\administrators_authorized_keys instead of
        the user's home directory.
        """
        if sys.platform != "win32":
            return False

        username = self._username.lower()

        # Check if username is "administrator"
        if username == "administrator":
            return True

        # Check if user is in Administrators group
        try:
            result = subprocess.run(
                ["net", "localgroup", "Administrators"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Parse output to find usernames
                lines = result.stdout.lower().splitlines()
                for line in lines:
                    if username in line:
                        return True
        except Exception as e:
            logger.debug(f"Could not check admin group: {e}")

        return False

    @property
    def authorized_keys_path(self) -> Path:
        """Path to authorized_keys file."""
        return self._authorized_keys_path

    def _run_powershell(self, command: str, timeout: int = 120) -> Tuple[bool, str, str]:
        """
        Run a PowerShell command and return (success, stdout, stderr).

        Args:
            command: PowerShell command to run
            timeout: Command timeout in seconds

        Returns:
            (success, stdout, stderr)
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

    def check_openssh_installed(self) -> bool:
        """
        Check if OpenSSH Server capability is installed.

        Returns:
            True if installed
        """
        success, stdout, _ = self._run_powershell(
            "Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*' | Select-Object -ExpandProperty State"
        )
        return success and "Installed" in stdout

    def install_openssh_server(self) -> Tuple[bool, str]:
        """
        Install OpenSSH Server Windows capability.

        Returns:
            (success, message)
        """
        if sys.platform != "win32":
            return False, "Only supported on Windows"

        if self.check_openssh_installed():
            return True, "OpenSSH Server already installed"

        logger.info("Installing OpenSSH Server capability...")
        success, stdout, stderr = self._run_powershell(
            "Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0",
            timeout=300  # Installation can take a while
        )

        if success:
            logger.info("OpenSSH Server installed successfully")
            return True, "OpenSSH Server installed"
        else:
            logger.error(f"Failed to install OpenSSH Server: {stderr}")
            return False, f"Installation failed: {stderr}"

    def is_sshd_running(self) -> bool:
        """Check if sshd service is running."""
        success, stdout, _ = self._run_powershell(
            "(Get-Service sshd -ErrorAction SilentlyContinue).Status"
        )
        return success and "Running" in stdout

    def start_sshd_service(self) -> Tuple[bool, str]:
        """
        Start the sshd service.

        Returns:
            (success, message)
        """
        if self.is_sshd_running():
            return True, "sshd service already running"

        logger.info("Starting sshd service...")
        success, stdout, stderr = self._run_powershell("Start-Service sshd")

        if success:
            logger.info("sshd service started")
            return True, "sshd service started"
        else:
            logger.error(f"Failed to start sshd: {stderr}")
            return False, f"Failed to start sshd: {stderr}"

    def is_sshd_enabled(self) -> bool:
        """Check if sshd service is set to automatic startup."""
        success, stdout, _ = self._run_powershell(
            "(Get-Service sshd -ErrorAction SilentlyContinue).StartType"
        )
        return success and "Automatic" in stdout

    def enable_sshd_autostart(self) -> Tuple[bool, str]:
        """
        Set sshd service to automatic startup.

        Returns:
            (success, message)
        """
        if self.is_sshd_enabled():
            return True, "sshd already set to automatic"

        logger.info("Enabling sshd automatic startup...")
        success, stdout, stderr = self._run_powershell(
            "Set-Service -Name sshd -StartupType 'Automatic'"
        )

        if success:
            logger.info("sshd set to automatic startup")
            return True, "sshd set to automatic startup"
        else:
            logger.error(f"Failed to enable sshd autostart: {stderr}")
            return False, f"Failed to enable autostart: {stderr}"

    def set_network_profile_private(self) -> bool:
        """
        Set network profile to Private for better SSH connectivity.

        Note: This may fail without admin rights, which is acceptable.

        Returns:
            True if successful or already private
        """
        # Check current profile
        success, stdout, _ = self._run_powershell(
            "Get-NetConnectionProfile | Select-Object -ExpandProperty NetworkCategory"
        )

        if success and "Private" in stdout:
            logger.debug("Network already set to Private")
            return True

        # Try to set to Private (may fail without admin)
        logger.info("Attempting to set network profile to Private...")
        success, _, stderr = self._run_powershell(
            "Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Private"
        )

        if success:
            logger.info("Network profile set to Private")
            return True
        else:
            logger.warning(f"Could not set network to Private (may need admin): {stderr}")
            return False

    def configure_firewall_rule(self) -> Tuple[bool, str]:
        """
        Configure Windows Firewall to allow SSH on all profiles.

        Creates or updates firewall rule for SSH port 22.

        Returns:
            (success, message)
        """
        logger.info("Configuring SSH firewall rule...")

        # Check if rule already exists
        success, stdout, _ = self._run_powershell(
            "Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Enabled"
        )

        if success and "True" in stdout:
            # Update existing rule to apply to all profiles
            success, _, stderr = self._run_powershell(
                "Set-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -Profile Any -Enabled True"
            )
            if success:
                return True, "Firewall rule updated for all profiles"
            else:
                logger.warning(f"Could not update firewall rule: {stderr}")
                return False, f"Failed to update firewall rule: {stderr}"

        # Create new rule for all profiles
        success, _, stderr = self._run_powershell(
            """
            New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' `
                -DisplayName 'OpenSSH SSH Server (sshd)' `
                -Description 'Inbound rule for OpenSSH SSH Server' `
                -Enabled True `
                -Direction Inbound `
                -Protocol TCP `
                -Action Allow `
                -LocalPort 22 `
                -Profile Any
            """
        )

        if success:
            logger.info("SSH firewall rule created for all profiles")
            return True, "Firewall rule created"
        else:
            logger.warning(f"Could not create firewall rule: {stderr}")
            return False, f"Failed to create firewall rule: {stderr}"

    def fetch_master_public_key(self, master_url: str = None) -> Tuple[bool, str, str]:
        """
        Fetch the Master's public SSH key from the Master server.

        Args:
            master_url: Master server URL (e.g., "http://192.168.50.100:5000")
                       If not provided, uses the URL from constructor.

        Returns:
            (success, public_key, message)
        """
        url = master_url or self._master_url
        if not url:
            return False, "", "No Master URL provided"

        # Ensure URL has protocol
        if not url.startswith("http"):
            url = f"http://{url}"

        # Try to fetch from Master's API endpoint
        api_url = f"{url.rstrip('/')}/api/ssh/public-key"

        try:
            import urllib.request
            import json

            logger.info(f"Fetching Master's public key from {api_url}")

            req = urllib.request.Request(api_url, method='GET')
            req.add_header('Accept', 'application/json')

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

                if data.get("public_key"):
                    public_key = data["public_key"].strip()
                    logger.info(f"Got Master's public key: {public_key[:50]}...")
                    return True, public_key, "Key fetched successfully"
                else:
                    return False, "", "No public key in response"

        except urllib.error.HTTPError as e:
            logger.warning(f"HTTP error fetching Master key: {e.code}")
            return False, "", f"HTTP error: {e.code}"
        except urllib.error.URLError as e:
            logger.warning(f"URL error fetching Master key: {e.reason}")
            return False, "", f"Connection error: {e.reason}"
        except Exception as e:
            logger.warning(f"Error fetching Master key: {e}")
            return False, "", str(e)

    def add_authorized_key(self, public_key: str) -> Tuple[bool, str]:
        """
        Add a public key to authorized_keys file.

        For admin users, writes to C:\\ProgramData\\ssh\\administrators_authorized_keys
        For regular users, writes to ~/.ssh/authorized_keys

        Args:
            public_key: Full public key line (ssh-ed25519 AAAA... comment)

        Returns:
            (success, message)
        """
        if not public_key or not public_key.strip():
            return False, "Empty public key"

        public_key = public_key.strip()

        # Validate key format
        if not (public_key.startswith("ssh-") or public_key.startswith("ecdsa-")):
            return False, "Invalid public key format"

        try:
            # Ensure directory exists
            self._ssh_dir.mkdir(parents=True, exist_ok=True)

            # Check if key already exists
            if self._authorized_keys_path.exists():
                existing = self._authorized_keys_path.read_text()
                # Extract key data (second field) for comparison
                parts = public_key.split()
                key_data = parts[1] if len(parts) >= 2 else public_key
                if key_data in existing:
                    logger.info("Master's SSH key already in authorized_keys")
                    return True, "Key already registered"

            # For admin users, we need to handle the file specially
            # The administrators_authorized_keys file needs specific permissions
            if self._is_admin_user():
                # Write/append the key
                mode = "a" if self._authorized_keys_path.exists() else "w"
                with open(self._authorized_keys_path, mode, encoding="utf-8") as f:
                    if mode == "a" and self._authorized_keys_path.stat().st_size > 0:
                        # Check if we need a newline
                        content = self._authorized_keys_path.read_text()
                        if content and not content.endswith("\n"):
                            f.write("\n")
                    f.write(public_key + "\n")

                # Fix permissions for administrators_authorized_keys
                # This file must be owned by Administrators/SYSTEM only
                self._fix_admin_authorized_keys_permissions()

                logger.info(f"Added Master's SSH key to {self._authorized_keys_path}")
                return True, f"Key added to {self._authorized_keys_path}"
            else:
                # Regular user - use normal .ssh/authorized_keys
                self._ssh_dir.mkdir(mode=0o700, exist_ok=True)

                with open(self._authorized_keys_path, "a", encoding="utf-8", newline="\n") as f:
                    if self._authorized_keys_path.exists() and self._authorized_keys_path.stat().st_size > 0:
                        content = self._authorized_keys_path.read_text()
                        if content and not content.endswith("\n"):
                            f.write("\n")
                    f.write(public_key + "\n")

                logger.info(f"Added Master's SSH key to authorized_keys")
                return True, "Key added successfully"

        except Exception as e:
            logger.error(f"Failed to add authorized key: {e}")
            return False, str(e)

    def _fix_admin_authorized_keys_permissions(self) -> bool:
        """
        Fix permissions on administrators_authorized_keys file.

        Windows OpenSSH requires this file to be owned by Administrators or SYSTEM,
        with no other users having write access.

        Returns:
            True if permissions were fixed successfully
        """
        if not self._authorized_keys_path.exists():
            return False

        try:
            # Use icacls to set proper permissions
            # Remove inheritance and set explicit permissions for Administrators and SYSTEM only
            file_path = str(self._authorized_keys_path)

            # Disable inheritance
            subprocess.run(
                ["icacls", file_path, "/inheritance:r"],
                capture_output=True,
                check=False
            )

            # Grant full control to Administrators
            subprocess.run(
                ["icacls", file_path, "/grant", "Administrators:F"],
                capture_output=True,
                check=False
            )

            # Grant full control to SYSTEM
            subprocess.run(
                ["icacls", file_path, "/grant", "SYSTEM:F"],
                capture_output=True,
                check=False
            )

            logger.info(f"Fixed permissions on {file_path}")
            return True

        except Exception as e:
            logger.warning(f"Could not fix permissions: {e}")
            return False

    def remove_authorized_key(self, key_fingerprint: str) -> Tuple[bool, str]:
        """
        Remove a public key from authorized_keys by fingerprint.

        Args:
            key_fingerprint: SHA256 fingerprint of key to remove

        Returns:
            (success, message)
        """
        if not self._authorized_keys_path.exists():
            return False, "No authorized_keys file"

        try:
            lines = self._authorized_keys_path.read_text().splitlines()
            new_lines = []
            removed = False

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    new_lines.append(line)
                    continue

                # Get fingerprint of this key
                fp = self._get_fingerprint(line)
                if fp and fp == key_fingerprint:
                    removed = True
                    logger.info(f"Removing key with fingerprint: {fp}")
                else:
                    new_lines.append(line)

            if removed:
                self._authorized_keys_path.write_text("\n".join(new_lines) + "\n")
                return True, "Key removed"
            else:
                return False, "Key not found"

        except Exception as e:
            logger.error(f"Failed to remove key: {e}")
            return False, str(e)

    def _get_fingerprint(self, public_key: str) -> Optional[str]:
        """Get SHA256 fingerprint of a public key."""
        if not public_key:
            return None

        try:
            result = subprocess.run(
                ["ssh-keygen", "-lf", "-"],
                input=public_key,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[1]
            return None

        except Exception as e:
            logger.error(f"Failed to get fingerprint: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """
        Get current SSH setup status.

        Returns:
            Dictionary with status information
        """
        authorized_keys_count = 0
        if self._authorized_keys_path.exists():
            content = self._authorized_keys_path.read_text()
            authorized_keys_count = len([
                line for line in content.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ])

        return {
            "openssh_installed": self.check_openssh_installed(),
            "sshd_running": self.is_sshd_running(),
            "sshd_enabled": self.is_sshd_enabled(),
            "authorized_keys_path": str(self._authorized_keys_path),
            "authorized_keys_count": authorized_keys_count,
            "username": getpass.getuser(),
        }

    def run_full_setup(self, master_url: str = None) -> Dict[str, Any]:
        """
        Run complete SSH setup for SUT.

        Steps:
        1. Install OpenSSH Server (if not installed)
        2. Start sshd service
        3. Enable sshd autostart
        4. Configure firewall rule
        5. Try to set network to Private (optional)
        6. Fetch and install Master's public key (if master_url provided)

        Args:
            master_url: Optional Master server URL to fetch public key from.
                       If not provided, uses URL from constructor or skips key installation.

        Returns:
            Dictionary with setup results
        """
        if sys.platform != "win32":
            return {
                "success": False,
                "error": "SSH setup only supported on Windows",
                "steps": []
            }

        results = {
            "success": True,
            "steps": [],
            "status": {}
        }

        # Step 1: Install OpenSSH Server
        success, msg = self.install_openssh_server()
        results["steps"].append({
            "step": "install_openssh",
            "success": success,
            "message": msg
        })
        if not success:
            results["success"] = False
            results["error"] = msg
            return results

        # Step 2: Start sshd service
        success, msg = self.start_sshd_service()
        results["steps"].append({
            "step": "start_sshd",
            "success": success,
            "message": msg
        })
        if not success:
            results["success"] = False
            results["error"] = msg
            return results

        # Step 3: Enable autostart
        success, msg = self.enable_sshd_autostart()
        results["steps"].append({
            "step": "enable_autostart",
            "success": success,
            "message": msg
        })
        if not success:
            # Non-fatal, continue
            logger.warning(f"Autostart enable failed (non-fatal): {msg}")

        # Step 4: Configure firewall
        success, msg = self.configure_firewall_rule()
        results["steps"].append({
            "step": "configure_firewall",
            "success": success,
            "message": msg
        })
        if not success:
            # Non-fatal for setup, but log warning
            logger.warning(f"Firewall configuration failed (non-fatal): {msg}")

        # Step 5: Try to set network to Private (optional)
        network_private = self.set_network_profile_private()
        results["steps"].append({
            "step": "set_network_private",
            "success": network_private,
            "message": "Network set to Private" if network_private else "Could not set network to Private (may need admin)"
        })

        # Step 6: Fetch and install Master's public key
        url = master_url or self._master_url
        if url:
            success, public_key, msg = self.fetch_master_public_key(url)
            if success and public_key:
                key_success, key_msg = self.add_authorized_key(public_key)
                results["steps"].append({
                    "step": "install_master_key",
                    "success": key_success,
                    "message": key_msg
                })
                if not key_success:
                    logger.warning(f"Failed to install Master's key (non-fatal): {key_msg}")
            else:
                results["steps"].append({
                    "step": "install_master_key",
                    "success": False,
                    "message": f"Could not fetch Master's key: {msg}"
                })
                logger.warning(f"Could not fetch Master's key (non-fatal): {msg}")
        else:
            results["steps"].append({
                "step": "install_master_key",
                "success": False,
                "message": "No Master URL provided - skipping key installation"
            })
            logger.info("No Master URL provided, skipping key installation")

        # Get final status
        results["status"] = self.get_status()

        logger.info(f"SSH setup complete: {results['success']}")
        return results

    def test_ssh_connectivity(self, timeout: int = 5) -> Tuple[bool, str]:
        """
        Test if SSH port is accessible locally.

        Returns:
            (success, message)
        """
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex(('127.0.0.1', 22))
            sock.close()

            if result == 0:
                return True, "SSH port 22 is accessible"
            else:
                return False, f"SSH port 22 not accessible (error code: {result})"

        except Exception as e:
            return False, str(e)


# Module-level singleton
_ssh_setup: Optional[SSHSetup] = None


def get_ssh_setup(master_url: str = None) -> SSHSetup:
    """
    Get or create the singleton SSHSetup instance.

    Args:
        master_url: Optional Master server URL for fetching public key.
                   Only used when creating a new instance.

    Returns:
        SSHSetup instance
    """
    global _ssh_setup
    if _ssh_setup is None:
        _ssh_setup = SSHSetup(master_url=master_url)
    return _ssh_setup


def reset_ssh_setup() -> None:
    """Reset the singleton instance (useful for testing or reconfiguration)."""
    global _ssh_setup
    _ssh_setup = None
