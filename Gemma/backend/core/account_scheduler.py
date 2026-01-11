"""
Steam Account Scheduler for Multi-SUT Parallel Execution

Manages Steam account locks across multiple SUTs. Steam only allows one account
to be logged in on one machine at a time, so we need to coordinate which SUT
uses which account.

Account Split:
- Account 1 (AF): Games starting with A-F
- Account 2 (GZ): Games starting with G-Z

Usage:
    scheduler = get_account_scheduler()

    # Try to acquire account for a game
    if scheduler.try_acquire(sut_ip, game_name):
        # Run the game
        ...
        # Release when done
        scheduler.release(sut_ip, game_name)
    else:
        # Account is busy, wait or try later
        ...
"""

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class AccountType(Enum):
    """Steam account type based on game first letter"""
    AF = "af"  # Games A-F (Account 1)
    GZ = "gz"  # Games G-Z (Account 2)


@dataclass
class AccountLock:
    """Tracks which SUT holds a Steam account"""
    account_type: AccountType
    holder_sut: Optional[str] = None
    game_running: Optional[str] = None
    locked_at: Optional[datetime] = None

    @property
    def is_locked(self) -> bool:
        return self.holder_sut is not None

    def acquire(self, sut_ip: str, game_name: str) -> bool:
        """Try to acquire this account for a SUT"""
        if self.holder_sut is None:
            self.holder_sut = sut_ip
            self.game_running = game_name
            self.locked_at = datetime.now()
            return True
        elif self.holder_sut == sut_ip:
            # Same SUT already holds it - update game
            self.game_running = game_name
            return True
        return False

    def release(self, sut_ip: str) -> bool:
        """Release this account from a SUT"""
        if self.holder_sut == sut_ip:
            old_game = self.game_running
            self.holder_sut = None
            self.game_running = None
            self.locked_at = None
            logger.info(f"Released {self.account_type.value.upper()} account from {sut_ip} (was running '{old_game}')")
            return True
        return False


class AccountScheduler:
    """
    Coordinates Steam account access across multiple SUTs.

    Thread-safe singleton that ensures only one SUT can use each account at a time.
    """

    _instance: Optional["AccountScheduler"] = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._lock = threading.RLock()
        self._af_lock = AccountLock(AccountType.AF)
        self._gz_lock = AccountLock(AccountType.GZ)

        # Callbacks for status updates
        self.on_account_acquired: Optional[callable] = None
        self.on_account_released: Optional[callable] = None
        self.on_account_waiting: Optional[callable] = None

        # Persistence file path - compute from module location
        # __file__ is Gemma/backend/core/account_scheduler.py
        # We need Gemma/logs/runs/account_locks.json
        self._locks_file = Path(__file__).parent.parent.parent / 'logs' / 'runs' / 'account_locks.json'

        # Clear any stale locks from previous session
        self._load_and_clear_stale_locks()

        logger.info("AccountScheduler initialized")

    def _save_locks(self):
        """Persist account locks to disk"""
        try:
            # Ensure directory exists
            self._locks_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'version': 1,
                'updated_at': datetime.now().isoformat(),
                'account_locks': {
                    'af': {
                        'sut_ip': self._af_lock.holder_sut,
                        'game_name': self._af_lock.game_running,
                        'locked_at': self._af_lock.locked_at.isoformat() if self._af_lock.locked_at else None
                    } if self._af_lock.is_locked else None,
                    'gz': {
                        'sut_ip': self._gz_lock.holder_sut,
                        'game_name': self._gz_lock.game_running,
                        'locked_at': self._gz_lock.locked_at.isoformat() if self._gz_lock.locked_at else None
                    } if self._gz_lock.is_locked else None
                }
            }

            # Atomic write
            temp_file = self._locks_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            temp_file.replace(self._locks_file)

            logger.debug(f"Saved account locks to disk")

        except Exception as e:
            logger.error(f"Failed to save account locks: {e}")

    def _load_and_clear_stale_locks(self):
        """Load account locks from disk and clear them (they're stale from previous session)"""
        if not self._locks_file.exists():
            logger.debug("No account_locks.json found")
            return

        try:
            with open(self._locks_file, 'r') as f:
                data = json.load(f)

            account_locks = data.get('account_locks', {})

            # Log stale locks before clearing
            if account_locks.get('af'):
                af_info = account_locks['af']
                logger.warning(f"Clearing stale AF account lock: was held by {af_info.get('sut_ip')} for '{af_info.get('game_name')}'")

            if account_locks.get('gz'):
                gz_info = account_locks['gz']
                logger.warning(f"Clearing stale GZ account lock: was held by {gz_info.get('sut_ip')} for '{gz_info.get('game_name')}'")

            # Clear the file (starting fresh)
            self._locks_file.unlink(missing_ok=True)
            logger.info("Cleared stale account locks")

        except Exception as e:
            logger.error(f"Failed to load account locks from storage: {e}")

    @classmethod
    def get_instance(cls) -> "AccountScheduler":
        """Get singleton instance"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)"""
        with cls._instance_lock:
            if cls._instance:
                cls._instance.release_all()
            cls._instance = None

    def get_account_type(self, game_name: str) -> AccountType:
        """Determine which account a game needs based on first letter"""
        first_letter = game_name[0].upper() if game_name else 'A'
        return AccountType.AF if first_letter <= 'F' else AccountType.GZ

    def _get_lock(self, account_type: AccountType) -> AccountLock:
        """Get the lock for an account type"""
        return self._af_lock if account_type == AccountType.AF else self._gz_lock

    def try_acquire(self, sut_ip: str, game_name: str) -> bool:
        """
        Try to acquire the account needed for a game.

        Returns:
            True if account acquired (can run the game)
            False if account is held by another SUT (must wait)
        """
        with self._lock:
            account_type = self.get_account_type(game_name)
            lock = self._get_lock(account_type)

            if lock.acquire(sut_ip, game_name):
                logger.info(f"SUT {sut_ip} acquired {account_type.value.upper()} account for '{game_name}'")
                self._save_locks()  # Persist lock state
                if self.on_account_acquired:
                    self.on_account_acquired(sut_ip, account_type.value, game_name)
                return True
            else:
                logger.debug(f"SUT {sut_ip} waiting for {account_type.value.upper()} account "
                           f"(held by {lock.holder_sut} for '{lock.game_running}')")
                if self.on_account_waiting:
                    self.on_account_waiting(sut_ip, account_type.value, lock.holder_sut)
                return False

    def release(self, sut_ip: str, game_name: str):
        """Release the account after a game completes"""
        with self._lock:
            account_type = self.get_account_type(game_name)
            lock = self._get_lock(account_type)

            if lock.release(sut_ip):
                self._save_locks()  # Persist lock release
                if self.on_account_released:
                    self.on_account_released(sut_ip, account_type.value)

    def release_all_for_sut(self, sut_ip: str):
        """Release all accounts held by a SUT (e.g., on disconnect/error)"""
        with self._lock:
            self._af_lock.release(sut_ip)
            self._gz_lock.release(sut_ip)

    def release_all(self):
        """Release all account locks"""
        with self._lock:
            if self._af_lock.holder_sut:
                self._af_lock.release(self._af_lock.holder_sut)
            if self._gz_lock.holder_sut:
                self._gz_lock.release(self._gz_lock.holder_sut)

    def get_holder(self, game_name: str) -> Optional[str]:
        """Get the SUT currently holding the account for a game"""
        with self._lock:
            account_type = self.get_account_type(game_name)
            lock = self._get_lock(account_type)
            return lock.holder_sut

    def is_available(self, game_name: str, for_sut: str) -> bool:
        """Check if the account for a game is available (or held by same SUT)"""
        with self._lock:
            account_type = self.get_account_type(game_name)
            lock = self._get_lock(account_type)
            return lock.holder_sut is None or lock.holder_sut == for_sut

    def get_status(self) -> Dict[str, dict]:
        """Get current status of both accounts"""
        with self._lock:
            return {
                "af": {
                    "locked": self._af_lock.is_locked,
                    "holder_sut": self._af_lock.holder_sut,
                    "game_running": self._af_lock.game_running,
                    "locked_at": self._af_lock.locked_at.isoformat() if self._af_lock.locked_at else None,
                },
                "gz": {
                    "locked": self._gz_lock.is_locked,
                    "holder_sut": self._gz_lock.holder_sut,
                    "game_running": self._gz_lock.game_running,
                    "locked_at": self._gz_lock.locked_at.isoformat() if self._gz_lock.locked_at else None,
                },
            }

    def can_run_parallel(self, sut_a: str, game_a: str, sut_b: str, game_b: str) -> bool:
        """Check if two games can run in parallel on different SUTs"""
        type_a = self.get_account_type(game_a)
        type_b = self.get_account_type(game_b)
        # Can run in parallel if they need different accounts
        return type_a != type_b


def get_account_scheduler() -> AccountScheduler:
    """Get the global account scheduler instance"""
    return AccountScheduler.get_instance()


def get_account_type_for_game(game_name: str) -> str:
    """Get account type string ('af' or 'gz') for a game"""
    first_letter = game_name[0].upper() if game_name else 'A'
    return 'af' if first_letter <= 'F' else 'gz'
