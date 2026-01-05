"""
Account Scheduler for Multi-SUT Automation

Manages Steam account locks across multiple SUTs. Unlike AccountPoolManager which
assigns entire account pairs to SUTs, this scheduler tracks which SUT holds which
individual account type (AF or GZ) at any moment.

Key difference from AccountPoolManager:
- AccountPoolManager: Assigns entire pair to SUT (for 2 concurrent games on SAME SUT)
- AccountScheduler: Tracks individual account locks (for multi-SUT parallel execution)

Steam Constraint: One account can only be logged in on ONE machine at a time.
- Account 1 (AF): Games A-F (Assassins Creed, Black Myth, Cyberpunk, Far Cry, etc.)
- Account 2 (GZ): Games G-Z (Hitman, RDR2, Shadow of Tomb Raider, etc.)

Smart Scheduling:
- SUTs with fewer remaining games for an account get priority
- When a SUT finishes all games for one account, it releases it for others
- Batching: Run all games for one account before switching
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from .account_pool import get_account_pool, AccountPoolManager

logger = logging.getLogger(__name__)


class AccountType(Enum):
    """Steam account type based on game first letter"""
    AF = "af"  # Games A-F
    GZ = "gz"  # Games G-Z


@dataclass
class AccountLock:
    """Tracks which SUT holds a Steam account"""
    account_type: AccountType
    holder_sut: Optional[str] = None
    holder_campaign: Optional[str] = None
    locked_at: Optional[datetime] = None
    game_running: Optional[str] = None

    @property
    def is_locked(self) -> bool:
        return self.holder_sut is not None

    def lock(self, sut_ip: str, campaign_id: str, game_name: str):
        """Lock this account to a SUT"""
        self.holder_sut = sut_ip
        self.holder_campaign = campaign_id
        self.locked_at = datetime.now()
        self.game_running = game_name

    def unlock(self):
        """Release this account"""
        self.holder_sut = None
        self.holder_campaign = None
        self.locked_at = None
        self.game_running = None


@dataclass
class WorkItem:
    """A single game work item for scheduling"""
    game_name: str
    account_type: AccountType
    priority: int = 0
    queued_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_game_name(cls, game_name: str, priority: int = 0) -> "WorkItem":
        """Create a WorkItem from game name, auto-detecting account type"""
        first_letter = game_name[0].upper() if game_name else 'A'
        account_type = AccountType.AF if first_letter <= 'F' else AccountType.GZ
        return cls(
            game_name=game_name,
            account_type=account_type,
            priority=priority,
        )


@dataclass
class SUTWorkQueue:
    """Work queue for a single SUT in a multi-SUT campaign"""
    sut_ip: str
    pending_games: List[WorkItem] = field(default_factory=list)
    current_work: Optional[WorkItem] = None
    current_run_id: Optional[str] = None
    completed_games: List[str] = field(default_factory=list)
    failed_games: List[str] = field(default_factory=list)
    current_account: Optional[AccountType] = None

    @property
    def games_on_af(self) -> List[str]:
        """Games requiring A-F account"""
        return [w.game_name for w in self.pending_games if w.account_type == AccountType.AF]

    @property
    def games_on_gz(self) -> List[str]:
        """Games requiring G-Z account"""
        return [w.game_name for w in self.pending_games if w.account_type == AccountType.GZ]

    @property
    def remaining_count(self) -> int:
        """Total remaining games"""
        return len(self.pending_games)

    def remaining_for_account(self, account_type: AccountType) -> int:
        """Count remaining games for a specific account type"""
        return sum(1 for w in self.pending_games if w.account_type == account_type)

    def pop_next_for_account(self, account_type: AccountType) -> Optional[WorkItem]:
        """Remove and return the next game for a specific account type"""
        for i, work in enumerate(self.pending_games):
            if work.account_type == account_type:
                return self.pending_games.pop(i)
        return None

    def sort_by_account_batching(self):
        """Sort pending games to batch by account type"""
        # Group by account type, preserving order within each group
        af_games = [w for w in self.pending_games if w.account_type == AccountType.AF]
        gz_games = [w for w in self.pending_games if w.account_type == AccountType.GZ]

        # Put the account with more games first (to minimize switches)
        if len(af_games) >= len(gz_games):
            self.pending_games = af_games + gz_games
        else:
            self.pending_games = gz_games + af_games


class AccountScheduler:
    """
    Manages Steam account allocation across multiple SUTs.

    Thread-safe scheduler that:
    - Tracks which SUT holds which account (AF or GZ)
    - Implements smart batching (run all games for one account before switching)
    - Implements priority yield (SUT with fewer remaining games gets priority)
    - Integrates with AccountPoolManager for actual credentials
    """

    _instance: Optional["AccountScheduler"] = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self.af_lock = AccountLock(AccountType.AF)
        self.gz_lock = AccountLock(AccountType.GZ)
        self._lock = threading.RLock()
        self._account_pool = get_account_pool()

        # Callbacks for events
        self.on_account_acquired: Optional[callable] = None
        self.on_account_released: Optional[callable] = None
        self.on_sut_waiting: Optional[callable] = None

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
            cls._instance = None

    def _get_lock_for_account(self, account_type: AccountType) -> AccountLock:
        """Get the AccountLock object for an account type"""
        return self.af_lock if account_type == AccountType.AF else self.gz_lock

    def request_account(
        self,
        sut_ip: str,
        account_type: AccountType,
        game_name: str,
        campaign_id: str
    ) -> bool:
        """
        Try to acquire an account for a SUT.

        Args:
            sut_ip: SUT requesting the account
            account_type: AF or GZ account
            game_name: Game being launched
            campaign_id: Campaign this belongs to

        Returns:
            True if account acquired, False if must wait
        """
        with self._lock:
            lock = self._get_lock_for_account(account_type)

            if lock.holder_sut is None:
                # Account is free - acquire it
                lock.lock(sut_ip, campaign_id, game_name)
                logger.info(f"SUT {sut_ip} acquired {account_type.value.upper()} account for '{game_name}'")

                if self.on_account_acquired:
                    self.on_account_acquired(sut_ip, account_type, game_name)

                return True

            elif lock.holder_sut == sut_ip:
                # Same SUT already holds it - just update game
                lock.game_running = game_name
                logger.debug(f"SUT {sut_ip} continuing with {account_type.value.upper()} account for '{game_name}'")
                return True

            else:
                # Another SUT holds it - must wait
                logger.info(f"SUT {sut_ip} waiting for {account_type.value.upper()} account (held by {lock.holder_sut})")

                if self.on_sut_waiting:
                    self.on_sut_waiting(sut_ip, account_type, lock.holder_sut)

                return False

    def release_account(self, sut_ip: str, account_type: AccountType) -> bool:
        """
        Release an account when game completes.

        Args:
            sut_ip: SUT releasing the account
            account_type: AF or GZ account

        Returns:
            True if released, False if not held by this SUT
        """
        with self._lock:
            lock = self._get_lock_for_account(account_type)

            if lock.holder_sut == sut_ip:
                old_game = lock.game_running
                lock.unlock()
                logger.info(f"SUT {sut_ip} released {account_type.value.upper()} account (was running '{old_game}')")

                if self.on_account_released:
                    self.on_account_released(sut_ip, account_type)

                return True

            return False

    def release_all_for_sut(self, sut_ip: str):
        """Release all accounts held by a SUT"""
        with self._lock:
            self.release_account(sut_ip, AccountType.AF)
            self.release_account(sut_ip, AccountType.GZ)

    def get_credentials_for_game(
        self,
        sut_ip: str,
        game_name: str
    ) -> Optional[Tuple[str, str]]:
        """
        Get Steam credentials for a game.

        Delegates to AccountPoolManager for actual credentials.

        Args:
            sut_ip: SUT running the game
            game_name: Game being launched

        Returns:
            Tuple of (username, password) or None
        """
        # Ensure SUT has an account pair allocated
        if not self._account_pool.has_allocation(sut_ip):
            if not self._account_pool.acquire_account_pair(sut_ip):
                logger.error(f"Failed to acquire account pair for SUT {sut_ip}")
                return None

        return self._account_pool.get_account_for_game(sut_ip, game_name)

    def get_next_work_for_sut(
        self,
        sut_ip: str,
        work_queue: SUTWorkQueue,
        all_work_queues: Dict[str, SUTWorkQueue]
    ) -> Optional[WorkItem]:
        """
        Get the next game this SUT should run.

        Smart scheduling logic:
        1. If holding an account, run remaining games for that account first
        2. Before switching accounts, check if another SUT needs this account more
        3. If not holding, try to get a free account
        4. If all accounts busy, return None (SUT should wait)

        Args:
            sut_ip: SUT requesting work
            work_queue: This SUT's work queue
            all_work_queues: All SUT work queues (for priority decisions)

        Returns:
            Next WorkItem or None if must wait
        """
        with self._lock:
            if not work_queue.pending_games:
                return None

            # Check what we're currently holding
            holding_af = self.af_lock.holder_sut == sut_ip
            holding_gz = self.gz_lock.holder_sut == sut_ip

            # If holding AF, prioritize AF games
            if holding_af:
                af_remaining = work_queue.remaining_for_account(AccountType.AF)

                if af_remaining > 0:
                    # Check if we should yield to another SUT with fewer AF games
                    yield_to = self._should_yield_account(
                        sut_ip, AccountType.AF, work_queue, all_work_queues
                    )
                    if yield_to:
                        logger.info(f"SUT {sut_ip} yielding AF account to {yield_to} (has fewer games)")
                        self.release_account(sut_ip, AccountType.AF)
                    else:
                        # Continue with AF games
                        return work_queue.pop_next_for_account(AccountType.AF)
                else:
                    # No more AF games - release
                    self.release_account(sut_ip, AccountType.AF)

            # If holding GZ, prioritize GZ games
            if holding_gz:
                gz_remaining = work_queue.remaining_for_account(AccountType.GZ)

                if gz_remaining > 0:
                    # Check if we should yield
                    yield_to = self._should_yield_account(
                        sut_ip, AccountType.GZ, work_queue, all_work_queues
                    )
                    if yield_to:
                        logger.info(f"SUT {sut_ip} yielding GZ account to {yield_to} (has fewer games)")
                        self.release_account(sut_ip, AccountType.GZ)
                    else:
                        # Continue with GZ games
                        return work_queue.pop_next_for_account(AccountType.GZ)
                else:
                    # No more GZ games - release
                    self.release_account(sut_ip, AccountType.GZ)

            # Not holding anything useful - try to acquire
            # Prioritize account with more remaining games (to batch)
            af_count = work_queue.remaining_for_account(AccountType.AF)
            gz_count = work_queue.remaining_for_account(AccountType.GZ)

            if af_count == 0 and gz_count == 0:
                return None

            # Try account with more games first
            first_try = AccountType.AF if af_count >= gz_count else AccountType.GZ
            second_try = AccountType.GZ if first_try == AccountType.AF else AccountType.AF

            for account_type in [first_try, second_try]:
                if work_queue.remaining_for_account(account_type) == 0:
                    continue

                # Try to acquire this account
                work_item = work_queue.pending_games[0]  # Peek at first item of this type
                for item in work_queue.pending_games:
                    if item.account_type == account_type:
                        work_item = item
                        break

                if self.request_account(sut_ip, account_type, work_item.game_name, ""):
                    return work_queue.pop_next_for_account(account_type)

            # All accounts busy - return None
            return None

    def _should_yield_account(
        self,
        holder_sut: str,
        account_type: AccountType,
        holder_queue: SUTWorkQueue,
        all_work_queues: Dict[str, SUTWorkQueue]
    ) -> Optional[str]:
        """
        Determine if holder should yield account to another SUT.

        Yield if another SUT:
        - Has fewer remaining games for this account type
        - Is waiting (not currently running a game)

        Args:
            holder_sut: SUT currently holding the account
            account_type: Account type to check
            holder_queue: Holder's work queue
            all_work_queues: All SUT work queues

        Returns:
            SUT IP to yield to, or None
        """
        holder_remaining = holder_queue.remaining_for_account(account_type)

        best_candidate = None
        best_remaining = holder_remaining

        for sut_ip, queue in all_work_queues.items():
            if sut_ip == holder_sut:
                continue

            # Skip SUTs currently running a game
            if queue.current_run_id is not None:
                continue

            sut_remaining = queue.remaining_for_account(account_type)

            # Only yield if other SUT has fewer games AND needs this account
            if 0 < sut_remaining < best_remaining:
                best_candidate = sut_ip
                best_remaining = sut_remaining

        return best_candidate

    def get_account_status(self) -> Dict[str, dict]:
        """Get current status of both accounts"""
        with self._lock:
            return {
                "af": {
                    "locked": self.af_lock.is_locked,
                    "holder_sut": self.af_lock.holder_sut,
                    "holder_campaign": self.af_lock.holder_campaign,
                    "game_running": self.af_lock.game_running,
                    "locked_at": self.af_lock.locked_at.isoformat() if self.af_lock.locked_at else None,
                },
                "gz": {
                    "locked": self.gz_lock.is_locked,
                    "holder_sut": self.gz_lock.holder_sut,
                    "holder_campaign": self.gz_lock.holder_campaign,
                    "game_running": self.gz_lock.game_running,
                    "locked_at": self.gz_lock.locked_at.isoformat() if self.gz_lock.locked_at else None,
                },
            }

    def is_account_available(self, account_type: AccountType) -> bool:
        """Check if an account is available"""
        with self._lock:
            lock = self._get_lock_for_account(account_type)
            return not lock.is_locked


# Convenience function
def get_account_scheduler() -> AccountScheduler:
    """Get the global account scheduler instance"""
    return AccountScheduler.get_instance()


def get_account_type_for_game(game_name: str) -> AccountType:
    """Determine account type for a game based on first letter"""
    first_letter = game_name[0].upper() if game_name else 'A'
    return AccountType.AF if first_letter <= 'F' else AccountType.GZ
