"""
Authorized Keys Manager for Master machine.
Manages the administrators_authorized_keys file for SUT SSH access.
"""

import subprocess
import threading
import logging
import sys
from pathlib import Path
from typing import Optional, Set, Tuple

logger = logging.getLogger(__name__)


class AuthorizedKeysManager:
    """
    Manages the administrators_authorized_keys file on Master.
    Thread-safe for concurrent SUT registrations.

    On Windows, administrator SSH keys are stored in:
    C:/ProgramData/ssh/administrators_authorized_keys

    This file must have specific ACL permissions:
    - Only Administrators and SYSTEM can access
    - No inherited permissions
    """

    # Windows stores admin SSH keys here (not user profile)
    AUTHORIZED_KEYS_PATH = Path("C:/ProgramData/ssh/administrators_authorized_keys")
    SSH_CONFIG_DIR = Path("C:/ProgramData/ssh")

    def __init__(self):
        self._lock = threading.Lock()
        self._registered_fingerprints: Set[str] = set()
        self._load_existing_keys()

    def _load_existing_keys(self):
        """Load fingerprints of existing keys on startup"""
        if not self.AUTHORIZED_KEYS_PATH.exists():
            logger.info("No existing authorized_keys file found")
            return

        try:
            content = self.AUTHORIZED_KEYS_PATH.read_text()
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    fingerprint = self._get_fingerprint(line)
                    if fingerprint:
                        self._registered_fingerprints.add(fingerprint)
                        logger.debug(f"Loaded existing key: {fingerprint}")

            logger.info(f"Loaded {len(self._registered_fingerprints)} existing SSH keys")
        except Exception as e:
            logger.error(f"Failed to load existing keys: {e}")

    def _get_fingerprint(self, public_key: str) -> Optional[str]:
        """
        Get SHA256 fingerprint of a public key.

        Args:
            public_key: Full public key line (ssh-ed25519 AAAA... comment)

        Returns:
            Fingerprint string (e.g., "SHA256:abc123...") or None
        """
        if not public_key or not public_key.strip():
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
                # Output format: "256 SHA256:xxx comment (ED25519)"
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[1]
            return None

        except Exception as e:
            logger.error(f"Failed to get fingerprint: {e}")
            return None

    def add_key(self, public_key: str, sut_id: str) -> Tuple[bool, str]:
        """
        Add SUT public key to authorized_keys.

        Args:
            public_key: Full public key line (ssh-ed25519 AAAA... comment)
            sut_id: SUT identifier for logging

        Returns:
            (success, message)
        """
        if sys.platform != "win32":
            return False, "SSH key management only supported on Windows"

        if not public_key or not public_key.strip():
            return False, "Empty public key"

        public_key = public_key.strip()

        # Validate key format
        if not (public_key.startswith("ssh-") or public_key.startswith("ecdsa-")):
            return False, "Invalid public key format"

        with self._lock:
            try:
                # Get fingerprint for deduplication
                fingerprint = self._get_fingerprint(public_key)
                if not fingerprint:
                    return False, "Could not determine key fingerprint"

                # Check if key already registered
                if fingerprint in self._registered_fingerprints:
                    logger.info(f"SSH key for {sut_id} already registered: {fingerprint}")
                    return True, "Key already registered"

                # Ensure authorized_keys file exists
                if not self.AUTHORIZED_KEYS_PATH.exists():
                    self._create_authorized_keys_file()

                # Append key to file
                with open(self.AUTHORIZED_KEYS_PATH, "a", encoding="utf-8", newline="\n") as f:
                    # Ensure we start on a new line
                    if self.AUTHORIZED_KEYS_PATH.stat().st_size > 0:
                        f.write("\n")
                    f.write(public_key)

                # Fix ACL permissions
                self._fix_acl()

                # Track fingerprint
                self._registered_fingerprints.add(fingerprint)
                logger.info(f"Added SSH key for {sut_id}: {fingerprint}")
                return True, "Key added successfully"

            except Exception as e:
                logger.error(f"Failed to add key for {sut_id}: {e}")
                return False, str(e)

    def _create_authorized_keys_file(self):
        """Create empty authorized_keys file"""
        try:
            self.SSH_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self.AUTHORIZED_KEYS_PATH.touch()
            logger.info(f"Created {self.AUTHORIZED_KEYS_PATH}")
        except Exception as e:
            logger.error(f"Failed to create authorized_keys: {e}")
            raise

    def _fix_acl(self) -> bool:
        """
        Set proper ACL on authorized_keys file.
        Only Administrators and SYSTEM should have access.
        Uses SID for internationalization support.
        """
        if not self.AUTHORIZED_KEYS_PATH.exists():
            return False

        try:
            # Use SID for Administrators group (*S-1-5-32-544) for i18n support
            result = subprocess.run([
                "icacls.exe",
                str(self.AUTHORIZED_KEYS_PATH),
                "/inheritance:r",  # Remove inherited permissions
                "/grant", "*S-1-5-32-544:F",  # Administrators: Full
                "/grant", "SYSTEM:F"  # SYSTEM: Full
            ], capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.warning(f"Failed to set ACL: {result.stderr}")
                return False

            logger.debug("Set proper ACL on authorized_keys")
            return True

        except Exception as e:
            logger.error(f"ACL fix failed: {e}")
            return False

    def is_key_registered(self, fingerprint: str) -> bool:
        """Check if a key fingerprint is already registered"""
        return fingerprint in self._registered_fingerprints

    def get_registered_count(self) -> int:
        """Get count of registered keys"""
        return len(self._registered_fingerprints)

    def get_status(self) -> dict:
        """Get current status of the key store"""
        return {
            "authorized_keys_path": str(self.AUTHORIZED_KEYS_PATH),
            "file_exists": self.AUTHORIZED_KEYS_PATH.exists(),
            "registered_keys": len(self._registered_fingerprints),
        }


# Module-level singleton
_key_store: Optional[AuthorizedKeysManager] = None


def get_key_store() -> AuthorizedKeysManager:
    """Get or create the singleton AuthorizedKeysManager instance."""
    global _key_store
    if _key_store is None:
        _key_store = AuthorizedKeysManager()
    return _key_store
