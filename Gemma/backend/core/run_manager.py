# -*- coding: utf-8 -*-
"""
Run Manager for tracking and coordinating automation runs across multiple SUTs
"""

import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import queue
import copy

from .run_storage import RunStorageManager, SUTInfo, RunConfig, RunManifest
from .log_collector import LogCollector

logger = logging.getLogger(__name__)


class RunStatus(Enum):
    """Status of an automation run"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class StepStatus(Enum):
    """Status of an automation step"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepProgress:
    """Progress tracking for an individual step"""
    step_number: int
    description: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    screenshot_url: Optional[str] = None
    error_message: Optional[str] = None
    is_optional: bool = False

    def to_dict(self) -> Dict[str, Any]:
        # Handle started_at - could be datetime or string
        started = None
        if self.started_at:
            started = self.started_at.isoformat() if isinstance(self.started_at, datetime) else self.started_at

        # Handle completed_at - could be datetime or string
        completed = None
        if self.completed_at:
            completed = self.completed_at.isoformat() if isinstance(self.completed_at, datetime) else self.completed_at

        return {
            'step_number': self.step_number,
            'description': self.description,
            'status': self.status.value,
            'started_at': started,
            'completed_at': completed,
            'screenshot_url': self.screenshot_url,
            'error_message': self.error_message,
            'is_optional': self.is_optional,
        }


@dataclass
class RunProgress:
    """Progress tracking for a run"""
    current_iteration: int = 0
    total_iterations: int = 1
    current_step: int = 0
    total_steps: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    steps: List['StepProgress'] = field(default_factory=list)


@dataclass
class RunResult:
    """Results from a completed run"""
    success_rate: float = 0.0
    successful_runs: int = 0
    total_iterations: int = 0
    run_directory: Optional[str] = None
    error_logs: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AutomationRun:
    """Represents a single automation run"""
    run_id: str
    game_name: str
    sut_ip: str
    sut_device_id: str
    status: RunStatus = RunStatus.QUEUED
    iterations: int = 1
    progress: RunProgress = field(default_factory=RunProgress)
    results: Optional[RunResult] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    sut_info: Optional[Dict[str, Any]] = None  # SUT hardware metadata from manifest
    folder_name: Optional[str] = None  # Run folder name for logs/artifacts
    campaign_id: Optional[str] = None  # Links to parent campaign (if part of multi-game campaign)
    campaign_name: Optional[str] = None  # Campaign name for display
    quality: Optional[str] = None  # 'low' | 'medium' | 'high' | 'ultra'
    resolution: Optional[str] = None  # '720p' | '1080p' | '1440p' | '2160p'
    # Runtime references (not serialized)
    stop_event: Optional[Any] = field(default=None, repr=False)  # threading.Event for cancellation
    timeline: Optional[Any] = field(default=None, repr=False)  # TimelineManager reference

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        # Handle start_time - could be datetime or string
        started = None
        if self.progress.start_time:
            started = self.progress.start_time.isoformat() if isinstance(self.progress.start_time, datetime) else self.progress.start_time

        # Handle end_time - could be datetime or string
        completed = None
        if self.progress.end_time:
            completed = self.progress.end_time.isoformat() if isinstance(self.progress.end_time, datetime) else self.progress.end_time

        # Handle created_at - could be datetime or string
        created = self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at

        return {
            'run_id': self.run_id,
            'game_name': self.game_name,
            'sut_ip': self.sut_ip,
            'sut_device_id': self.sut_device_id,
            'status': self.status.value,
            'iterations': self.iterations,
            'progress': {
                'current_iteration': self.progress.current_iteration,
                'total_iterations': self.progress.total_iterations,
                'current_step': self.progress.current_step,
                'total_steps': self.progress.total_steps,
                'steps': [step.to_dict() for step in self.progress.steps],
            },
            'started_at': started,
            'completed_at': completed,
            'results': self.results.__dict__ if self.results else None,
            'error_message': self.error_message,
            'created_at': created,
            'sut_info': self.sut_info,
            'folder_name': self.folder_name,
            'campaign_id': self.campaign_id,
            'campaign_name': self.campaign_name,
            'quality': self.quality,
            'resolution': self.resolution,
        }


class RunManager:
    """Manages automation runs across multiple SUTs with parallel execution support"""

    def __init__(self, max_concurrent_runs: int = 10, orchestrator=None, sut_client=None):
        self.max_concurrent_runs = max_concurrent_runs
        self.orchestrator = orchestrator
        self.sut_client = sut_client  # For fetching SUT system_info
        self.active_runs: Dict[str, AutomationRun] = {}
        self.run_history: List[AutomationRun] = []
        self.run_queue = queue.Queue()
        self.worker_threads: List[threading.Thread] = []
        self.running = False
        self._lock = threading.Lock()

        # Per-SUT tracking for parallel execution
        self._sut_current_run: Dict[str, str] = {}  # sut_ip -> run_id currently executing

        # Account scheduler for Steam account coordination
        from .account_scheduler import get_account_scheduler
        self.account_scheduler = get_account_scheduler()

        # Persistent storage manager
        self.storage = RunStorageManager()

        # Log collector for pulling service logs at run completion
        self.log_collector = LogCollector(self.storage, sut_client)

        # Map run_id to storage manifest
        self._storage_map: Dict[str, RunManifest] = {}

        # Event callbacks
        self.on_run_started = None
        self.on_run_progress = None
        self.on_run_completed = None
        self.on_run_failed = None
        # Step-level callbacks (for real-time timeline updates)
        self.on_step_started = None
        self.on_step_completed = None
        self.on_step_failed = None

        # Load history from disk
        self._load_history_from_storage()

        logger.info(f"RunManager initialized with max_concurrent_runs={max_concurrent_runs} (persistent storage mode)")

    def _load_history_from_storage(self):
        """Load run history from persistent storage"""
        try:
            manifests = self.storage.load_run_history()
            stale_count = 0
            for manifest in manifests:
                # Fix stale "running" runs - they were interrupted by Gemma restart
                if manifest.status == 'running':
                    stale_count += 1
                    manifest.status = 'failed'
                    manifest.error = 'Run interrupted - Gemma was restarted'
                    manifest.completed_at = datetime.now().isoformat()
                    # Update the manifest on disk
                    try:
                        self.storage.update_manifest(manifest)
                        logger.info(f"Marked stale run {manifest.run_id} as failed (Gemma restart)")
                    except Exception as update_err:
                        logger.warning(f"Failed to update stale run manifest: {update_err}")

                # Convert manifest to AutomationRun for compatibility
                run = self._manifest_to_run(manifest)
                if run:
                    self.run_history.append(run)
                    self._storage_map[run.run_id] = manifest

            if stale_count > 0:
                logger.info(f"Fixed {stale_count} stale 'running' runs from previous session")
            logger.info(f"Loaded {len(manifests)} runs from persistent storage")
        except Exception as e:
            logger.error(f"Error loading run history from storage: {e}")

    def _manifest_to_run(self, manifest: RunManifest) -> Optional[AutomationRun]:
        """Convert a storage manifest to an AutomationRun"""
        try:
            status_map = {
                'running': RunStatus.RUNNING,
                'completed': RunStatus.COMPLETED,
                'failed': RunStatus.FAILED,
                'stopped': RunStatus.STOPPED,
            }

            # Convert SUTInfo to dict format expected by frontend
            sut_info = None
            if manifest.sut:
                sut_info = {
                    'cpu': {'brand_string': manifest.sut.cpu_brand or ''},
                    'gpu': {'name': manifest.sut.gpu_name or ''},
                    'ram': {'total_gb': manifest.sut.ram_gb or 0},
                    'os': {
                        'name': manifest.sut.os_name or '',
                        'version': manifest.sut.os_version or '',
                        'release': '',
                        'build': manifest.sut.os_build or ''
                    },
                    'bios': {
                        'name': manifest.sut.bios_name or '',
                        'version': manifest.sut.bios_version or ''
                    },
                    'screen': {
                        'width': manifest.sut.resolution_width or 0,
                        'height': manifest.sut.resolution_height or 0
                    },
                    'hostname': manifest.sut.hostname or '',
                    'device_id': manifest.sut.device_id or '',
                }

            # Parse created_at datetime
            created_at_dt = datetime.now()
            if manifest.created_at:
                try:
                    created_at_dt = datetime.fromisoformat(manifest.created_at) if isinstance(manifest.created_at, str) else manifest.created_at
                except Exception:
                    pass

            # Parse preset_level (e.g., "high-1080p") into quality and resolution
            quality = None
            resolution = None
            if manifest.config and manifest.config.preset_level:
                preset_parts = manifest.config.preset_level.split('-')
                if len(preset_parts) >= 2:
                    quality = preset_parts[0]  # e.g., "high"
                    resolution = preset_parts[1]  # e.g., "1080p"
                elif len(preset_parts) == 1:
                    # Just quality or resolution
                    if preset_parts[0] in ['720p', '1080p', '1440p', '2160p']:
                        resolution = preset_parts[0]
                    else:
                        quality = preset_parts[0]

            run = AutomationRun(
                run_id=manifest.run_id,
                game_name=manifest.config.games[0] if manifest.config and manifest.config.games else "Unknown",
                sut_ip=manifest.sut.ip if manifest.sut else "",
                sut_device_id=manifest.sut.device_id if manifest.sut else "",
                status=status_map.get(manifest.status, RunStatus.COMPLETED),
                iterations=manifest.config.iterations if manifest.config else 1,
                sut_info=sut_info,
                folder_name=manifest.folder_name,
                created_at=created_at_dt,
                campaign_id=manifest.campaign_id,  # Preserve campaign link for filtering
                campaign_name=manifest.campaign_name,  # Preserve campaign name for display
                quality=quality,
                resolution=resolution,
            )

            # Set progress times
            if manifest.created_at:
                try:
                    run.progress.start_time = datetime.fromisoformat(manifest.created_at) if isinstance(manifest.created_at, str) else manifest.created_at
                except Exception:
                    pass
            if manifest.completed_at:
                try:
                    run.progress.end_time = datetime.fromisoformat(manifest.completed_at) if isinstance(manifest.completed_at, str) else manifest.completed_at
                except Exception:
                    pass

            # Set results
            if manifest.summary:
                run.results = RunResult(
                    success_rate=manifest.summary.get('completed_iterations', 0) / max(manifest.summary.get('total_iterations', 1), 1),
                    successful_runs=manifest.summary.get('completed_iterations', 0),
                    total_iterations=manifest.summary.get('total_iterations', 0),
                    run_directory=str(self.storage.base_dir / manifest.folder_name),
                )

            return run
        except Exception as e:
            logger.error(f"Error converting manifest to run: {e}")
            return None

    def set_sut_client(self, sut_client):
        """Set the SUT client for fetching system info"""
        self.sut_client = sut_client
    
    def set_orchestrator(self, orchestrator):
        """Set the automation orchestrator"""
        self.orchestrator = orchestrator
    
    
    def start(self):
        """Start the run manager worker threads"""
        if self.running:
            return

        self.running = True

        # Start multiple worker threads for parallel execution across SUTs
        # Each worker can process runs on different SUTs simultaneously
        # Account scheduler ensures no Steam account conflicts
        num_workers = min(self.max_concurrent_runs, 4)  # Up to 4 parallel workers
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"RunWorker-{i}",
                daemon=True
            )
            worker.start()
            self.worker_threads.append(worker)

        logger.info(f"RunManager started with {len(self.worker_threads)} worker threads (parallel execution enabled)")
    
    def stop(self):
        """Stop the run manager and all running automation"""
        if not self.running:
            return
            
        logger.info("Stopping RunManager...")
        self.running = False
        
        # Stop all active runs
        with self._lock:
            for run in self.active_runs.values():
                if run.status == RunStatus.RUNNING:
                    run.status = RunStatus.STOPPED
                    run.error_message = "Stopped by system shutdown"
                    run.progress.end_time = datetime.now()
        
        # Wait for worker threads to finish with timeout
        for thread in self.worker_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)  # 2 second timeout per thread
                if thread.is_alive():
                    logger.warning(f"Worker thread {thread.name} did not shut down gracefully")
        
        # Clear the queue to help threads exit
        try:
            while not self.run_queue.empty():
                self.run_queue.get_nowait()
        except:
            pass
        
        logger.info("RunManager stopped")
    
    def queue_run(self, game_name: str, sut_ip: str, sut_device_id: str, iterations: int = 1,
                  campaign_id: Optional[str] = None, quality: Optional[str] = None,
                  resolution: Optional[str] = None) -> str:
        """Queue a new automation run

        Args:
            game_name: Name of the game to run
            sut_ip: IP address of the SUT
            sut_device_id: Unique device ID of the SUT
            iterations: Number of iterations to run
            campaign_id: Optional campaign ID if this run is part of a multi-game campaign
            quality: Optional quality preset ('low', 'medium', 'high', 'ultra')
            resolution: Optional resolution preset ('720p', '1080p', '1440p', '2160p')
        """
        campaign_info = f" (campaign: {campaign_id[:8]}...)" if campaign_id else ""
        preset_info = f" (preset: {quality}@{resolution})" if quality and resolution else ""
        logger.info(f"Attempting to queue run: {game_name} on {sut_ip} ({iterations} iterations){campaign_info}{preset_info}")

        # Check if run manager is running
        if not self.running:
            logger.error("Cannot queue run: Run manager is not running")
            raise RuntimeError("Run manager is not running")

        try:
            run_id = str(uuid.uuid4())
            logger.info(f"Generated run_id: {run_id}")

            run = AutomationRun(
                run_id=run_id,
                game_name=game_name,
                sut_ip=sut_ip,
                sut_device_id=sut_device_id,
                iterations=iterations,
                campaign_id=campaign_id,
                quality=quality,
                resolution=resolution
            )
            run.progress.total_iterations = iterations
            logger.info(f"Created AutomationRun object for {run_id}")
            
            with self._lock:
                self.active_runs[run_id] = run
                logger.info(f"Added run {run_id} to active runs. Current active runs: {len(self.active_runs)}")
            
            logger.info(f"Adding run {run_id} to queue")
            self.run_queue.put(run_id)
            
            queue_size = self.run_queue.qsize()
            worker_count = len([t for t in self.worker_threads if t.is_alive()])
            logger.info(f"Queued run {run_id}: {game_name} on {sut_ip} ({iterations} iterations)")
            logger.info(f"Queue size: {queue_size}, Active workers: {worker_count}")
            
            return run_id
            
        except Exception as e:
            logger.error(f"Error queuing run: {e}", exc_info=True)
            raise
    
    def stop_run(self, run_id: str) -> bool:
        """Stop a specific run - interrupts running or cancels queued runs"""
        with self._lock:
            if run_id in self.active_runs:
                run = self.active_runs[run_id]
                if run.status == RunStatus.RUNNING:
                    # Set status first
                    run.status = RunStatus.STOPPED
                    run.error_message = "Stopped by user"
                    run.progress.end_time = datetime.now()

                    # CRITICAL: Set the stop_event to interrupt SimpleAutomation
                    # This causes the automation loop to exit at the next checkpoint
                    if run.stop_event:
                        run.stop_event.set()
                        logger.info(f"Set stop_event for run {run_id}")

                    # Release the Steam account lock so other runs can use it
                    self.account_scheduler.release(run.sut_ip, run.game_name)
                    logger.info(f"Released account for stopped run {run_id}")

                    # Release the SUT lock so other runs can use this SUT
                    if self._sut_current_run.get(run.sut_ip) == run_id:
                        del self._sut_current_run[run.sut_ip]
                        logger.info(f"Released SUT {run.sut_ip} lock for stopped run")

                    # Emit timeline event so frontend shows "User cancelled"
                    if run.timeline:
                        try:
                            run.timeline.run_cancelled("User cancelled")
                            logger.info(f"Emitted run_cancelled timeline event for {run_id}")
                        except Exception as e:
                            logger.warning(f"Failed to emit timeline event: {e}")

                    logger.info(f"Stopped run {run_id}")
                    return True
                elif run.status == RunStatus.QUEUED:
                    # Cancel queued run - remove from active and move to history
                    run.status = RunStatus.STOPPED
                    run.error_message = "Cancelled before starting"
                    run.progress.end_time = datetime.now()

                    # Release account lock if somehow acquired while queued
                    self.account_scheduler.release(run.sut_ip, run.game_name)

                    # Move to history
                    self.run_history.insert(0, run)
                    del self.active_runs[run_id]

                    logger.info(f"Cancelled queued run {run_id}")
                    return True
        return False
    
    def get_run(self, run_id: str) -> Optional[AutomationRun]:
        """Get a specific run object by ID"""
        with self._lock:
            if run_id in self.active_runs:
                return self.active_runs[run_id]

            # Check history
            for run in self.run_history:
                if run.run_id == run_id:
                    return run
        return None

    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific run"""
        with self._lock:
            if run_id in self.active_runs:
                return self.active_runs[run_id].to_dict()

            # Check history
            for run in self.run_history:
                if run.run_id == run_id:
                    return run.to_dict()
        return None
    
    def get_all_runs(self) -> Dict[str, Any]:
        """Get all runs (active and history)"""
        with self._lock:
            # Get active runs from memory
            active_dict = {run_id: run.to_dict() for run_id, run in self.active_runs.items()}

            # Get history from memory (sorted newest first, take first 50)
            history_list = [run.to_dict() for run in self.run_history[:50]]

            return {
                'active': active_dict,
                'history': history_list
            }
    
    def update_run_progress(self, run_id: str, current_iteration: int = None, current_step: int = None):
        """Update progress for a running automation"""
        with self._lock:
            if run_id not in self.active_runs:
                return

            run = self.active_runs[run_id]

            if current_iteration is not None:
                run.progress.current_iteration = current_iteration
            if current_step is not None:
                run.progress.current_step = current_step

            # Trigger progress callback
            if self.on_run_progress:
                try:
                    self.on_run_progress(run_id, run.to_dict())
                except Exception as e:
                    logger.error(f"Error in run progress callback: {e}")

    def initialize_steps(self, run_id: str, steps: List[Dict[str, Any]]):
        """Initialize step list for a run from game config"""
        with self._lock:
            if run_id not in self.active_runs:
                return

            run = self.active_runs[run_id]
            run.progress.total_steps = len(steps)
            run.progress.steps = []

            for step_data in steps:
                step = StepProgress(
                    step_number=step_data.get('step_number', 0),
                    description=step_data.get('description', 'Unknown step'),
                    is_optional=step_data.get('optional', False) or '[OPTIONAL]' in step_data.get('description', '').upper(),
                )
                run.progress.steps.append(step)

            logger.info(f"Initialized {len(steps)} steps for run {run_id}")

    def start_step(self, run_id: str, step_number: int, description: str = None, screenshot_url: str = None):
        """Mark a step as started"""
        with self._lock:
            if run_id not in self.active_runs:
                return

            run = self.active_runs[run_id]
            run.progress.current_step = step_number

            # Find or create the step
            step = None
            for s in run.progress.steps:
                if s.step_number == step_number:
                    step = s
                    break

            if not step:
                # Create new step if not initialized
                step = StepProgress(
                    step_number=step_number,
                    description=description or f"Step {step_number}",
                )
                run.progress.steps.append(step)

            step.status = StepStatus.IN_PROGRESS
            step.started_at = datetime.now()
            if description:
                step.description = description
            if screenshot_url:
                step.screenshot_url = screenshot_url

            step_dict = step.to_dict()

        # Trigger callback outside lock
        if self.on_step_started:
            try:
                self.on_step_started(run_id, step_dict)
            except Exception as e:
                logger.error(f"Error in step started callback: {e}")

    def complete_step(self, run_id: str, step_number: int, success: bool = True,
                      screenshot_url: str = None, error_message: str = None):
        """Mark a step as completed or failed"""
        with self._lock:
            if run_id not in self.active_runs:
                return

            run = self.active_runs[run_id]

            # Find the step
            step = None
            for s in run.progress.steps:
                if s.step_number == step_number:
                    step = s
                    break

            if not step:
                logger.warning(f"Step {step_number} not found for run {run_id}")
                return

            step.status = StepStatus.COMPLETED if success else StepStatus.FAILED
            step.completed_at = datetime.now()
            if screenshot_url:
                step.screenshot_url = screenshot_url
            if error_message:
                step.error_message = error_message

            step_dict = step.to_dict()

        # Trigger callback outside lock
        callback = self.on_step_completed if success else self.on_step_failed
        if callback:
            try:
                callback(run_id, step_dict)
            except Exception as e:
                logger.error(f"Error in step completion callback: {e}")

    def skip_step(self, run_id: str, step_number: int, reason: str = None):
        """Mark a step as skipped (for optional steps)"""
        with self._lock:
            if run_id not in self.active_runs:
                return

            run = self.active_runs[run_id]

            # Find the step
            step = None
            for s in run.progress.steps:
                if s.step_number == step_number:
                    step = s
                    break

            if step:
                step.status = StepStatus.SKIPPED
                step.completed_at = datetime.now()
                if reason:
                    step.error_message = reason
    
    def complete_run(self, run_id: str, success: bool, results: Optional[RunResult] = None, error_message: str = None):
        """Mark a run as completed"""
        logger.info(f"complete_run called for {run_id}, acquiring lock...")
        with self._lock:
            logger.info(f"complete_run acquired lock for {run_id}")
            if run_id not in self.active_runs:
                logger.warning(f"Run {run_id} not found in active_runs, returning early")
                return
                
            logger.info(f"Updating run status for {run_id}")
            run = self.active_runs[run_id]
            run.status = RunStatus.COMPLETED if success else RunStatus.FAILED
            run.progress.end_time = datetime.now()
            run.results = results
            if error_message:
                run.error_message = error_message
            
            logger.info(f"Moving run {run_id} to history")
            # Move to history - clear non-serializable fields before deepcopy
            # threading.Event and TimelineManager cannot be pickled
            run.stop_event = None
            run.timeline = None
            # Insert at beginning to maintain newest-first order (history loaded from disk is already sorted)
            self.run_history.insert(0, copy.deepcopy(run))
            del self.active_runs[run_id]
            logger.info(f"Removed run {run_id} from active_runs")
            
            # Keep history manageable
            if len(self.run_history) > 100:
                self.run_history = self.run_history[-100:]
            
            logger.info(f"Completed run {run_id}: {run.game_name} ({'success' if success else 'failed'})")
            
            # Log queue state for debugging
            queue_size = self.run_queue.qsize()
            active_runs_count = len(self.active_runs)
            logger.info(f"After completion - Queue size: {queue_size}, Active runs: {active_runs_count}")
            if active_runs_count > 0:
                pending_games = [(run.game_name, run.sut_ip) for run in self.active_runs.values()]
                logger.info(f"Pending games: {pending_games}")
            
            if queue_size > 0:
                logger.info(f"Worker should pick up next run from queue (size: {queue_size})")
        
        # Trigger completion callback OUTSIDE the lock to avoid deadlock
        logger.info(f"About to trigger completion callback for {run_id}")
        callback = self.on_run_completed if success else self.on_run_failed
        if callback:
            try:
                logger.info(f"Calling completion callback for {run_id}")
                callback(run_id, run.to_dict())
                logger.info(f"Completion callback finished for {run_id}")
            except Exception as e:
                logger.error(f"Error in run completion callback: {e}")
        else:
            logger.info(f"No completion callback set for {run_id}")
    
    def _worker_loop(self):
        """Worker thread main loop with parallel SUT execution support"""
        worker_name = threading.current_thread().name
        logger.info(f"Worker thread {worker_name} started")

        requeued_runs = set()  # Track runs we've requeued to avoid infinite loops

        while self.running:
            try:
                # Wait for a run to process
                try:
                    run_id = self.run_queue.get(timeout=0.5)
                except queue.Empty:
                    requeued_runs.clear()  # Clear requeue tracking on empty queue
                    continue

                # Double-check we're still running
                if not self.running:
                    logger.info(f"Worker thread {worker_name} stopping")
                    break

                # ATOMIC CHECK: Both SUT-busy and account checks must be atomic
                # to prevent race conditions where two workers grab the same SUT
                with self._lock:
                    if run_id not in self.active_runs:
                        continue
                    run = self.active_runs[run_id]

                    # Check 1: Is another run already executing on this SUT?
                    current_run_on_sut = self._sut_current_run.get(run.sut_ip)
                    if current_run_on_sut and current_run_on_sut != run_id:
                        # SUT is busy, requeue this run (always requeue to avoid losing runs)
                        if run_id not in requeued_runs:
                            logger.debug(f"SUT {run.sut_ip} busy with run {current_run_on_sut[:8]}, "
                                       f"requeueing {run_id[:8]} ({run.game_name})")
                            requeued_runs.add(run_id)
                        self.run_queue.put(run_id)  # Always put back in queue
                        continue

                    # Check 2: Can we acquire the Steam account for this game?
                    if not self.account_scheduler.try_acquire(run.sut_ip, run.game_name):
                        # Account is held by another SUT, requeue this run (always requeue)
                        if run_id not in requeued_runs:
                            holder = self.account_scheduler.get_holder(run.game_name)
                            account_type = self.account_scheduler.get_account_type(run.game_name).value.upper()
                            logger.info(f"SUT {run.sut_ip} waiting for {account_type} account "
                                      f"(held by {holder}), requeueing '{run.game_name}'")
                            requeued_runs.add(run_id)
                        self.run_queue.put(run_id)  # Always put back in queue
                        continue

                    # BOTH checks passed - atomically mark SUT as busy BEFORE releasing lock
                    self._sut_current_run[run.sut_ip] = run_id
                    requeued_runs.discard(run_id)

                # Now outside lock - log and execute
                account_type = self.account_scheduler.get_account_type(run.game_name).value.upper()
                logger.info(f"Worker {worker_name} executing {run.game_name} on {run.sut_ip} "
                          f"(account: {account_type})")

                try:
                    # Process the run
                    self._execute_run(run)
                    logger.info(f"Worker {worker_name} completed run {run_id[:8]}")
                finally:
                    # Always release account and SUT lock when done
                    self.account_scheduler.release(run.sut_ip, run.game_name)
                    with self._lock:
                        if self._sut_current_run.get(run.sut_ip) == run_id:
                            del self._sut_current_run[run.sut_ip]

            except Exception as e:
                logger.error(f"Error in worker thread {worker_name}: {e}", exc_info=True)

                # Cleanup on error
                try:
                    if 'run' in locals() and run:
                        self.account_scheduler.release(run.sut_ip, run.game_name)
                        with self._lock:
                            if self._sut_current_run.get(run.sut_ip) == run.run_id:
                                del self._sut_current_run[run.sut_ip]
                        self.complete_run(run.run_id, False, error_message=f"Worker thread error: {str(e)}")
                except Exception as cleanup_error:
                    logger.error(f"Error during worker thread cleanup: {cleanup_error}")

        logger.info(f"Worker thread {worker_name} ended")
    
    def _execute_run(self, run: AutomationRun):
        """Execute a single automation run"""
        logger.info(f"Starting execution of run {run.run_id}: {run.game_name} on {run.sut_ip}")

        # Mark as running
        with self._lock:
            run.status = RunStatus.RUNNING
            run.progress.start_time = datetime.now()

        # Create persistent storage structure
        storage_manifest = self._create_run_storage(run)

        # Trigger started callback
        if self.on_run_started:
            try:
                self.on_run_started(run.run_id, run.to_dict())
            except Exception as e:
                logger.error(f"Error in run started callback: {e}")

        try:
            # Execute the automation using orchestrator
            logger.info(f"Starting automation execution for run {run.run_id}")
            success = self._simulate_automation_execution(run)
            logger.info(f"Automation execution completed for run {run.run_id} with success={success}")

            # Complete storage
            if storage_manifest:
                self.storage.complete_run(run.run_id, success)

            # Create results (results may be set by orchestrator)
            run_directory = str(self.storage.get_run_dir(run.run_id)) if storage_manifest else f"logs/{run.game_name}/run_{run.run_id}"

            if not hasattr(run, '_execution_results'):
                results = RunResult(
                    success_rate=1.0 if success else 0.0,
                    successful_runs=run.iterations if success else 0,
                    total_iterations=run.iterations,
                    run_directory=run_directory,
                )
            else:
                results = run._execution_results
                results.run_directory = run_directory

            # Determine final error message
            error_message = None
            if not success and hasattr(run, '_execution_error'):
                error_message = run._execution_error

            logger.info(f"About to complete run {run.run_id} with success={success}")
            self.complete_run(run.run_id, success, results, error_message)
            logger.info(f"Completed run call finished for {run.run_id}")

            # Collect service logs for correlation
            self._collect_run_logs(run)

        except Exception as e:
            logger.error(f"Critical error executing run {run.run_id}: {e}", exc_info=True)
            if storage_manifest:
                self.storage.add_error(run.run_id, str(e))
                self.storage.complete_run(run.run_id, False)
            self.complete_run(run.run_id, False, error_message=f"Critical error: {str(e)}")

            # Still try to collect logs even on critical failure
            try:
                self._collect_run_logs(run)
            except Exception as log_err:
                logger.warning(f"Failed to collect logs after critical error: {log_err}")

    def _collect_run_logs(self, run: AutomationRun):
        """
        Collect service logs at run completion for correlation.

        Pulls logs from:
        - SUT Client (via HTTP API)
        - Queue Service (local file)
        - Preset Manager (local file)
        - SUT Discovery (local file)
        """
        try:
            # Get run start time for filtering
            run_start = run.progress.start_time if run.progress else None

            logger.info(f"Collecting service logs for run {run.run_id}")
            results = self.log_collector.collect_all_logs(
                run_id=run.run_id,
                sut_ip=run.sut_ip,
                run_start_time=run_start
            )

            # Log summary
            collected = sum(1 for r in results.values() if r.get('success'))
            total_lines = sum(r.get('lines_collected', 0) for r in results.values())
            logger.info(f"Log collection complete: {collected}/{len(results)} services, {total_lines} total lines")

        except Exception as e:
            logger.warning(f"Log collection failed for run {run.run_id}: {e}")

    def _create_run_storage(self, run: AutomationRun) -> Optional[RunManifest]:
        """Create persistent storage for a run, fetching SUT info"""
        try:
            # Fetch SUT system info
            sut_info = self._fetch_sut_info(run.sut_ip)

            # Create run config
            run_type = "campaign" if run.campaign_id else "single"
            # Build preset_level from quality and resolution (e.g., "high-1080p")
            preset_level = ""
            if run.quality and run.resolution:
                preset_level = f"{run.quality}-{run.resolution}"
            elif run.quality:
                preset_level = run.quality
            elif run.resolution:
                preset_level = run.resolution

            config = RunConfig(
                run_type=run_type,
                games=[run.game_name],
                iterations=run.iterations,
                preset_level=preset_level,
            )

            # Get campaign name if part of campaign
            campaign_name = None
            if run.campaign_id and hasattr(self, 'campaign_manager') and self.campaign_manager:
                campaign = self.campaign_manager.get_campaign(run.campaign_id)
                if campaign:
                    campaign_name = campaign.name

            # Create storage structure
            manifest = self.storage.create_run(
                run_id=run.run_id,
                sut_info=sut_info,
                config=config,
                campaign_id=run.campaign_id,
                campaign_name=campaign_name,
            )

            self._storage_map[run.run_id] = manifest

            # Also update the run object with folder_name and campaign_name for API responses
            run.folder_name = manifest.folder_name
            run.campaign_name = campaign_name
            run.sut_info = {
                'cpu': {'brand_string': sut_info.cpu_brand or ''},
                'gpu': {'name': sut_info.gpu_name or ''},
                'ram': {'total_gb': sut_info.ram_gb or 0},
                'os': {
                    'name': sut_info.os_name or '',
                    'version': sut_info.os_version or '',
                    'release': '',
                    'build': sut_info.os_build or ''
                },
                'bios': {
                    'name': sut_info.bios_name or '',
                    'version': sut_info.bios_version or ''
                },
                'screen': {
                    'width': sut_info.resolution_width or 0,
                    'height': sut_info.resolution_height or 0
                },
                'hostname': sut_info.hostname or '',
                'device_id': sut_info.device_id or '',
            }

            logger.info(f"Created run storage: {manifest.folder_name}")

            return manifest

        except Exception as e:
            logger.error(f"Error creating run storage: {e}")
            return None

    def _fetch_sut_info(self, sut_ip: str) -> SUTInfo:
        """Fetch SUT system information"""
        if self.sut_client:
            try:
                result = self.sut_client.get_system_info(sut_ip, 8080)
                if result.success and result.data:
                    return SUTInfo.from_system_info(sut_ip, result.data)
            except Exception as e:
                logger.warning(f"Failed to fetch SUT info: {e}")

        # Return basic info if fetch fails
        return SUTInfo(ip=sut_ip)
    
    def _simulate_automation_execution(self, run: AutomationRun) -> bool:
        """Execute automation using the orchestrator or simulate if not available"""
        if self.orchestrator:
            logger.info(f"Executing real automation for run {run.run_id}")
            try:
                logger.info(f"Calling orchestrator.execute_run for {run.run_id}")
                success, results, error_message = self.orchestrator.execute_run(run)
                logger.info(f"Orchestrator.execute_run returned for {run.run_id}: success={success}")
                
                # Store results and error on the run object for later retrieval
                if results:
                    run._execution_results = results
                if error_message:
                    run._execution_error = error_message
                    logger.error(f"Automation execution failed: {error_message}")
                
                return success
            except Exception as e:
                logger.error(f"Error in orchestrator execution: {e}", exc_info=True)
                return False
        else:
            # Fallback to simulation
            logger.info(f"Simulating automation for run {run.run_id} (no orchestrator)")
            
            # Simulate multiple iterations
            for i in range(run.iterations):
                if run.status != RunStatus.RUNNING:
                    return False
                    
                # Update progress
                self.update_run_progress(run.run_id, current_iteration=i + 1)
                
                # Simulate work
                time.sleep(2)  # Simulate 2 seconds per iteration
                
                logger.info(f"Run {run.run_id}: Completed iteration {i + 1}/{run.iterations}")
            
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get run manager statistics"""
        with self._lock:
            active_count = len(self.active_runs)
            queued_count = self.run_queue.qsize()
            
            # Calculate history stats
            completed_count = len([r for r in self.run_history if r.status == RunStatus.COMPLETED])
            failed_count = len([r for r in self.run_history if r.status == RunStatus.FAILED])
            
            # Get detailed queue info for debugging
            active_games = [run.game_name for run in self.active_runs.values()]
            
            return {
                'active_runs': active_count,
                'queued_runs': queued_count,
                'total_history': len(self.run_history),
                'completed_runs': completed_count,
                'failed_runs': failed_count,
                'worker_threads': len(self.worker_threads),
                'running': self.running,
                'active_games': active_games  # For debugging
            }