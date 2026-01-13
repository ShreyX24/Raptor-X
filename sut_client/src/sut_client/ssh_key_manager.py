"""
SSH Key Manager for SUT Client.
Handles automatic SSH key generation and retrieval for Master authentication.
"""

import subprocess
import socket
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class SSHKeyManager:
    """
    Manages SSH key generation and retrieval for SUT Client.
    Keys are generated once and reused for all Master connections.

    Uses Ed25519 keys for:
    - Modern, secure algorithm
    - Fast key generation
    - Small key size
    """

    def __init__(self, key_name: str = "id_ed25519"):
        """
        Initialize SSH Key Manager.

        Args:
            key_name: Base name for key files (default: id_ed25519)
        """
        self._ssh_dir = Path.home() / ".ssh"
        self._key_path = self._ssh_dir / key_name
        self._pub_key_path = self._ssh_dir / f"{key_name}.pub"

    @property
    def key_path(self) -> Path:
        """Path to private key"""
        return self._key_path

    @property
    def public_key_path(self) -> Path:
        """Path to public key"""
        return self._pub_key_path

    def ensure_key_exists(self) -> Tuple[bool, str]:
        """
        Ensure SSH key pair exists, generating if necessary.

        Returns:
            (success, message)
        """
        if self._key_path.exists() and self._pub_key_path.exists():
            logger.debug(f"SSH key already exists: {self._key_path}")
            return True, "Key already exists"

        # Ensure .ssh directory exists with proper permissions
        try:
            self._ssh_dir.mkdir(mode=0o700, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create .ssh directory: {e}")
            return False, f"Failed to create .ssh directory: {e}"

        # Generate Ed25519 key pair (no passphrase)
        hostname = socket.gethostname()
        comment = f"sut-client@{hostname}"

        try:
            result = subprocess.run([
                "ssh-keygen",
                "-t", "ed25519",
                "-N", "",  # No passphrase
                "-f", str(self._key_path),
                "-C", comment
            ], capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip()
                logger.error(f"ssh-keygen failed: {error}")
                return False, f"Key generation failed: {error}"

            logger.info(f"Generated SSH key pair: {self._key_path}")
            return True, f"Generated new key: {comment}"

        except FileNotFoundError:
            logger.error("ssh-keygen not found - OpenSSH client not installed?")
            return False, "ssh-keygen not found"
        except subprocess.TimeoutExpired:
            logger.error("ssh-keygen timed out")
            return False, "Key generation timed out"
        except Exception as e:
            logger.error(f"Key generation error: {e}")
            return False, str(e)

    def get_public_key(self) -> Optional[str]:
        """
        Read and return the public key content.

        Returns:
            Public key string (e.g., "ssh-ed25519 AAAA... comment")
            or None if not available
        """
        if not self._pub_key_path.exists():
            logger.warning(f"Public key not found: {self._pub_key_path}")
            return None

        try:
            content = self._pub_key_path.read_text().strip()
            logger.debug(f"Read public key: {content[:50]}...")
            return content
        except Exception as e:
            logger.error(f"Failed to read public key: {e}")
            return None

    def get_key_fingerprint(self) -> Optional[str]:
        """
        Get SHA256 fingerprint of the key.

        Returns:
            Fingerprint string (e.g., "SHA256:abc123...")
            or None if not available
        """
        if not self._key_path.exists():
            return None

        try:
            result = subprocess.run(
                ["ssh-keygen", "-lf", str(self._key_path)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # Output format: "256 SHA256:xxx comment (ED25519)"
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[1]
            return None

        except Exception as e:
            logger.error(f"Failed to get fingerprint: {e}")
            return None

    def get_key_info(self) -> dict:
        """
        Get information about the SSH key.

        Returns:
            Dictionary with key info
        """
        exists = self._key_path.exists() and self._pub_key_path.exists()

        return {
            "exists": exists,
            "private_key_path": str(self._key_path),
            "public_key_path": str(self._pub_key_path),
            "fingerprint": self.get_key_fingerprint() if exists else None,
            "public_key": self.get_public_key() if exists else None,
        }

    def test_connection(self, master_ip: str, username: str = None, timeout: int = 10) -> Tuple[bool, str]:
        """
        Test SSH connection to Master server.

        Args:
            master_ip: Master server IP address
            username: SSH username (defaults to current user)
            timeout: Connection timeout in seconds

        Returns:
            (success, message)
        """
        import getpass

        if username is None:
            username = getpass.getuser()

        try:
            result = subprocess.run([
                "ssh",
                "-o", "BatchMode=yes",  # No interactive prompts
                "-o", "StrictHostKeyChecking=no",  # Accept new host keys
                "-o", f"ConnectTimeout={timeout}",
                f"{username}@{master_ip}",
                "echo SSH_OK"
            ], capture_output=True, text=True, timeout=timeout + 5)

            if result.returncode == 0 and "SSH_OK" in result.stdout:
                logger.info(f"SSH connection to {master_ip} successful")
                return True, "Connection successful"
            else:
                error = result.stderr.strip() or "Connection failed"
                logger.warning(f"SSH connection failed: {error}")
                return False, error

        except subprocess.TimeoutExpired:
            return False, "Connection timed out"
        except Exception as e:
            return False, str(e)


# Module-level instance for easy access
_key_manager: Optional[SSHKeyManager] = None


def get_key_manager() -> SSHKeyManager:
    """Get or create the singleton SSH key manager instance."""
    global _key_manager
    if _key_manager is None:
        _key_manager = SSHKeyManager()
    return _key_manager
