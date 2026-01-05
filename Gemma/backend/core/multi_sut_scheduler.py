"""
Multi-SUT Scheduler

Orchestrates parallel game automation across multiple SUTs with intelligent
Steam account scheduling. Each SUT runs one game at a time, but multiple
SUTs can run simultaneously (subject to account constraints).

Key Features:
- Parallel execution across N SUTs
- Smart account scheduling (A-F vs G-Z accounts)
- Priority yield (SUT with fewer games gets priority)
- Account batching (run all games for one account before switching)
- Backward compatible (existing single-SUT campaigns work unchanged)

Example Flow:
    User creates campaign:
      SUTs: [192.168.0.102, 192.168.0.103]
      Games: [Cyberpunk 2077 (C), Far Cry 6 (F), Hitman 3 (H), RDR2 (R)]

    Initial assignment:
      SUT 102: AF account → runs Cyberpunk, then Far Cry
      SUT 103: GZ account → runs Hitman, then RDR2
      (Both run in parallel - different accounts)

    After SUT 103 finishes (Hitman + RDR2):
      SUT 103 waits (needs AF account for Cyberpunk, Far Cry)
      SUT 102 still running Far Cry

    After SUT 102 finishes (Cyberpunk + Far Cry):
      Accounts swap - both continue in parallel
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable, Tuple, Set

from .account_scheduler import (
    AccountScheduler,
    AccountType,
    SUTWorkQueue,
    WorkItem,
    get_account_scheduler,
    get_account_type_for_game,
)

logger = logging.getLogger(__name__)


class MultiSUTCampaignStatus(Enum):
    """Status of a multi-SUT campaign"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"
    STOPPED = "stopped"


# Game name abbreviations for auto-naming
GAME_ABBREVIATIONS = {
    'assassins-creed-mirage': 'ACM',
    'black-myth-wukong': 'BMW',
    'cyberpunk-2077': 'CP77',
    'cyberpunk 2077': 'CP77',
    'counter-strike-2': 'CS2',
    'far-cry-6': 'FC6',
    'far cry 6': 'FC6',
    'hitman-3': 'HM3',
    'hitman 3': 'HM3',
    'horizon-zero-dawn-remastered': 'HZD',
    'red-dead-redemption-2': 'RDR2',
    'shadow-of-the-tomb-raider': 'SOTR',
    'shadow-of-tomb-raider': 'SOTR',
    'sid-meier-civ-6': 'CIV6',
    'tiny-tina-wonderlands': 'TTW',
    'final-fantasy-xiv-dawntrail': 'FFXIV',
    'f1-24': 'F124',
}


def abbreviate_game(game_name: str) -> str:
    """Get short abbreviation for a game name"""
    normalized = game_name.lower().replace(' ', '-')
    if normalized in GAME_ABBREVIATIONS:
        return GAME_ABBREVIATIONS[normalized]
    if game_name.lower() in GAME_ABBREVIATIONS:
        return GAME_ABBREVIATIONS[game_name.lower()]
    # Generate abbreviation from first letters
    words = game_name.replace('-', ' ').split()
    return ''.join(w[0].upper() for w in words[:4])


@dataclass
class MultiSUTCampaign:
    """A campaign spanning multiple SUTs"""
    campaign_id: str
    name: str
    suts: List[str]  # List of SUT IPs
    games: List[str]  # All games to run on each SUT
    iterations_per_game: int
    quality: Optional[str] = None
    resolution: Optional[str] = None
    status: MultiSUTCampaignStatus = MultiSUTCampaignStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Per-SUT work tracking
    sut_work: Dict[str, SUTWorkQueue] = field(default_factory=dict)

    # Run tracking
    run_ids: List[str] = field(default_factory=list)

    @property
    def total_games(self) -> int:
        """Total games across all SUTs"""
        return len(self.suts) * len(self.games)

    @property
    def completed_games(self) -> int:
        """Count of completed games across all SUTs"""
        return sum(len(q.completed_games) for q in self.sut_work.values())

    @property
    def failed_games(self) -> int:
        """Count of failed games across all SUTs"""
        return sum(len(q.failed_games) for q in self.sut_work.values())

    @property
    def pending_games(self) -> int:
        """Count of pending games across all SUTs"""
        return sum(q.remaining_count for q in self.sut_work.values())

    @property
    def progress_percent(self) -> float:
        """Overall progress percentage"""
        if self.total_games == 0:
            return 100.0
        done = self.completed_games + self.failed_games
        return (done / self.total_games) * 100.0

    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "suts": self.suts,
            "games": self.games,
            "iterations_per_game": self.iterations_per_game,
            "quality": self.quality,
            "resolution": self.resolution,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "total_games": self.total_games,
            "completed_games": self.completed_games,
            "failed_games": self.failed_games,
            "pending_games": self.pending_games,
            "progress_percent": self.progress_percent,
            "run_ids": self.run_ids,
            "sut_status": {
                sut_ip: {
                    "pending_count": queue.remaining_count,
                    "completed_count": len(queue.completed_games),
                    "failed_count": len(queue.failed_games),
                    "current_game": queue.current_work.game_name if queue.current_work else None,
                    "current_run_id": queue.current_run_id,
                    "current_account": queue.current_account.value if queue.current_account else None,
                    "pending_games_af": queue.games_on_af,
                    "pending_games_gz": queue.games_on_gz,
                }
                for sut_ip, queue in self.sut_work.items()
            },
        }


class SUTWorker(threading.Thread):
    """
    Worker thread for a single SUT in a multi-SUT campaign.

    Runs as a daemon thread, continuously checking for work and executing games.
    """

    def __init__(
        self,
        sut_ip: str,
        scheduler: "MultiSUTScheduler",
        on_run_request: Callable[[str, str, int, Optional[str], Optional[str], Optional[str]], str],
        on_run_wait: Callable[[str], Tuple[bool, Optional[str]]],
    ):
        """
        Args:
            sut_ip: IP address of this SUT
            scheduler: Parent MultiSUTScheduler
            on_run_request: Callback to request a new run
                Args: (game_name, sut_ip, iterations, campaign_id, quality, resolution)
                Returns: run_id
            on_run_wait: Callback to wait for run completion
                Args: (run_id)
                Returns: (success, error_message)
        """
        super().__init__(name=f"SUTWorker-{sut_ip}", daemon=True)
        self.sut_ip = sut_ip
        self.scheduler = scheduler
        self.on_run_request = on_run_request
        self.on_run_wait = on_run_wait

        self._running = True
        self._wake_event = threading.Event()
        self._current_campaign: Optional[str] = None

    def stop(self):
        """Stop the worker thread"""
        self._running = False
        self._wake_event.set()

    def wake(self):
        """Wake the worker to check for new work"""
        self._wake_event.set()

    def set_campaign(self, campaign_id: Optional[str]):
        """Set the current campaign this worker is processing"""
        self._current_campaign = campaign_id
        self._wake_event.set()

    def run(self):
        """Main worker loop"""
        logger.info(f"SUTWorker started for {self.sut_ip}")

        while self._running:
            try:
                # Get next work item
                result = self.scheduler.get_next_work(self.sut_ip)

                if result is None:
                    # No work available - wait for wake signal
                    self._wake_event.clear()
                    self._wake_event.wait(timeout=2.0)
                    continue

                campaign_id, work_item = result

                # Execute the work item
                success = self._execute_work(campaign_id, work_item)

                # Report completion
                self.scheduler.notify_work_completed(
                    self.sut_ip,
                    campaign_id,
                    work_item,
                    success,
                )

            except Exception as e:
                logger.error(f"Error in SUTWorker {self.sut_ip}: {e}", exc_info=True)
                time.sleep(1.0)  # Prevent tight error loop

        logger.info(f"SUTWorker stopped for {self.sut_ip}")

    def _execute_work(self, campaign_id: str, work_item: WorkItem) -> bool:
        """Execute a single work item"""
        campaign = self.scheduler.get_campaign(campaign_id)
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return False

        logger.info(f"SUT {self.sut_ip} starting '{work_item.game_name}' "
                   f"(account: {work_item.account_type.value.upper()})")

        try:
            # Request the run
            run_id = self.on_run_request(
                work_item.game_name,
                self.sut_ip,
                campaign.iterations_per_game,
                campaign_id,
                campaign.quality,
                campaign.resolution,
            )

            # Notify scheduler that run started
            self.scheduler.notify_work_started(
                self.sut_ip,
                campaign_id,
                work_item,
                run_id,
            )

            # Wait for run completion
            success, error = self.on_run_wait(run_id)

            if success:
                logger.info(f"SUT {self.sut_ip} completed '{work_item.game_name}'")
            else:
                logger.error(f"SUT {self.sut_ip} failed '{work_item.game_name}': {error}")

            return success

        except Exception as e:
            logger.error(f"Failed to execute '{work_item.game_name}' on SUT {self.sut_ip}: {e}")
            return False


class MultiSUTScheduler:
    """
    Orchestrates parallel automation across multiple SUTs.

    Manages multiple SUTWorker threads, one per SUT, and coordinates
    work distribution using AccountScheduler for Steam account management.
    """

    _instance: Optional["MultiSUTScheduler"] = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        on_run_request: Optional[Callable] = None,
        on_run_wait: Optional[Callable] = None,
    ):
        """
        Args:
            on_run_request: Callback to request a new run via RunManager
            on_run_wait: Callback to wait for run completion
        """
        self.account_scheduler = get_account_scheduler()

        self.on_run_request = on_run_request
        self.on_run_wait = on_run_wait

        self.active_campaigns: Dict[str, MultiSUTCampaign] = {}
        self.campaign_history: List[MultiSUTCampaign] = []

        self.sut_workers: Dict[str, SUTWorker] = {}
        self._lock = threading.RLock()

        # Event callbacks
        self.on_campaign_started: Optional[Callable] = None
        self.on_campaign_progress: Optional[Callable] = None
        self.on_campaign_completed: Optional[Callable] = None
        self.on_sut_work_started: Optional[Callable] = None
        self.on_sut_work_completed: Optional[Callable] = None

    @classmethod
    def get_instance(cls) -> "MultiSUTScheduler":
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
                cls._instance.shutdown()
            cls._instance = None

    def set_callbacks(
        self,
        on_run_request: Callable,
        on_run_wait: Callable,
    ):
        """Set the run management callbacks"""
        self.on_run_request = on_run_request
        self.on_run_wait = on_run_wait

    def create_campaign(
        self,
        suts: List[str],
        games: List[str],
        iterations: int = 1,
        name: Optional[str] = None,
        quality: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> MultiSUTCampaign:
        """
        Create a multi-SUT campaign.

        All games will run on all SUTs in parallel (subject to account constraints).

        Args:
            suts: List of SUT IP addresses
            games: List of game names to run
            iterations: Iterations per game
            name: Campaign name (auto-generated if not provided)
            quality: Preset quality (low/medium/high/ultra)
            resolution: Target resolution (720p/1080p/1440p/2160p)

        Returns:
            Created MultiSUTCampaign
        """
        if not suts:
            raise ValueError("At least one SUT is required")
        if not games:
            raise ValueError("At least one game is required")
        if not self.on_run_request or not self.on_run_wait:
            raise ValueError("Run callbacks not configured")

        campaign_id = str(uuid.uuid4())

        # Auto-generate name if not provided
        if not name:
            sut_count = len(suts)
            game_abbrevs = [abbreviate_game(g) for g in games[:3]]
            name = f"{sut_count}SUT-" + "-".join(game_abbrevs)
            if len(games) > 3:
                name += f"+{len(games) - 3}"

        # Build work queues for each SUT
        sut_work = {}
        for sut_ip in suts:
            queue = SUTWorkQueue(sut_ip=sut_ip)

            # Add all games as work items
            for game in games:
                work_item = WorkItem.from_game_name(game)
                queue.pending_games.append(work_item)

            # Sort for optimal batching
            queue.sort_by_account_batching()
            sut_work[sut_ip] = queue

        campaign = MultiSUTCampaign(
            campaign_id=campaign_id,
            name=name,
            suts=suts,
            games=games,
            iterations_per_game=iterations,
            quality=quality,
            resolution=resolution,
            sut_work=sut_work,
        )

        with self._lock:
            self.active_campaigns[campaign_id] = campaign

            # Start workers for each SUT
            for sut_ip in suts:
                self._ensure_worker(sut_ip)

            campaign.status = MultiSUTCampaignStatus.RUNNING

        logger.info(f"Created multi-SUT campaign '{name}' ({campaign_id}): "
                   f"{len(suts)} SUTs x {len(games)} games = {campaign.total_games} total runs")

        if self.on_campaign_started:
            self.on_campaign_started(campaign)

        # Wake all workers
        for sut_ip in suts:
            if sut_ip in self.sut_workers:
                self.sut_workers[sut_ip].wake()

        return campaign

    def _ensure_worker(self, sut_ip: str):
        """Ensure a worker exists for a SUT"""
        if sut_ip not in self.sut_workers:
            worker = SUTWorker(
                sut_ip=sut_ip,
                scheduler=self,
                on_run_request=self.on_run_request,
                on_run_wait=self.on_run_wait,
            )
            self.sut_workers[sut_ip] = worker
            worker.start()
            logger.info(f"Started worker for SUT {sut_ip}")

    def get_next_work(self, sut_ip: str) -> Optional[Tuple[str, WorkItem]]:
        """
        Get next work item for a SUT.

        Called by SUTWorker to get its next task.

        Args:
            sut_ip: SUT requesting work

        Returns:
            Tuple of (campaign_id, WorkItem) or None if no work
        """
        with self._lock:
            # Check all active campaigns for work
            for campaign_id, campaign in self.active_campaigns.items():
                if sut_ip not in campaign.sut_work:
                    continue

                if campaign.status != MultiSUTCampaignStatus.RUNNING:
                    continue

                work_queue = campaign.sut_work[sut_ip]

                if not work_queue.pending_games:
                    continue

                # Use account scheduler for smart work selection
                work_item = self.account_scheduler.get_next_work_for_sut(
                    sut_ip,
                    work_queue,
                    campaign.sut_work,
                )

                if work_item:
                    return (campaign_id, work_item)

            return None

    def notify_work_started(
        self,
        sut_ip: str,
        campaign_id: str,
        work_item: WorkItem,
        run_id: str,
    ):
        """Notify that a work item has started"""
        with self._lock:
            campaign = self.active_campaigns.get(campaign_id)
            if not campaign:
                return

            campaign.run_ids.append(run_id)

            work_queue = campaign.sut_work.get(sut_ip)
            if work_queue:
                work_queue.current_work = work_item
                work_queue.current_run_id = run_id
                work_queue.current_account = work_item.account_type

        if self.on_sut_work_started:
            self.on_sut_work_started(campaign_id, sut_ip, work_item.game_name, run_id)

    def notify_work_completed(
        self,
        sut_ip: str,
        campaign_id: str,
        work_item: WorkItem,
        success: bool,
    ):
        """Notify that a work item has completed"""
        with self._lock:
            campaign = self.active_campaigns.get(campaign_id)
            if not campaign:
                return

            work_queue = campaign.sut_work.get(sut_ip)
            if work_queue:
                # Track completion
                if success:
                    work_queue.completed_games.append(work_item.game_name)
                else:
                    work_queue.failed_games.append(work_item.game_name)

                work_queue.current_work = None
                work_queue.current_run_id = None

            # Release account
            self.account_scheduler.release_account(sut_ip, work_item.account_type)

            # Check if campaign is complete
            if campaign.pending_games == 0:
                self._complete_campaign(campaign)

        if self.on_sut_work_completed:
            self.on_sut_work_completed(
                campaign_id, sut_ip, work_item.game_name, success
            )

        if self.on_campaign_progress:
            self.on_campaign_progress(campaign_id, campaign.progress_percent)

        # Wake other workers in case accounts freed up
        self._wake_waiting_workers(campaign_id)

    def _complete_campaign(self, campaign: MultiSUTCampaign):
        """Mark a campaign as complete"""
        campaign.completed_at = datetime.now()

        if campaign.failed_games == 0:
            campaign.status = MultiSUTCampaignStatus.COMPLETED
        elif campaign.completed_games == 0:
            campaign.status = MultiSUTCampaignStatus.FAILED
        else:
            campaign.status = MultiSUTCampaignStatus.PARTIALLY_COMPLETED

        # Move to history
        del self.active_campaigns[campaign.campaign_id]
        self.campaign_history.append(campaign)

        logger.info(f"Campaign '{campaign.name}' completed: "
                   f"{campaign.completed_games}/{campaign.total_games} succeeded, "
                   f"{campaign.failed_games} failed")

        if self.on_campaign_completed:
            self.on_campaign_completed(campaign)

    def _wake_waiting_workers(self, campaign_id: str):
        """Wake workers that might be waiting for accounts"""
        with self._lock:
            campaign = self.active_campaigns.get(campaign_id)
            if not campaign:
                return

            for sut_ip in campaign.suts:
                worker = self.sut_workers.get(sut_ip)
                if worker:
                    worker.wake()

    def stop_campaign(self, campaign_id: str) -> bool:
        """
        Stop a multi-SUT campaign.

        Args:
            campaign_id: Campaign to stop

        Returns:
            True if stopped, False if not found
        """
        with self._lock:
            campaign = self.active_campaigns.get(campaign_id)
            if not campaign:
                return False

            campaign.status = MultiSUTCampaignStatus.STOPPED
            campaign.completed_at = datetime.now()

            # Release all accounts
            for sut_ip in campaign.suts:
                self.account_scheduler.release_all_for_sut(sut_ip)

            # Move to history
            del self.active_campaigns[campaign_id]
            self.campaign_history.append(campaign)

            logger.info(f"Campaign '{campaign.name}' stopped")

            return True

    def get_campaign(self, campaign_id: str) -> Optional[MultiSUTCampaign]:
        """Get a campaign by ID (active or history)"""
        with self._lock:
            if campaign_id in self.active_campaigns:
                return self.active_campaigns[campaign_id]

            for campaign in self.campaign_history:
                if campaign.campaign_id == campaign_id:
                    return campaign

            return None

    def get_active_campaigns(self) -> List[MultiSUTCampaign]:
        """Get all active campaigns"""
        with self._lock:
            return list(self.active_campaigns.values())

    def get_campaign_history(self, limit: int = 50) -> List[MultiSUTCampaign]:
        """Get campaign history"""
        with self._lock:
            return list(reversed(self.campaign_history[-limit:]))

    def get_account_status(self) -> dict:
        """Get current account lock status"""
        return self.account_scheduler.get_account_status()

    def shutdown(self):
        """Shutdown all workers"""
        logger.info("Shutting down MultiSUTScheduler")

        # Stop all workers
        for worker in self.sut_workers.values():
            worker.stop()

        # Wait for workers to finish
        for worker in self.sut_workers.values():
            worker.join(timeout=5.0)

        self.sut_workers.clear()

        # Release all accounts
        for campaign in self.active_campaigns.values():
            for sut_ip in campaign.suts:
                self.account_scheduler.release_all_for_sut(sut_ip)


# Convenience function
def get_multi_sut_scheduler() -> MultiSUTScheduler:
    """Get the global multi-SUT scheduler instance"""
    return MultiSUTScheduler.get_instance()
