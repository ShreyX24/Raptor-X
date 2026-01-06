"""
Steam Account Pool Manager

Manages Steam account pairs for multi-SUT automation. Each SUT gets assigned
an account pair, and games are split by first letter (A-F vs G-Z) to allow
two concurrent games per SUT without login conflicts.

Configuration Sources (in priority order):
    1. Config file: ~/.gemma/service_manager_config.json (preferred)
    2. Environment Variable: STEAM_ACCOUNT_PAIRS = "Pair1:af_user:af_pass:gz_user:gz_pass|..."

    Each pair is separated by |
    Fields within pair separated by :
"""

import os
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class AccountPair:
    """A pair of Steam accounts for A-F and G-Z games"""
    name: str
    af_username: str
    af_password: str
    gz_username: str
    gz_password: str

    @classmethod
    def from_env_string(cls, s: str) -> "AccountPair":
        """Parse from environment variable string format.

        Format: name:af_user:af_pass:gz_user:gz_pass
        """
        parts = s.split(":")
        if len(parts) < 5:
            raise ValueError(f"Invalid account pair format: {s}")
        return cls(
            name=parts[0],
            af_username=parts[1],
            af_password=parts[2],
            gz_username=parts[3],
            gz_password=parts[4],
        )


class AccountPoolManager:
    """
    Manages Steam account allocation for multi-SUT automation.

    Thread-safe singleton that:
    - Parses account pairs from STEAM_ACCOUNT_PAIRS env var
    - Allocates account pairs to SUTs on demand
    - Returns appropriate account based on game's first letter
    - Tracks accounts that are in use on other devices (externally busy)
    - Releases accounts when SUT automation completes

    Usage:
        pool = AccountPoolManager.get_instance()

        # At automation start
        if pool.acquire_account_pair(sut_id):
            # Account acquired
            pass

        # When launching a game
        username, password = pool.get_account_for_game(sut_id, "Cyberpunk 2077")

        # If Steam login fails with "account in use on another device"
        pool.mark_account_externally_busy(sut_id, username, game_name)
        new_creds = pool.try_alternative_account(sut_id, game_name)

        # At automation end
        pool.release_account_pair(sut_id)
    """

    _instance: Optional["AccountPoolManager"] = None
    _lock = Lock()

    def __init__(self):
        self._pairs: list[AccountPair] = []
        self._allocations: Dict[str, AccountPair] = {}  # sut_id -> AccountPair
        self._externally_busy: Dict[str, set] = {}  # username -> set of sut_ids that reported it busy
        self._allocation_lock = Lock()
        self._load_from_env()

    @classmethod
    def get_instance(cls) -> "AccountPoolManager":
        """Get singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)"""
        with cls._lock:
            cls._instance = None

    def _load_from_env(self):
        """Load account pairs from config file or environment variable"""
        # First try loading from config file (preferred)
        if self._load_from_config_file():
            return

        # Fall back to environment variable
        env_value = os.environ.get("STEAM_ACCOUNT_PAIRS", "")
        if not env_value:
            logger.info("No STEAM_ACCOUNT_PAIRS configured (neither config file nor env var)")
            return

        try:
            for pair_str in env_value.split("|"):
                pair_str = pair_str.strip()
                if pair_str:
                    pair = AccountPair.from_env_string(pair_str)
                    self._pairs.append(pair)
            logger.info(f"Loaded {len(self._pairs)} Steam account pair(s) from env var")
        except ValueError as e:
            logger.error(f"Failed to parse STEAM_ACCOUNT_PAIRS: {e}")

    def _load_from_config_file(self) -> bool:
        """Load account pairs from ~/.gemma/service_manager_config.json"""
        config_path = Path.home() / ".gemma" / "service_manager_config.json"
        if not config_path.exists():
            logger.debug(f"Config file not found: {config_path}")
            return False

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            pairs = config.get('steam_account_pairs', [])
            if not pairs:
                logger.debug("No steam_account_pairs in config file")
                return False

            for pair_data in pairs:
                if not pair_data.get('enabled', True):
                    continue  # Skip disabled pairs

                # Validate required fields
                required = ['af_username', 'af_password', 'gz_username', 'gz_password']
                if not all(pair_data.get(k) for k in required):
                    logger.warning(f"Skipping incomplete account pair: {pair_data.get('name', 'unnamed')}")
                    continue

                pair = AccountPair(
                    name=pair_data.get('name', f'Pair{len(self._pairs) + 1}'),
                    af_username=pair_data['af_username'],
                    af_password=pair_data['af_password'],
                    gz_username=pair_data['gz_username'],
                    gz_password=pair_data['gz_password'],
                )
                self._pairs.append(pair)

            if self._pairs:
                logger.info(f"Loaded {len(self._pairs)} Steam account pair(s) from config file")
                return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")

        return False

    def reload_from_config(self):
        """Reload account pairs from config file or environment (e.g., after config change)"""
        with self._allocation_lock:
            self._pairs.clear()
            # Keep existing allocations if the pairs still exist
            old_allocations = self._allocations.copy()
            self._allocations.clear()
            self._load_from_env()  # This now checks config file first

            # Restore allocations for pairs that still exist
            for sut_id, old_pair in old_allocations.items():
                for pair in self._pairs:
                    if pair.name == old_pair.name:
                        self._allocations[sut_id] = pair
                        break

            logger.info(f"Reloaded account pool: {len(self._pairs)} pairs configured")

    # Alias for backward compatibility
    reload_from_env = reload_from_config

    @property
    def available_pairs(self) -> int:
        """Number of account pairs available for allocation"""
        with self._allocation_lock:
            allocated = set(id(p) for p in self._allocations.values())
            return sum(1 for p in self._pairs if id(p) not in allocated)

    @property
    def total_pairs(self) -> int:
        """Total number of configured account pairs"""
        return len(self._pairs)

    def get_allocation_status(self) -> Dict[str, str]:
        """Get current allocation status: {sut_id: pair_name}"""
        with self._allocation_lock:
            return {sut_id: pair.name for sut_id, pair in self._allocations.items()}

    def acquire_account_pair(self, sut_id: str) -> bool:
        """
        Acquire an account pair for a SUT.

        Args:
            sut_id: Unique identifier for the SUT (e.g., IP address or device ID)

        Returns:
            True if a pair was acquired, False if none available
        """
        with self._allocation_lock:
            # Check if already allocated
            if sut_id in self._allocations:
                logger.debug(f"SUT {sut_id} already has pair {self._allocations[sut_id].name}")
                return True

            # Find an unallocated pair
            allocated_pairs = set(id(p) for p in self._allocations.values())
            for pair in self._pairs:
                if id(pair) not in allocated_pairs:
                    self._allocations[sut_id] = pair
                    logger.info(f"Allocated account pair '{pair.name}' to SUT {sut_id}")
                    return True

            logger.warning(f"No account pairs available for SUT {sut_id}")
            return False

    def release_account_pair(self, sut_id: str) -> bool:
        """
        Release the account pair allocated to a SUT.

        Args:
            sut_id: Unique identifier for the SUT

        Returns:
            True if released, False if no allocation existed
        """
        with self._allocation_lock:
            if sut_id in self._allocations:
                pair = self._allocations.pop(sut_id)
                logger.info(f"Released account pair '{pair.name}' from SUT {sut_id}")
                return True
            return False

    def get_account_for_game(self, sut_id: str, game_name: str) -> Optional[Tuple[str, str]]:
        """
        Get the appropriate Steam account for a game on a SUT.

        Games are split by first letter:
        - A-F: Uses the af_account (e.g., BMW, Cyberpunk, Far Cry)
        - G-Z: Uses the gz_account (e.g., Hitman, RDR2, SOTR)

        Args:
            sut_id: Unique identifier for the SUT
            game_name: Name of the game to launch

        Returns:
            Tuple of (username, password) or None if no allocation
        """
        with self._allocation_lock:
            pair = self._allocations.get(sut_id)
            if not pair:
                logger.warning(f"No account pair allocated for SUT {sut_id}")
                return None

            # Determine which account to use based on first letter
            first_letter = game_name[0].upper() if game_name else 'A'

            if 'A' <= first_letter <= 'F':
                logger.debug(f"Game '{game_name}' ({first_letter}) -> A-F account: {pair.af_username}")
                return (pair.af_username, pair.af_password)
            else:
                logger.debug(f"Game '{game_name}' ({first_letter}) -> G-Z account: {pair.gz_username}")
                return (pair.gz_username, pair.gz_password)

    def get_current_account(self, sut_id: str, game_name: str) -> Optional[str]:
        """
        Get just the username for logging purposes.

        Args:
            sut_id: Unique identifier for the SUT
            game_name: Name of the game

        Returns:
            Username or None
        """
        result = self.get_account_for_game(sut_id, game_name)
        return result[0] if result else None

    def has_allocation(self, sut_id: str) -> bool:
        """Check if a SUT has an allocated account pair"""
        with self._allocation_lock:
            return sut_id in self._allocations

    def is_configured(self) -> bool:
        """Check if any account pairs are configured"""
        return len(self._pairs) > 0

    def mark_account_externally_busy(self, sut_id: str, username: str, game_name: str = None):
        """
        Mark a Steam account as externally busy (in use on another device).

        This is called when Steam login fails with "account in use on another device".

        Args:
            sut_id: SUT that reported the conflict
            username: Steam username that is in use elsewhere
            game_name: Game that was being launched (for logging)
        """
        with self._allocation_lock:
            username_lower = username.lower()
            if username_lower not in self._externally_busy:
                self._externally_busy[username_lower] = set()
            self._externally_busy[username_lower].add(sut_id)
            logger.warning(f"Marked account '{username}' as externally busy (reported by SUT {sut_id})")
            if game_name:
                logger.warning(f"Game: {game_name}")

    def is_account_externally_busy(self, username: str) -> bool:
        """Check if a Steam account is marked as externally busy."""
        with self._allocation_lock:
            return username.lower() in self._externally_busy

    def clear_externally_busy(self, username: str = None):
        """
        Clear externally busy status for an account (or all accounts).

        Call this when:
        - An account successfully logs in (conflict may have resolved)
        - At the start of a new automation session

        Args:
            username: Specific account to clear, or None to clear all
        """
        with self._allocation_lock:
            if username:
                self._externally_busy.pop(username.lower(), None)
                logger.info(f"Cleared externally busy status for '{username}'")
            else:
                self._externally_busy.clear()
                logger.info("Cleared all externally busy account statuses")

    def try_alternative_account(self, sut_id: str, game_name: str) -> Optional[Tuple[str, str]]:
        """
        Try to get an alternative account for a SUT when the current one is in use elsewhere.

        This attempts to allocate a different account pair to the SUT.

        Args:
            sut_id: SUT that needs a new account
            game_name: Game being launched (determines A-F vs G-Z account)

        Returns:
            Tuple of (username, password) for the new account, or None if no alternatives
        """
        with self._allocation_lock:
            current_pair = self._allocations.get(sut_id)
            if not current_pair:
                logger.warning(f"No current allocation for SUT {sut_id}, cannot try alternative")
                return None

            # Get the username that failed (based on game's first letter)
            first_letter = game_name[0].upper() if game_name else 'A'
            if 'A' <= first_letter <= 'F':
                failed_username = current_pair.af_username.lower()
            else:
                failed_username = current_pair.gz_username.lower()

            # Find pairs that are not allocated and don't have the failed username marked busy
            allocated_pair_ids = set(id(p) for p in self._allocations.values())

            for pair in self._pairs:
                if id(pair) in allocated_pair_ids:
                    continue  # Already allocated

                # Check if this pair's relevant account is externally busy
                if 'A' <= first_letter <= 'F':
                    candidate_username = pair.af_username.lower()
                    candidate_password = pair.af_password
                else:
                    candidate_username = pair.gz_username.lower()
                    candidate_password = pair.gz_password

                if candidate_username in self._externally_busy:
                    logger.debug(f"Skipping pair '{pair.name}' - account '{candidate_username}' is externally busy")
                    continue

                # Found a viable alternative - switch to this pair
                logger.info(f"Switching SUT {sut_id} from pair '{current_pair.name}' to '{pair.name}'")
                self._allocations[sut_id] = pair

                if 'A' <= first_letter <= 'F':
                    return (pair.af_username, pair.af_password)
                else:
                    return (pair.gz_username, pair.gz_password)

            logger.error(f"No alternative account pairs available for SUT {sut_id}")
            return None

    def get_externally_busy_accounts(self) -> Dict[str, list]:
        """Get list of externally busy accounts and which SUTs reported them."""
        with self._allocation_lock:
            return {user: list(suts) for user, suts in self._externally_busy.items()}

    def get_account_by_game_type(self, game_name: str) -> Optional[Tuple[str, str]]:
        """
        Get Steam account credentials based on game type (A-F or G-Z).

        This method doesn't require per-SUT allocation - it's used when
        account_scheduler has already granted access to the account TYPE.

        Args:
            game_name: Name of the game to get credentials for

        Returns:
            Tuple of (username, password) or None if no pairs configured
        """
        with self._allocation_lock:
            if not self._pairs:
                logger.warning("No Steam account pairs configured")
                return None

            # Use the first configured pair
            pair = self._pairs[0]

            # Determine which account to use based on first letter
            first_letter = game_name[0].upper() if game_name else 'A'

            if 'A' <= first_letter <= 'F':
                logger.debug(f"Game '{game_name}' ({first_letter}) -> A-F account: {pair.af_username}")
                return (pair.af_username, pair.af_password)
            else:
                logger.debug(f"Game '{game_name}' ({first_letter}) -> G-Z account: {pair.gz_username}")
                return (pair.gz_username, pair.gz_password)


# Convenience function
def get_account_pool() -> AccountPoolManager:
    """Get the global account pool manager instance"""
    return AccountPoolManager.get_instance()
