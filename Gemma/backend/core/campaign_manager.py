"""
Campaign Manager - Manages multi-game campaign runs

A campaign is a collection of AutomationRuns (one per game) that are
executed sequentially on a single SUT. This allows users to benchmark
multiple games in one operation.
"""

import uuid
import logging
import threading
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

from .events import event_bus, EventType

logger = logging.getLogger(__name__)


class CampaignStatus(Enum):
    """Status of a campaign"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"
    STOPPED = "stopped"


@dataclass
class CampaignProgress:
    """Tracks progress of a campaign"""
    total_games: int = 0
    completed_games: int = 0
    failed_games: int = 0
    current_game: Optional[str] = None
    current_game_index: int = 0


@dataclass
class Campaign:
    """Represents a multi-game campaign run"""
    campaign_id: str
    name: str
    sut_ip: str
    sut_device_id: str
    games: List[str]
    iterations_per_game: int
    status: CampaignStatus = CampaignStatus.QUEUED
    run_ids: List[str] = field(default_factory=list)
    progress: CampaignProgress = field(default_factory=CampaignProgress)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    quality: Optional[str] = None  # 'low' | 'medium' | 'high' | 'ultra'
    resolution: Optional[str] = None  # '720p' | '1080p' | '1440p' | '2160p'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'campaign_id': self.campaign_id,
            'name': self.name,
            'sut_ip': self.sut_ip,
            'sut_device_id': self.sut_device_id,
            'games': self.games,
            'iterations_per_game': self.iterations_per_game,
            'status': self.status.value,
            'run_ids': self.run_ids,
            'progress': {
                'total_games': self.progress.total_games,
                'completed_games': self.progress.completed_games,
                'failed_games': self.progress.failed_games,
                'current_game': self.progress.current_game,
                'current_game_index': self.progress.current_game_index,
            },
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'completed_at': self.completed_at.isoformat() if self.completed_at and isinstance(self.completed_at, datetime) else self.completed_at,
            'error_message': self.error_message,
            'quality': self.quality,
            'resolution': self.resolution,
        }


class CampaignManager:
    """Manages multi-game campaign runs"""

    def __init__(self, run_manager):
        """
        Initialize campaign manager.

        Args:
            run_manager: Reference to the RunManager for queuing individual runs
        """
        self.run_manager = run_manager
        self.campaigns: Dict[str, Campaign] = {}
        self.campaign_history: List[Campaign] = []
        self._lock = threading.RLock()  # Use RLock to allow nested locking

        # Mapping from run_id to campaign_id for quick lookup on events
        self._run_to_campaign: Dict[str, str] = {}

        # Load campaign history from storage
        self._load_history_from_storage()

        # Subscribe to run events for real-time progress updates
        self._subscribe_to_events()

        logger.info("CampaignManager initialized")

    def _subscribe_to_events(self):
        """Subscribe to run events to update campaign progress in real-time"""
        event_bus.subscribe(EventType.AUTOMATION_STARTED, self._on_run_event)
        event_bus.subscribe(EventType.AUTOMATION_COMPLETED, self._on_run_event)
        event_bus.subscribe(EventType.AUTOMATION_FAILED, self._on_run_event)

    def _on_run_event(self, event):
        """Handle run events to update campaign progress"""
        run_id = event.data.get('run_id')
        if not run_id:
            return

        # Check if this run belongs to a campaign
        campaign_id = self._run_to_campaign.get(run_id)
        if not campaign_id:
            return

        # Update campaign progress
        with self._lock:
            campaign = self.campaigns.get(campaign_id)
            if campaign:
                logger.debug(f"Updating campaign {campaign_id[:8]} progress due to run event: {event.event_type.value}")
                self._update_campaign_progress(campaign)

    def _load_history_from_storage(self):
        """Load completed campaigns from persistent storage"""
        try:
            if not hasattr(self.run_manager, 'storage'):
                return

            campaign_dicts = self.run_manager.storage.load_campaign_history()
            for data in campaign_dicts:
                campaign = Campaign(
                    campaign_id=data['campaign_id'],
                    name=data['name'],
                    sut_ip=data['sut_ip'],
                    sut_device_id=data.get('sut_device_id', ''),
                    games=data['games'],
                    iterations_per_game=data.get('iterations_per_game', 1),
                    status=CampaignStatus(data['status']),
                    run_ids=data.get('run_ids', []),
                    quality=data.get('quality'),
                    resolution=data.get('resolution'),
                )
                # Set progress
                progress_data = data.get('progress', {})
                campaign.progress = CampaignProgress(
                    total_games=progress_data.get('total_games', len(data['games'])),
                    completed_games=progress_data.get('completed_games', 0),
                    failed_games=progress_data.get('failed_games', 0),
                )
                # Set timestamps
                if data.get('created_at'):
                    try:
                        campaign.created_at = datetime.fromisoformat(data['created_at'])
                    except:
                        pass
                if data.get('completed_at'):
                    try:
                        campaign.completed_at = datetime.fromisoformat(data['completed_at']) if isinstance(data['completed_at'], str) else data['completed_at']
                    except:
                        pass

                self.campaign_history.append(campaign)

            logger.info(f"Loaded {len(self.campaign_history)} campaigns from storage")
        except Exception as e:
            logger.error(f"Error loading campaign history: {e}")

    def create_campaign(
        self,
        sut_ip: str,
        sut_device_id: str,
        games: List[str],
        iterations: int,
        name: Optional[str] = None,
        quality: Optional[str] = None,
        resolution: Optional[str] = None,
        skip_steam_login: bool = False
    ) -> Campaign:
        """
        Create a new campaign and queue individual runs for each game.

        Args:
            sut_ip: IP address of the target SUT
            sut_device_id: Unique device ID of the SUT
            games: List of game names to run
            iterations: Number of iterations per game
            name: Optional custom name for the campaign
            quality: Optional quality preset ('low', 'medium', 'high', 'ultra')
            resolution: Optional resolution preset ('720p', '1080p', '1440p', '2160p')

        Returns:
            Created Campaign object
        """
        campaign_id = str(uuid.uuid4())

        # Auto-generate name if not provided
        if not name:
            # Use first 3 game abbreviations
            game_abbrevs = []
            for game in games[:3]:
                # Take first letter of each word, max 3 chars
                words = game.replace(":", "").split()
                abbrev = "".join(w[0].upper() for w in words[:3])
                game_abbrevs.append(abbrev)
            if len(games) > 3:
                game_abbrevs.append(f"+{len(games) - 3}")
            name = "-".join(game_abbrevs)

        logger.info(f"Creating campaign '{name}' with {len(games)} games on {sut_ip}")

        campaign = Campaign(
            campaign_id=campaign_id,
            name=name,
            sut_ip=sut_ip,
            sut_device_id=sut_device_id,
            games=games,
            iterations_per_game=iterations,
            status=CampaignStatus.QUEUED,
            progress=CampaignProgress(total_games=len(games)),
            quality=quality,
            resolution=resolution
        )

        # Queue individual runs for each game
        run_ids = []
        for game in games:
            try:
                run_id = self.run_manager.queue_run(
                    game_name=game,
                    sut_ip=sut_ip,
                    sut_device_id=sut_device_id,
                    iterations=iterations,
                    campaign_id=campaign_id,
                    quality=quality,
                    resolution=resolution,
                    skip_steam_login=skip_steam_login
                )
                run_ids.append(run_id)
                logger.info(f"Queued run {run_id} for game '{game}' in campaign {campaign_id[:8]} (preset: {quality}@{resolution})")
            except Exception as e:
                logger.error(f"Failed to queue run for game '{game}': {e}")
                campaign.error_message = f"Failed to queue game '{game}': {e}"

        campaign.run_ids = run_ids

        # Store campaign and run-to-campaign mapping
        with self._lock:
            self.campaigns[campaign_id] = campaign
            for run_id in run_ids:
                self._run_to_campaign[run_id] = campaign_id

        logger.info(f"Campaign {campaign_id[:8]} created with {len(run_ids)} runs queued")

        # Emit campaign created event
        event_bus.emit(EventType.CAMPAIGN_CREATED, {
            'campaign_id': campaign_id,
            'campaign': campaign.to_dict()
        })

        return campaign

    def get_campaign(self, campaign_id: str, force_update: bool = False) -> Optional[Campaign]:
        """Get a campaign by ID.

        Args:
            campaign_id: The campaign ID
            force_update: If True, recalculate progress from run states.
                          If False, use cached progress (updated by events).
        """
        with self._lock:
            campaign = self.campaigns.get(campaign_id)
            if campaign and force_update:
                # Force update from run states (for initial load or manual refresh)
                self._update_campaign_progress(campaign)
            return campaign

    def get_all_campaigns(self, force_update: bool = False) -> List[Campaign]:
        """Get all active campaigns.

        Args:
            force_update: If True, recalculate all progress from run states.
                          If False (default), use cached progress (updated by events).
                          The event-driven approach keeps progress up-to-date automatically.
        """
        with self._lock:
            campaigns = list(self.campaigns.values())
            if force_update:
                for campaign in campaigns:
                    self._update_campaign_progress(campaign)
            return campaigns

    def get_campaign_history(self) -> List[Campaign]:
        """Get completed/failed campaigns"""
        return self.campaign_history.copy()

    def _update_campaign_progress(self, campaign: Campaign):
        """Update campaign progress based on individual run statuses"""
        if not campaign.run_ids:
            return

        completed = 0
        failed = 0
        current_game = None
        current_index = 0

        for i, run_id in enumerate(campaign.run_ids):
            run = self.run_manager.get_run(run_id)
            if not run:
                continue

            if run.status.value == "completed":
                completed += 1
            elif run.status.value == "failed":
                failed += 1
            elif run.status.value == "running":
                current_game = run.game_name
                current_index = i + 1
            elif run.status.value == "queued" and current_game is None:
                # First queued game is next
                current_game = run.game_name
                current_index = i + 1

        # Track if progress changed for event emission
        old_completed = campaign.progress.completed_games
        old_failed = campaign.progress.failed_games
        old_status = campaign.status

        campaign.progress.completed_games = completed
        campaign.progress.failed_games = failed
        campaign.progress.current_game = current_game
        campaign.progress.current_game_index = current_index

        # Update campaign status
        total = len(campaign.run_ids)
        if completed + failed == total:
            campaign.completed_at = datetime.now()
            if failed == 0:
                campaign.status = CampaignStatus.COMPLETED
            elif completed == 0:
                campaign.status = CampaignStatus.FAILED
            else:
                campaign.status = CampaignStatus.PARTIALLY_COMPLETED

            # Move to history and clean up run mappings
            with self._lock:
                if campaign.campaign_id in self.campaigns:
                    del self.campaigns[campaign.campaign_id]
                    self.campaign_history.append(campaign)
                    # Clean up run-to-campaign mappings
                    for run_id in campaign.run_ids:
                        self._run_to_campaign.pop(run_id, None)

            # Emit completion event
            event_type = EventType.CAMPAIGN_COMPLETED if failed == 0 else EventType.CAMPAIGN_FAILED
            event_bus.emit(event_type, {
                'campaign_id': campaign.campaign_id,
                'campaign': campaign.to_dict()
            })
        elif completed > 0 or current_game:
            campaign.status = CampaignStatus.RUNNING

        # Emit progress event if progress changed
        progress_changed = (completed != old_completed or failed != old_failed or campaign.status != old_status)
        if progress_changed and campaign.status == CampaignStatus.RUNNING:
            event_bus.emit(EventType.CAMPAIGN_PROGRESS, {
                'campaign_id': campaign.campaign_id,
                'campaign': campaign.to_dict()
            })

    def stop_campaign(self, campaign_id: str) -> bool:
        """
        Stop all runs in a campaign.

        Args:
            campaign_id: ID of the campaign to stop

        Returns:
            True if campaign was found and stop initiated
        """
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            logger.warning(f"Campaign {campaign_id} not found")
            return False

        logger.info(f"Stopping campaign {campaign_id[:8]} with {len(campaign.run_ids)} runs")

        stopped_count = 0
        for run_id in campaign.run_ids:
            try:
                if self.run_manager.stop_run(run_id):
                    stopped_count += 1
            except Exception as e:
                logger.warning(f"Failed to stop run {run_id}: {e}")

        campaign.status = CampaignStatus.STOPPED
        campaign.completed_at = datetime.now()

        logger.info(f"Stopped {stopped_count}/{len(campaign.run_ids)} runs in campaign {campaign_id[:8]}")
        return True

    def get_runs_for_campaign(self, campaign_id: str) -> List[Any]:
        """Get all runs belonging to a campaign"""
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return []

        runs = []
        for run_id in campaign.run_ids:
            run = self.run_manager.get_run(run_id)
            if run:
                runs.append(run)
        return runs


# Global campaign manager instance
_campaign_manager: Optional[CampaignManager] = None


def get_campaign_manager() -> CampaignManager:
    """Get the global campaign manager instance"""
    global _campaign_manager
    if _campaign_manager is None:
        raise RuntimeError("CampaignManager not initialized. Call init_campaign_manager first.")
    return _campaign_manager


def init_campaign_manager(run_manager) -> CampaignManager:
    """Initialize the global campaign manager"""
    global _campaign_manager
    _campaign_manager = CampaignManager(run_manager)
    return _campaign_manager
