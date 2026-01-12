# -*- coding: utf-8 -*-
"""
Timeline Manager - Tracks comprehensive run lifecycle events for visualization.

The timeline shows the entire automation flow:
- Run started
- SUT connection
- Resolution detection
- OmniParser connection
- Preset sync
- Game launch
- Each automation step
- Benchmark phase
- Game exit
- Run completion

Events are stored in timeline.json in the blackbox directory for persistence.
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class TimelineEventType(Enum):
    """Types of timeline events"""
    # Run lifecycle
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"

    # Iteration
    ITERATION_STARTED = "iteration_started"
    ITERATION_COMPLETED = "iteration_completed"

    # Connection & Setup
    SUT_CONNECTING = "sut_connecting"
    SUT_CONNECTED = "sut_connected"
    SUT_CONNECTION_FAILED = "sut_connection_failed"

    RESOLUTION_DETECTING = "resolution_detecting"
    RESOLUTION_DETECTED = "resolution_detected"

    OMNIPARSER_CONNECTING = "omniparser_connecting"
    OMNIPARSER_CONNECTED = "omniparser_connected"
    OMNIPARSER_FAILED = "omniparser_failed"

    # Preset
    PRESET_SYNCING = "preset_syncing"
    PRESET_SYNCED = "preset_synced"
    PRESET_SKIPPED = "preset_skipped"
    PRESET_FAILED = "preset_failed"

    # Game lifecycle
    GAME_LAUNCHING = "game_launching"
    GAME_LAUNCHED = "game_launched"
    GAME_LAUNCH_FAILED = "game_launch_failed"
    GAME_PROCESS_WAITING = "game_process_waiting"  # Waiting for process with countdown
    GAME_PROCESS_DETECTED = "game_process_detected"
    GAME_INITIALIZING = "game_initializing"
    GAME_READY = "game_ready"
    GAME_EXITING = "game_exiting"
    GAME_EXITED = "game_exited"

    # Steam dialog handling
    STEAM_DIALOG_CHECKING = "steam_dialog_checking"
    STEAM_DIALOG_DETECTED = "steam_dialog_detected"
    STEAM_DIALOG_DISMISSED = "steam_dialog_dismissed"
    STEAM_ACCOUNT_BUSY = "steam_account_busy"
    STEAM_ACCOUNT_SWITCHING = "steam_account_switching"
    STEAM_NO_ACCOUNTS = "steam_no_accounts"

    # Automation steps
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"
    STEP_RETRYING = "step_retrying"

    # Benchmark
    BENCHMARK_STARTING = "benchmark_starting"
    BENCHMARK_RUNNING = "benchmark_running"
    BENCHMARK_COMPLETED = "benchmark_completed"

    # Waiting periods
    WAITING = "waiting"
    WAIT_COMPLETED = "wait_completed"

    # Screenshots & OCR
    SCREENSHOT_CAPTURED = "screenshot_captured"
    OCR_PROCESSING = "ocr_processing"
    OCR_COMPLETED = "ocr_completed"

    # Generic
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class TimelineEventStatus(Enum):
    """Status of a timeline event"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TimelineEvent:
    """A single event in the run timeline"""
    event_id: str
    event_type: TimelineEventType
    message: str
    timestamp: datetime
    status: TimelineEventStatus = TimelineEventStatus.IN_PROGRESS

    # Optional fields
    duration_ms: Optional[int] = None  # Calculated when event completes
    metadata: Dict[str, Any] = field(default_factory=dict)

    # For events that replace others (e.g., "Connecting" -> "Connected")
    replaces_event_id: Optional[str] = None

    # For grouping (e.g., all step events in same group)
    group: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value,
            'duration_ms': self.duration_ms,
            'metadata': self.metadata,
            'replaces_event_id': self.replaces_event_id,
            'group': self.group,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimelineEvent':
        """Create from dictionary"""
        return cls(
            event_id=data['event_id'],
            event_type=TimelineEventType(data['event_type']),
            message=data['message'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            status=TimelineEventStatus(data['status']),
            duration_ms=data.get('duration_ms'),
            metadata=data.get('metadata', {}),
            replaces_event_id=data.get('replaces_event_id'),
            group=data.get('group'),
        )


class TimelineManager:
    """Manages timeline events for a single automation run.

    Usage:
        timeline = TimelineManager(run_id, run_dir)

        # Add events
        timeline.add_event("sut_connect", TimelineEventType.SUT_CONNECTING, "Connecting to SUT...")
        timeline.complete_event("sut_connect", "Connected to 192.168.1.100:8080")

        # Or use convenience methods
        timeline.sut_connecting("192.168.1.100")
        timeline.sut_connected("192.168.1.100", port=8080)
    """

    def __init__(self, run_id: str, run_dir: str, on_event: Callable[[TimelineEvent], None] = None):
        self.run_id = run_id
        self.run_dir = run_dir
        self.on_event = on_event  # Callback for WebSocket events

        self._events: Dict[str, TimelineEvent] = {}
        self._event_order: List[str] = []  # Maintain insertion order
        self._event_counter = 0

        # Timeline file path - save directly in run directory (not in blackbox subfolder)
        self.timeline_file = os.path.join(run_dir, 'timeline.json')

        # Ensure run directory exists
        os.makedirs(run_dir, exist_ok=True)

        logger.debug(f"TimelineManager initialized for run {run_id}")

    def _generate_event_id(self, prefix: str = "evt") -> str:
        """Generate unique event ID"""
        self._event_counter += 1
        return f"{prefix}_{self._event_counter}"

    def add_event(
        self,
        event_id: str,
        event_type: TimelineEventType,
        message: str,
        status: TimelineEventStatus = TimelineEventStatus.IN_PROGRESS,
        metadata: Dict[str, Any] = None,
        replaces: str = None,
        group: str = None,
    ) -> TimelineEvent:
        """Add a new event to the timeline"""
        event = TimelineEvent(
            event_id=event_id,
            event_type=event_type,
            message=message,
            timestamp=datetime.now(),
            status=status,
            metadata=metadata or {},
            replaces_event_id=replaces,
            group=group,
        )

        self._events[event_id] = event
        if event_id not in self._event_order:
            self._event_order.append(event_id)

        # If this replaces another event, mark the old one
        if replaces and replaces in self._events:
            old_event = self._events[replaces]
            # Calculate duration from old event start to now
            duration = (event.timestamp - old_event.timestamp).total_seconds() * 1000
            event.duration_ms = int(duration)

        # Save and notify
        self._save()
        self._notify(event)

        logger.debug(f"Timeline [{self.run_id}]: {message}")
        return event

    def update_event(
        self,
        event_id: str,
        message: str = None,
        status: TimelineEventStatus = None,
        metadata: Dict[str, Any] = None,
    ) -> Optional[TimelineEvent]:
        """Update an existing event"""
        if event_id not in self._events:
            logger.warning(f"Event {event_id} not found")
            return None

        event = self._events[event_id]

        if message:
            event.message = message
        if status:
            event.status = status
            # Calculate duration when completing
            if status in (TimelineEventStatus.COMPLETED, TimelineEventStatus.FAILED):
                duration = (datetime.now() - event.timestamp).total_seconds() * 1000
                event.duration_ms = int(duration)
        if metadata:
            event.metadata.update(metadata)

        self._save()
        self._notify(event)
        return event

    def complete_event(self, event_id: str, message: str = None, metadata: Dict[str, Any] = None) -> Optional[TimelineEvent]:
        """Mark an event as completed"""
        return self.update_event(event_id, message=message, status=TimelineEventStatus.COMPLETED, metadata=metadata)

    def fail_event(self, event_id: str, message: str = None, error: str = None) -> Optional[TimelineEvent]:
        """Mark an event as failed"""
        meta = {'error': error} if error else None
        return self.update_event(event_id, message=message, status=TimelineEventStatus.FAILED, metadata=meta)

    def get_events(self) -> List[TimelineEvent]:
        """Get all events in order"""
        return [self._events[eid] for eid in self._event_order if eid in self._events]

    def get_events_dict(self) -> List[Dict[str, Any]]:
        """Get all events as dictionaries"""
        return [e.to_dict() for e in self.get_events()]

    def _save(self):
        """Save timeline to file"""
        try:
            data = {
                'run_id': self.run_id,
                'updated_at': datetime.now().isoformat(),
                'events': self.get_events_dict(),
            }
            with open(self.timeline_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save timeline: {e}")

    def _notify(self, event: TimelineEvent):
        """Notify listeners of event update"""
        if self.on_event:
            try:
                self.on_event(event)
            except Exception as e:
                logger.error(f"Error in timeline event callback: {e}")

    @classmethod
    def load(cls, run_dir: str) -> Optional['TimelineManager']:
        """Load timeline from file"""
        # Timeline is saved directly in run_dir (not in blackbox subfolder)
        timeline_file = os.path.join(run_dir, 'timeline.json')
        if not os.path.exists(timeline_file):
            # Fallback to old location for backwards compatibility
            timeline_file = os.path.join(run_dir, 'blackbox', 'timeline.json')
            if not os.path.exists(timeline_file):
                return None

        try:
            with open(timeline_file, 'r') as f:
                data = json.load(f)

            manager = cls(data['run_id'], run_dir)
            for event_data in data.get('events', []):
                event = TimelineEvent.from_dict(event_data)
                manager._events[event.event_id] = event
                manager._event_order.append(event.event_id)

            return manager
        except Exception as e:
            logger.error(f"Failed to load timeline: {e}")
            return None

    # =========================================
    # Convenience methods for common events
    # =========================================

    def run_started(self, game_name: str, sut_ip: str, iterations: int):
        """Log run started"""
        return self.add_event(
            "run_start",
            TimelineEventType.RUN_STARTED,
            f"Starting automation: {game_name}",
            status=TimelineEventStatus.IN_PROGRESS,
            metadata={'game': game_name, 'sut_ip': sut_ip, 'iterations': iterations}
        )

    def run_completed(self, success_count: int, total: int):
        """Log run completed"""
        return self.add_event(
            "run_complete",
            TimelineEventType.RUN_COMPLETED,
            f"Run completed: {success_count}/{total} iterations successful",
            status=TimelineEventStatus.COMPLETED,
            metadata={'success_count': success_count, 'total': total},
            replaces="run_start"
        )

    def run_failed(self, error: str):
        """Log run failed and mark all in-progress events as failed"""
        # First, fail all in-progress events
        self._fail_all_in_progress()

        return self.add_event(
            "run_failed",
            TimelineEventType.RUN_FAILED,
            f"Run failed: {error}",
            status=TimelineEventStatus.FAILED,
            metadata={'error': error},
            replaces="run_start"
        )

    def run_cancelled(self, reason: str = "User cancelled"):
        """Log run cancelled by user and mark all in-progress events as cancelled"""
        # Mark all in-progress events as failed (cancelled is a type of failure)
        self._fail_all_in_progress()

        return self.add_event(
            "run_cancelled",
            TimelineEventType.RUN_CANCELLED,
            f"Run cancelled: {reason}",
            status=TimelineEventStatus.FAILED,
            metadata={'reason': reason, 'cancelled_by': 'user'},
            replaces="run_start"
        )

    def _fail_all_in_progress(self):
        """Mark all in-progress events as failed"""
        changed = False
        for event in self._events.values():
            if event.status == TimelineEventStatus.IN_PROGRESS:
                event.status = TimelineEventStatus.FAILED
                # Calculate duration
                duration = (datetime.now() - event.timestamp).total_seconds() * 1000
                event.duration_ms = int(duration)
                logger.debug(f"Marked event '{event.event_id}' as failed")
                changed = True
        if changed:
            self._save()
            # Notify for each failed event
            for event in self._events.values():
                if event.status == TimelineEventStatus.FAILED:
                    self._notify(event)

    def iteration_started(self, iteration: int, total: int):
        """Log iteration started"""
        return self.add_event(
            f"iteration_{iteration}",
            TimelineEventType.ITERATION_STARTED,
            f"Starting iteration {iteration}/{total}",
            status=TimelineEventStatus.IN_PROGRESS,
            group="iteration"
        )

    def iteration_completed(self, iteration: int, success: bool):
        """Log iteration completed"""
        status = TimelineEventStatus.COMPLETED if success else TimelineEventStatus.FAILED
        msg = f"Iteration {iteration} {'completed' if success else 'failed'}"
        return self.add_event(
            f"iteration_{iteration}_done",
            TimelineEventType.ITERATION_COMPLETED,
            msg,
            status=status,
            replaces=f"iteration_{iteration}",
            group="iteration"
        )

    def sut_connecting(self, ip: str, port: int = 8080):
        """Log SUT connection starting"""
        return self.add_event(
            "sut_connect",
            TimelineEventType.SUT_CONNECTING,
            f"Connecting to SUT {ip}:{port}...",
            metadata={'ip': ip, 'port': port}
        )

    def sut_connected(self, ip: str, port: int = 8080):
        """Log SUT connected"""
        return self.add_event(
            "sut_connected",
            TimelineEventType.SUT_CONNECTED,
            f"Connected to SUT {ip}:{port}",
            status=TimelineEventStatus.COMPLETED,
            metadata={'ip': ip, 'port': port},
            replaces="sut_connect"
        )

    def sut_connection_failed(self, ip: str, error: str):
        """Log SUT connection failed"""
        return self.add_event(
            "sut_failed",
            TimelineEventType.SUT_CONNECTION_FAILED,
            f"Failed to connect to SUT {ip}: {error}",
            status=TimelineEventStatus.FAILED,
            metadata={'ip': ip, 'error': error},
            replaces="sut_connect"
        )

    def resolution_detecting(self):
        """Log resolution detection starting"""
        return self.add_event(
            "resolution",
            TimelineEventType.RESOLUTION_DETECTING,
            "Detecting screen resolution..."
        )

    def resolution_detected(self, width: int, height: int):
        """Log resolution detected"""
        return self.add_event(
            "resolution_done",
            TimelineEventType.RESOLUTION_DETECTED,
            f"Resolution: {width}x{height}",
            status=TimelineEventStatus.COMPLETED,
            metadata={'width': width, 'height': height},
            replaces="resolution"
        )

    def omniparser_connecting(self, url: str):
        """Log OmniParser connection starting"""
        return self.add_event(
            "omniparser",
            TimelineEventType.OMNIPARSER_CONNECTING,
            f"Connecting to OmniParser..."
        )

    def omniparser_connected(self, url: str):
        """Log OmniParser connected"""
        return self.add_event(
            "omniparser_done",
            TimelineEventType.OMNIPARSER_CONNECTED,
            "OmniParser connected",
            status=TimelineEventStatus.COMPLETED,
            metadata={'url': url},
            replaces="omniparser"
        )

    def preset_syncing(self, game: str, preset: str = None, parallel_info: str = None):
        """Log preset sync starting

        Args:
            game: Game name
            preset: Preset name (optional)
            parallel_info: Info about parallel tasks (e.g., "while game terminates")
        """
        msg = f"Syncing preset for {game}"
        if preset:
            msg += f" ({preset})"
        if parallel_info:
            msg += f" ({parallel_info})"
        return self.add_event(
            "preset",
            TimelineEventType.PRESET_SYNCING,
            msg + "...",
            metadata={'game': game, 'preset': preset, 'parallel': parallel_info is not None}
        )

    def preset_synced(self, game: str, preset: str = None):
        """Log preset synced"""
        msg = f"Preset applied for {game}"
        if preset:
            msg += f" ({preset})"
        return self.add_event(
            "preset_done",
            TimelineEventType.PRESET_SYNCED,
            msg,
            status=TimelineEventStatus.COMPLETED,
            metadata={'game': game, 'preset': preset},
            replaces="preset"
        )

    def preset_skipped(self, reason: str = "not configured"):
        """Log preset skipped"""
        return self.add_event(
            "preset_skipped",
            TimelineEventType.PRESET_SKIPPED,
            f"Preset sync skipped: {reason}",
            status=TimelineEventStatus.SKIPPED,
            replaces="preset"
        )

    def game_launching(self, game_name: str, path: str = None):
        """Log game launching"""
        msg = f"Launching {game_name}"
        if path:
            # Show just the filename or app ID
            short_path = os.path.basename(path) if '\\' in path or '/' in path else path
            msg += f" ({short_path})"
        return self.add_event(
            "game_launch",
            TimelineEventType.GAME_LAUNCHING,
            msg + "...",
            metadata={'game': game_name, 'path': path}
        )

    def game_launched(self, game_name: str, pid: int = None):
        """Log game launched"""
        msg = f"Game launched"
        if pid:
            msg += f" (PID: {pid})"
        return self.add_event(
            "game_launched",
            TimelineEventType.GAME_LAUNCHED,
            msg,
            status=TimelineEventStatus.COMPLETED,
            metadata={'game': game_name, 'pid': pid},
            replaces="game_launch"
        )

    def game_process_waiting(self, process_name: str, timeout_seconds: int = 60):
        """Log waiting for game process to appear with countdown"""
        return self.add_event(
            "game_process_wait",
            TimelineEventType.GAME_PROCESS_WAITING,
            f"Waiting for process '{process_name}' ({timeout_seconds}s)...",
            metadata={'process_name': process_name, 'timeout': timeout_seconds, 'countdown': timeout_seconds}
        )

    def game_process_detected(self, process_name: str, pid: int = None):
        """Log game process detected"""
        msg = f"Process '{process_name}' detected"
        if pid:
            msg += f" (PID: {pid})"
        return self.add_event(
            "game_process_found",
            TimelineEventType.GAME_PROCESS_DETECTED,
            msg,
            status=TimelineEventStatus.COMPLETED,
            metadata={'process_name': process_name, 'pid': pid},
            replaces="game_process_wait"
        )

    def game_process_timeout(self, process_name: str, timeout_seconds: int):
        """Log game process wait timeout"""
        return self.add_event(
            "game_process_timeout",
            TimelineEventType.GAME_LAUNCH_FAILED,
            f"Process '{process_name}' not detected after {timeout_seconds}s",
            status=TimelineEventStatus.FAILED,
            metadata={'process_name': process_name, 'timeout': timeout_seconds},
            replaces="game_process_wait"
        )

    def game_initializing(self, wait_seconds: int):
        """Log waiting for game to initialize"""
        return self.add_event(
            "game_init",
            TimelineEventType.GAME_INITIALIZING,
            f"Waiting {wait_seconds}s for game to initialize...",
            metadata={'wait_seconds': wait_seconds, 'countdown': wait_seconds}
        )

    def game_ready(self):
        """Log game ready"""
        return self.add_event(
            "game_ready",
            TimelineEventType.GAME_READY,
            "Game ready",
            status=TimelineEventStatus.COMPLETED,
            replaces="game_init"
        )

    # ===== Steam Dialog Events =====

    def steam_dialog_checking(self):
        """Log that we're checking for Steam dialogs"""
        return self.add_event(
            "steam_check",
            TimelineEventType.STEAM_DIALOG_CHECKING,
            "Checking for Steam dialogs...",
        )

    def steam_dialog_detected(self, dialog_name: str, handler: str):
        """Log that a Steam dialog was detected"""
        return self.add_event(
            "steam_dialog",
            TimelineEventType.STEAM_DIALOG_DETECTED,
            f"Steam dialog: {dialog_name}",
            status=TimelineEventStatus.IN_PROGRESS,
            metadata={'dialog': dialog_name, 'handler': handler},
            replaces="steam_check"
        )

    def steam_dialog_dismissed(self, dialog_name: str):
        """Log that a Steam dialog was dismissed"""
        return self.add_event(
            "steam_dismissed",
            TimelineEventType.STEAM_DIALOG_DISMISSED,
            f"Dialog dismissed: {dialog_name}",
            status=TimelineEventStatus.COMPLETED,
            metadata={'dialog': dialog_name},
            replaces="steam_dialog"
        )

    def steam_account_busy(self, account: str, game: str):
        """Log that a Steam account is busy on another machine"""
        return self.add_event(
            "steam_busy",
            TimelineEventType.STEAM_ACCOUNT_BUSY,
            f"Account '{account}' busy - in use elsewhere",
            status=TimelineEventStatus.WARNING,
            metadata={'account': account, 'game': game},
            replaces="steam_dialog"
        )

    def steam_account_switching(self, from_account: str, to_account: str):
        """Log switching to a different Steam account"""
        return self.add_event(
            "steam_switch",
            TimelineEventType.STEAM_ACCOUNT_SWITCHING,
            f"Switching account: {from_account} -> {to_account}",
            metadata={'from_account': from_account, 'to_account': to_account}
        )

    def steam_no_accounts(self, game: str):
        """Log that no available Steam accounts remain"""
        return self.add_event(
            "steam_fail",
            TimelineEventType.STEAM_NO_ACCOUNTS,
            f"No available Steam accounts for {game}",
            status=TimelineEventStatus.ERROR,
            metadata={'game': game}
        )

    def steam_check_passed(self):
        """Log that no Steam dialog was detected"""
        return self.add_event(
            "steam_ok",
            TimelineEventType.STEAM_DIALOG_CHECKING,
            "No Steam dialog detected",
            status=TimelineEventStatus.COMPLETED,
            replaces="steam_check"
        )

    def step_started(self, step_num: int, description: str, total_steps: int = None, duration: int = None):
        """Log step started

        Args:
            step_num: Step number
            description: Step description
            total_steps: Total number of steps
            duration: Optional duration in seconds for wait steps
        """
        msg = f"Step {step_num}"
        if total_steps:
            msg += f"/{total_steps}"
        msg += f": {description}"

        metadata = {'step': step_num, 'description': description, 'total': total_steps}
        # Add duration for wait steps so frontend can show countdown
        if duration:
            metadata['duration'] = duration

        return self.add_event(
            f"step_{step_num}",
            TimelineEventType.STEP_STARTED,
            msg,
            metadata=metadata,
            group="steps"
        )

    def step_completed(self, step_num: int, description: str = None):
        """Log step completed"""
        if description:
            # Shorten description: "Click OPTIONS to access benchmark" -> "OPTIONS clicked"
            msg = f"Step {step_num} done"
        else:
            msg = f"Step {step_num} done"
        return self.add_event(
            f"step_{step_num}_done",
            TimelineEventType.STEP_COMPLETED,
            msg,
            status=TimelineEventStatus.COMPLETED,
            replaces=f"step_{step_num}",
            group="steps"
        )

    def step_failed(self, step_num: int, error: str = None):
        """Log step failed"""
        msg = f"Step {step_num} failed"
        if error:
            msg += f": {error}"
        return self.add_event(
            f"step_{step_num}_failed",
            TimelineEventType.STEP_FAILED,
            msg,
            status=TimelineEventStatus.FAILED,
            metadata={'error': error},
            replaces=f"step_{step_num}",
            group="steps"
        )

    def step_skipped(self, step_num: int, reason: str = None):
        """Log step skipped"""
        msg = f"Step {step_num} skipped"
        if reason:
            msg += f" ({reason})"
        return self.add_event(
            f"step_{step_num}_skipped",
            TimelineEventType.STEP_SKIPPED,
            msg,
            status=TimelineEventStatus.SKIPPED,
            replaces=f"step_{step_num}",
            group="steps"
        )

    def benchmark_starting(self, duration: int = None):
        """Log benchmark starting"""
        msg = "Starting benchmark"
        if duration:
            msg += f" ({duration}s)"
        return self.add_event(
            "benchmark",
            TimelineEventType.BENCHMARK_STARTING,
            msg + "...",
            metadata={'duration': duration}
        )

    def benchmark_running(self, duration: int):
        """Log benchmark running"""
        return self.add_event(
            "benchmark_run",
            TimelineEventType.BENCHMARK_RUNNING,
            f"Benchmark running ({duration}s)...",
            metadata={'duration': duration},
            replaces="benchmark"
        )

    def benchmark_completed(self):
        """Log benchmark completed"""
        return self.add_event(
            "benchmark_done",
            TimelineEventType.BENCHMARK_COMPLETED,
            "Benchmark completed",
            status=TimelineEventStatus.COMPLETED,
            replaces="benchmark_run"
        )

    def waiting(self, seconds: int, reason: str = None):
        """Log waiting period"""
        msg = f"Waiting {seconds}s"
        if reason:
            msg += f" ({reason})"
        return self.add_event(
            self._generate_event_id("wait"),
            TimelineEventType.WAITING,
            msg + "...",
            metadata={'seconds': seconds, 'reason': reason}
        )

    def game_exiting(self):
        """Log game exiting"""
        return self.add_event(
            "game_exit",
            TimelineEventType.GAME_EXITING,
            "Closing game..."
        )

    def game_exited(self, graceful: bool = True):
        """Log game exited"""
        msg = "Game exited gracefully" if graceful else "Game terminated"
        return self.add_event(
            "game_exited",
            TimelineEventType.GAME_EXITED,
            msg,
            status=TimelineEventStatus.COMPLETED,
            replaces="game_exit"
        )

    def info(self, message: str, metadata: Dict[str, Any] = None):
        """Log info event"""
        return self.add_event(
            self._generate_event_id("info"),
            TimelineEventType.INFO,
            message,
            status=TimelineEventStatus.COMPLETED,
            metadata=metadata
        )

    def warning(self, message: str, metadata: Dict[str, Any] = None):
        """Log warning event"""
        return self.add_event(
            self._generate_event_id("warn"),
            TimelineEventType.WARNING,
            message,
            status=TimelineEventStatus.COMPLETED,
            metadata=metadata
        )

    def error(self, message: str, error: str = None):
        """Log error event"""
        return self.add_event(
            self._generate_event_id("error"),
            TimelineEventType.ERROR,
            message,
            status=TimelineEventStatus.FAILED,
            metadata={'error': error} if error else None
        )
