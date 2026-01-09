# -*- coding: utf-8 -*-
"""
Automation Orchestrator - Integrates the existing automation engine with the backend
"""

import logging
import threading
import time
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime

# Add the main directory to the path to import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import base64
import yaml
import requests

from .run_manager import AutomationRun, RunResult, RunStatus
from .events import event_bus, EventType
from .timeline_manager import TimelineManager
from .account_pool import get_account_pool

# Steam dialogs config path
STEAM_DIALOGS_CONFIG = Path(__file__).parent.parent.parent / "config" / "steam_dialogs.yaml"

if TYPE_CHECKING:
    from .run_storage import RunStorageManager

logger = logging.getLogger(__name__)


class StepProgressCallback:
    """Callback class for tracking step progress during automation.

    This class:
    1. Updates the run's progress.steps list for API responses
    2. Emits WebSocket events for real-time timeline updates in the frontend
    3. Updates the TimelineManager for comprehensive run timeline
    """

    def __init__(self, run: 'AutomationRun', run_dir: str = None, timeline: TimelineManager = None):
        self.run = run
        self.run_id = run.run_id
        self.run_dir = run_dir
        self.timeline = timeline  # For comprehensive timeline tracking
        self.total_steps = 0
        self.completed_steps = 0
        self._current_step = 0
        self._step_map: Dict[int, Any] = {}  # step_number -> StepProgress

    def _get_screenshot_url(self, step_number: int) -> Optional[str]:
        """Get screenshot URL for a step"""
        if self.run_dir:
            return f"/api/runs/{self.run_id}/screenshots/step_{step_number}.png"
        return None

    def _update_run_step(self, step_number: int, **kwargs):
        """Update or create a step in the run's progress"""
        from .run_manager import StepProgress, StepStatus

        # Find existing step or create new one
        existing_step = None
        for step in self.run.progress.steps:
            if step.step_number == step_number:
                existing_step = step
                break

        if existing_step:
            # Update existing step
            for key, value in kwargs.items():
                if hasattr(existing_step, key):
                    if key == 'status' and isinstance(value, str):
                        value = StepStatus(value)
                    setattr(existing_step, key, value)
        else:
            # Create new step
            status = kwargs.get('status', 'pending')
            if isinstance(status, str):
                status = StepStatus(status)

            new_step = StepProgress(
                step_number=step_number,
                description=kwargs.get('description', f'Step {step_number}'),
                status=status,
                started_at=datetime.fromisoformat(kwargs['started_at']) if kwargs.get('started_at') else None,
                completed_at=datetime.fromisoformat(kwargs['completed_at']) if kwargs.get('completed_at') else None,
                screenshot_url=kwargs.get('screenshot_url'),
                error_message=kwargs.get('error_message'),
                is_optional=kwargs.get('is_optional', False),
            )
            self.run.progress.steps.append(new_step)

        # Update current step in progress
        self.run.progress.current_step = step_number

    def on_step_start(self, step_number: int, description: str):
        """Called when a step begins execution"""
        self._current_step = step_number
        self._current_step_description = description  # Track for completion message
        screenshot_url = self._get_screenshot_url(step_number)
        started_at = datetime.now().isoformat()

        # Update run's progress.steps
        self._update_run_step(
            step_number,
            description=description,
            status='in_progress',
            started_at=started_at,
            screenshot_url=screenshot_url,
        )

        # Update timeline - include duration for wait steps
        if self.timeline:
            # Get duration from current step config if it's a wait step
            duration = getattr(self, '_current_step_duration', None)
            self.timeline.step_started(step_number, description, self.total_steps, duration=duration)

        # Emit WebSocket event for real-time UI updates
        event_bus.emit(EventType.AUTOMATION_STEP_STARTED, {
            'run_id': self.run_id,
            'step': {
                'step_number': step_number,
                'description': description,
                'status': 'in_progress',
                'started_at': started_at,
                'screenshot_url': screenshot_url,
            }
        })

    def on_step_complete(self, step_number: int, success: bool = True, error_message: str = None):
        """Called when a step completes"""
        self.completed_steps = step_number
        screenshot_url = self._get_screenshot_url(step_number)
        completed_at = datetime.now().isoformat()
        status = 'completed' if success else 'failed'

        # Update run's progress.steps
        self._update_run_step(
            step_number,
            status=status,
            completed_at=completed_at,
            screenshot_url=screenshot_url,
            error_message=error_message,
        )

        # Update timeline with description for better message
        if self.timeline:
            description = getattr(self, '_current_step_description', None)
            if success:
                self.timeline.step_completed(step_number, description)
            else:
                self.timeline.step_failed(step_number, error_message)

        # Emit WebSocket event
        event_type = EventType.AUTOMATION_STEP_COMPLETED if success else EventType.AUTOMATION_STEP_FAILED
        event_bus.emit(event_type, {
            'run_id': self.run_id,
            'step': {
                'step_number': step_number,
                'status': status,
                'completed_at': completed_at,
                'screenshot_url': screenshot_url,
                'error_message': error_message,
            }
        })

    def on_step_skip(self, step_number: int, reason: str = None):
        """Called when an optional step is skipped"""
        completed_at = datetime.now().isoformat()

        # Update run's progress.steps
        self._update_run_step(
            step_number,
            status='skipped',
            completed_at=completed_at,
            error_message=reason,
            is_optional=True,
        )

        # Update timeline
        if self.timeline:
            self.timeline.step_skipped(step_number, reason)

        # Emit WebSocket event
        event_bus.emit(EventType.AUTOMATION_STEP_COMPLETED, {
            'run_id': self.run_id,
            'step': {
                'step_number': step_number,
                'status': 'skipped',
                'completed_at': completed_at,
                'error_message': reason,
            }
        })


class AutomationOrchestrator:
    """Orchestrates automation execution using the existing engine from modules/"""

    def __init__(self, game_manager, device_registry, omniparser_client, discovery_client=None, websocket_handler=None):
        self.game_manager = game_manager
        self.device_registry = device_registry
        self.omniparser_client = omniparser_client
        self.discovery_client = discovery_client
        self.websocket_handler = websocket_handler

        # Storage manager reference (set by RunManager)
        self.storage: Optional['RunStorageManager'] = None

        # Import paths for the automation modules
        self.modules_path = os.path.join(os.path.dirname(__file__), '../..', 'modules')

        logger.info("AutomationOrchestrator initialized")

    def set_storage(self, storage: 'RunStorageManager'):
        """Set the storage manager for persistent run storage"""
        self.storage = storage
        logger.info("Storage manager attached to orchestrator")

    def _create_timeline_callback(self, run_id: str):
        """Create a callback function for timeline events that emits via WebSocket"""
        def on_timeline_event(event: 'TimelineEvent'):
            if self.websocket_handler:
                try:
                    # Serialize the event for WebSocket
                    event_data = {
                        'run_id': run_id,
                        'event_id': event.event_id,
                        'event_type': event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
                        'message': event.message,
                        'status': event.status.value if hasattr(event.status, 'value') else str(event.status),
                        'timestamp': event.timestamp.isoformat() if event.timestamp else None,
                        'duration_ms': event.duration_ms,
                        'metadata': event.metadata,
                        'group': event.group,
                    }
                    # Emit to general updates and run-specific room
                    self.websocket_handler.broadcast_message('timeline_event', event_data)
                    self.websocket_handler.broadcast_message('timeline_event', event_data, room=f'run_{run_id}')
                except Exception as e:
                    logger.error(f"Error emitting timeline event via WebSocket: {e}")
        return on_timeline_event
    
    def execute_run(self, run: AutomationRun) -> tuple[bool, Optional[RunResult], Optional[str]]:
        """
        Execute a single automation run using the existing automation engine

        Returns:
            (success, results, error_message)
        """
        logger.info(f"Starting execution of {run.game_name} on SUT {run.sut_ip}")

        # Get run directory from storage manager (correct path for new run structure)
        if self.storage:
            base_run_dir = str(self.storage.get_run_dir(run.run_id))
        else:
            # Fallback to old method if storage not available
            base_run_dir = self._get_run_directory(run)
        os.makedirs(base_run_dir, exist_ok=True)

        # Create timeline manager for comprehensive run tracking
        # Pass WebSocket callback for real-time timeline updates
        timeline = TimelineManager(
            run.run_id,
            base_run_dir,
            on_event=self._create_timeline_callback(run.run_id)
        )
        timeline.run_started(run.game_name, run.sut_ip, run.iterations)

        # Store timeline reference on run for API access AND for stop_run() to emit cancel event
        run.timeline = timeline

        # Create a shared stop_event and store it on the run object
        # This allows stop_run() to set it and interrupt the automation
        import threading
        run.stop_event = threading.Event()

        # Acquire Steam account pair for this SUT (for multi-SUT automation)
        account_pool = get_account_pool()
        account_acquired = False
        if account_pool.is_configured():
            account_acquired = account_pool.acquire_account_pair(run.sut_ip)
            if account_acquired:
                account_info = account_pool.get_current_account(run.sut_ip, run.game_name)
                timeline.info(f"Steam account acquired: {account_info}")
                logger.info(f"Acquired Steam account '{account_info}' for SUT {run.sut_ip}")
            else:
                timeline.warning("No Steam account pairs available - using existing Steam login on SUT")
                logger.warning(f"No account pairs available for SUT {run.sut_ip}")

        try:
            # Reload game configs from disk to pick up any YAML changes
            self.game_manager.reload_configurations()

            # Get game configuration
            game_config = self.game_manager.get_game(run.game_name)
            if not game_config:
                timeline.run_failed(f"Game '{run.game_name}' not found")
                return False, None, f"Game '{run.game_name}' not found"

            # Get SUT device
            device = None
            if self.discovery_client:
                # Use Discovery Service to find device by IP (sync version)
                try:
                    suts = self.discovery_client.get_suts_sync()
                    # Find an online SUT with matching IP (prefer online over offline)
                    matching_suts = [s for s in suts if s.get("ip") == run.sut_ip]
                    online_sut = next((s for s in matching_suts if s.get("status") == "online" or s.get("is_online")), None)

                    if online_sut:
                        # Create a simple object with required attributes
                        class DeviceProxy:
                            def __init__(self, data):
                                self.unique_id = data.get("unique_id")
                                self.ip = data.get("ip")
                                self.port = data.get("port", 8080)
                                self.hostname = data.get("hostname")
                                self.is_online = True  # We know it's online
                        device = DeviceProxy(online_sut)
                    elif matching_suts:
                        # All matching SUTs are offline
                        timeline.sut_connection_failed(run.sut_ip, "SUT is offline")
                        timeline.run_failed(f"SUT {run.sut_ip} is not online")
                        return False, None, f"SUT {run.sut_ip} is not online"
                except Exception as e:
                    logger.error(f"Error querying Discovery Service: {e}")
                    timeline.sut_connection_failed(run.sut_ip, str(e))
            else:
                device = self.device_registry.get_device_by_ip(run.sut_ip)
                if device and not device.is_online:
                    timeline.sut_connection_failed(run.sut_ip, "SUT is offline")
                    timeline.run_failed(f"SUT {run.sut_ip} is not online")
                    return False, None, f"SUT {run.sut_ip} is not online"

            if not device:
                timeline.sut_connection_failed(run.sut_ip, "SUT not found")
                timeline.run_failed(f"SUT {run.sut_ip} not found")
                return False, None, f"SUT {run.sut_ip} not found"

            # Execute multiple iterations
            successful_runs = 0
            total_runs = run.iterations
            error_logs = []

            # Run-level state for resolution (only change once, restore at end)
            run_resolution_changed = False
            run_original_resolution = None  # Will store (width, height) from first iteration

            for iteration in range(run.iterations):
                logger.info(f"Starting iteration {iteration + 1}/{run.iterations} for run {run.run_id}")
                timeline.iteration_started(iteration + 1, run.iterations)
                
                # Check if run was stopped
                if run.status != RunStatus.RUNNING:
                    logger.info(f"Run {run.run_id} was stopped during iteration {iteration + 1}")
                    break
                
                try:
                    # Execute single iteration (pass timeline for detailed events)
                    # Pass run-level resolution state to avoid changing per iteration
                    iteration_success, iter_original_res, iter_res_changed = self._execute_single_iteration(
                        run, game_config, device, iteration + 1, timeline,
                        skip_resolution_change=run_resolution_changed
                    )
                    # Store original resolution and state from first iteration
                    if iteration == 0 and iter_res_changed:
                        run_original_resolution = iter_original_res
                        run_resolution_changed = iter_res_changed

                    if iteration_success:
                        successful_runs += 1
                        logger.info(f"Iteration {iteration + 1} completed successfully")
                        timeline.iteration_completed(iteration + 1, success=True)
                    else:
                        error_msg = f"Iteration {iteration + 1} failed"
                        error_logs.append(error_msg)
                        logger.warning(error_msg)
                        timeline.iteration_completed(iteration + 1, success=False)

                except FileNotFoundError as e:
                    error_msg = f"Game file not found (iteration {iteration + 1}): {str(e)}"
                    error_logs.append(error_msg)
                    logger.error(error_msg)
                    timeline.error(error_msg, str(e))
                    timeline.iteration_completed(iteration + 1, success=False)
                    # For file not found, fail fast - no point retrying other iterations
                    break
                except RuntimeError as e:
                    error_msg = f"Game launch failed (iteration {iteration + 1}): {str(e)}"
                    error_logs.append(error_msg)
                    logger.error(error_msg)
                    timeline.error(error_msg, str(e))
                    timeline.iteration_completed(iteration + 1, success=False)
                    # For launch failures, also fail fast
                    break
                except Exception as e:
                    error_msg = f"Unexpected error in iteration {iteration + 1}: {str(e)}"
                    error_logs.append(error_msg)
                    logger.error(error_msg, exc_info=True)
                    timeline.error(error_msg, str(e))
                    timeline.iteration_completed(iteration + 1, success=False)

            # Check if run was cancelled by user
            was_cancelled = run.status == RunStatus.STOPPED

            # Restore resolution at end of run (not per iteration)
            # This runs even if cancelled - each run only affects its own SUT
            if run_resolution_changed and run_original_resolution:
                try:
                    from modules.network import NetworkManager
                    orig_w, orig_h = run_original_resolution
                    logger.info(f"Restoring original SUT resolution ({orig_w}x{orig_h}) after run {'cancellation' if was_cancelled else 'completion'}...")
                    if timeline:
                        timeline.info(f"Restoring original resolution ({orig_w}x{orig_h})...")
                    # Create a fresh network connection just for resolution restore
                    restore_network = NetworkManager(device.ip, device.port)
                    if restore_network.set_resolution(orig_w, orig_h):
                        if timeline:
                            timeline.info(f"Resolution restored to {orig_w}x{orig_h}")
                        logger.info(f"Resolution restored to {orig_w}x{orig_h}")
                    else:
                        logger.warning(f"Failed to restore resolution to {orig_w}x{orig_h}")
                        if timeline:
                            timeline.warning(f"Failed to restore resolution to {orig_w}x{orig_h}")
                    restore_network.close()
                    time.sleep(2)  # Wait for display to settle after restore
                except Exception as res_err:
                    logger.warning(f"Failed to restore resolution: {res_err}")
                    if timeline:
                        timeline.warning(f"Failed to restore resolution: {res_err}")

            # Calculate results
            success_rate = successful_runs / total_runs if total_runs > 0 else 0.0

            results = RunResult(
                success_rate=success_rate,
                successful_runs=successful_runs,
                total_iterations=total_runs,
                run_directory=self._get_run_directory(run),
                error_logs=error_logs
            )

            overall_success = successful_runs > 0  # At least one iteration succeeded

            # Log run completion in timeline
            # Skip if cancelled - stop_run() already emitted run_cancelled event
            if not was_cancelled:
                if overall_success:
                    timeline.run_completed(successful_runs, total_runs)
                else:
                    timeline.run_failed(f"All {total_runs} iterations failed")

            return overall_success, results, None

        except Exception as e:
            error_msg = f"Critical error in run execution: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Try to restore resolution even on critical error (if we have the info)
            if 'run_resolution_changed' in locals() and run_resolution_changed and 'run_original_resolution' in locals() and run_original_resolution:
                try:
                    from modules.network import NetworkManager
                    orig_w, orig_h = run_original_resolution
                    logger.info(f"Restoring resolution ({orig_w}x{orig_h}) after critical error...")
                    restore_network = NetworkManager(device.ip, device.port)
                    restore_network.set_resolution(orig_w, orig_h)
                    restore_network.close()
                except Exception as res_err:
                    logger.warning(f"Failed to restore resolution after error: {res_err}")

            timeline.run_failed(error_msg)
            return False, None, error_msg

        finally:
            # Release Steam account pair if we acquired one
            if account_acquired:
                account_pool.release_account_pair(run.sut_ip)
                logger.info(f"Released Steam account pair for SUT {run.sut_ip}")

    def _execute_single_iteration(self, run: AutomationRun, game_config, device, iteration_num: int, timeline: TimelineManager = None, skip_resolution_change: bool = False) -> tuple:
        """Execute a single automation iteration

        Returns:
            tuple: (success: bool, original_resolution: tuple or None, resolution_changed: bool)
                   original_resolution is (width, height) if resolution was changed, else None
        """
        original_resolution = None  # Will store (width, height) if we change resolution
        resolution_changed = False
        try:
            # Import automation modules dynamically
            from modules.network import NetworkManager
            from modules.screenshot import ScreenshotManager
            from modules.omniparser_client import OmniparserClient
            from modules.simple_automation import SimpleAutomation
            from modules.game_launcher import GameLauncher

            # Mark iteration as started in storage
            if self.storage:
                self.storage.start_iteration(run.run_id, iteration_num)

            # Create run directory (use storage path if available)
            run_dir = self._create_run_directory(run, iteration_num)

            # Setup blackbox logging for this run
            self._setup_blackbox_logging(run_dir, game_config.name, run.run_id, iteration_num)

            # ===== SUT Connection =====
            if timeline:
                timeline.sut_connecting(device.ip, device.port)
            logger.info(f"Connecting to SUT at {device.ip}:{device.port}")
            network = NetworkManager(device.ip, device.port)
            screenshot_mgr = ScreenshotManager(network)
            if timeline:
                timeline.sut_connected(device.ip, device.port)

            # ===== Resolution Detection =====
            if timeline:
                timeline.resolution_detecting()
            try:
                resolution = network.get_resolution()
                screen_width = resolution.get('width', 1920)
                screen_height = resolution.get('height', 1080)
                logger.info(f"Using SUT screen resolution: {screen_width}x{screen_height}")
                if timeline:
                    timeline.resolution_detected(screen_width, screen_height)
            except Exception as e:
                logger.warning(f"Failed to get SUT resolution, using default 1920x1080: {e}")
                screen_width, screen_height = 1920, 1080
                if timeline:
                    timeline.resolution_detected(screen_width, screen_height)
                    timeline.warning(f"Using default resolution (detection failed: {e})")

            # ===== OmniParser Connection =====
            omniparser_url = getattr(self.omniparser_client, 'queue_url', None) or getattr(self.omniparser_client, 'api_url', 'http://localhost:9000')
            if timeline:
                timeline.omniparser_connecting(omniparser_url)
            vision_model = OmniparserClient(
                omniparser_url,
                screen_width=screen_width,
                screen_height=screen_height
            )
            if timeline:
                timeline.omniparser_connected(omniparser_url)

            game_launcher = GameLauncher(network)

            # ===== Steam Account Login =====
            # Skip Steam login if user pre-logged in manually (skip_steam_login flag)
            if run.skip_steam_login:
                if timeline:
                    timeline.info("Steam login skipped (manual login mode)")
                logger.info("Skipping Steam login - user pre-logged in manually on SUT")
                credentials = None  # No credentials needed
            else:
                # Get credentials - either from per-SUT allocation or directly by game type
                # (for multi-SUT parallel mode where account_scheduler handles exclusivity)
                account_pool = get_account_pool()
                if account_pool.has_allocation(run.sut_ip):
                    credentials = account_pool.get_account_for_game(run.sut_ip, run.game_name)
                else:
                    # Fallback: get credentials by game type (A-F or G-Z)
                    # This supports multi-SUT parallel execution where account_scheduler
                    # already ensures only one SUT uses each account type at a time
                    credentials = account_pool.get_account_by_game_type(run.game_name)

            if credentials:
                steam_username, steam_password = credentials

                # Get configurable timeout from env var (default 180s for slow connections)
                steam_login_timeout = int(os.environ.get("STEAM_LOGIN_TIMEOUT", "180"))

                def attempt_steam_login(username: str, password: str) -> dict:
                    """Attempt Steam login and return result dict"""
                    try:
                        return network.login_steam(username, password, timeout=steam_login_timeout)
                    except Exception as e:
                        logger.warning(f"Steam login request failed: {e}")
                        return {'success': False, 'status': 'error', 'message': str(e)}

                def handle_steam_login_with_retry(initial_username: str, initial_password: str) -> bool:
                    """
                    Handle Steam login with automatic retry using alternative account if conflict detected.

                    Returns True if login succeeded, False if failed (after retries).
                    """
                    username, password = initial_username, initial_password

                    # First attempt
                    if timeline:
                        timeline.info(f"Steam: Logging in as {username}")
                    logger.info(f"Attempting Steam login for: {username}")

                    login_result = attempt_steam_login(username, password)

                    if login_result.get('success'):
                        if timeline:
                            timeline.info(f"Steam login successful: {username}")
                        logger.info(f"Steam login completed for {username}")
                        # Clear any previous externally busy status for this account
                        account_pool.clear_externally_busy(username)
                        return True

                    elif login_result.get('status') == 'conflict':
                        # Account is in use on another device - try alternative
                        if timeline:
                            timeline.steam_account_busy(username, run.game_name)
                        logger.warning(f"Steam account '{username}' is in use on another device")

                        # Mark this account as externally busy
                        account_pool.mark_account_externally_busy(run.sut_ip, username, run.game_name)

                        # Try to get an alternative account
                        logger.info(f"Looking for alternative Steam account for SUT {run.sut_ip}")

                        alternative = account_pool.try_alternative_account(run.sut_ip, run.game_name)

                        if alternative:
                            alt_username, alt_password = alternative
                            if timeline:
                                timeline.steam_account_switching(username, alt_username)
                            logger.info(f"Trying alternative Steam account: {alt_username}")

                            # Retry with alternative account
                            alt_result = attempt_steam_login(alt_username, alt_password)

                            if alt_result.get('success'):
                                if timeline:
                                    timeline.info(f"Steam login successful with alternative: {alt_username}")
                                logger.info(f"Steam login completed with alternative account: {alt_username}")
                                account_pool.clear_externally_busy(alt_username)
                                return True
                            elif alt_result.get('status') == 'conflict':
                                # Alternative also in use - fail
                                if timeline:
                                    timeline.error(f"Alternative account '{alt_username}' also in use on another device!")
                                logger.error(f"Alternative account '{alt_username}' also in use elsewhere")
                                account_pool.mark_account_externally_busy(run.sut_ip, alt_username, run.game_name)
                                return False
                            else:
                                if timeline:
                                    timeline.warning(f"Alternative account login failed: {alt_result.get('message', 'unknown')}")
                                logger.warning(f"Alternative Steam login failed: {alt_result.get('message')}")
                                return False
                        else:
                            # No alternative accounts available
                            if timeline:
                                timeline.steam_no_accounts(run.game_name)
                            logger.error("No alternative Steam account pairs available")
                            return False
                    else:
                        # Other login failure (timeout, etc.)
                        if timeline:
                            timeline.warning(f"Steam login failed: {login_result.get('message', 'unknown')}")
                        logger.warning(f"Steam login failed for {username}: {login_result.get('message')}")
                        return False

                # Check current logged-in Steam user before attempting login
                current_steam = network.get_current_steam_user()
                if current_steam and current_steam.get("logged_in"):
                    current_user = current_steam.get("username", "").lower()
                    if current_user == steam_username.lower():
                        if timeline:
                            timeline.info(f"Steam: Already logged in as {steam_username}")
                        logger.info(f"Steam already logged in as {steam_username}, skipping login")
                    else:
                        # Different user logged in - need to switch
                        if timeline:
                            timeline.info(f"Steam: Need to switch from {current_user} to {steam_username}")
                        logger.info(f"Switching Steam account from {current_user} to {steam_username}")

                        login_success = handle_steam_login_with_retry(steam_username, steam_password)
                        if not login_success:
                            # Steam login failed and no alternatives - fail the iteration
                            error_msg = f"Steam login failed: All accounts in use or unavailable"
                            if timeline:
                                timeline.error(error_msg)
                            logger.error(error_msg)
                            if self.storage:
                                self.storage.complete_iteration(run.run_id, iteration_num, success=False, error_message=error_msg)
                            return False, None, False
                else:
                    # No user logged in or Steam not running - login
                    logger.info(f"Steam not logged in, initiating login for: {steam_username}")

                    login_success = handle_steam_login_with_retry(steam_username, steam_password)
                    if not login_success:
                        # Steam login failed and no alternatives - fail the iteration
                        error_msg = f"Steam login failed: All accounts in use or unavailable"
                        if timeline:
                            timeline.error(error_msg)
                        logger.error(error_msg)
                        if self.storage:
                            self.storage.complete_iteration(run.run_id, iteration_num, success=False, error_message=error_msg)
                        return False, None, False
            else:
                logger.debug(f"No credentials returned for SUT {run.sut_ip}, using existing Steam session")

            # Use the run's stop_event (created in execute_run) so stop_run() can interrupt us
            # This is critical - if we create a new one here, stop_run() can't cancel us!
            stop_event = run.stop_event

            # Create progress callback for step-level events (with timeline reference)
            progress_callback = StepProgressCallback(
                run=run,
                run_dir=run_dir,
                timeline=timeline
            )

            # Initialize SimpleAutomation
            automation = SimpleAutomation(
                config_path=game_config.yaml_path,
                network=network,
                screenshot_mgr=screenshot_mgr,
                vision_model=vision_model,
                stop_event=stop_event,
                run_dir=run_dir,
                progress_callback=progress_callback,
            )

            # ===== Preset Sync =====
            if timeline:
                timeline.preset_syncing(game_config.name)
            preset_result = self._sync_preset_to_sut(game_config, device, run.quality, run.resolution)
            if timeline:
                if preset_result:
                    timeline.preset_synced(game_config.name)
                else:
                    timeline.preset_skipped("No preset configured or sync failed")

            # ===== Resolution Switching =====
            # Priority: run.resolution > game_config.resolution
            # Only change resolution on first iteration (skip_resolution_change=False)
            # Resolution is restored at the END of the entire run, not per iteration

            # Map resolution presets to dimensions
            resolution_map = {
                '720p': (1280, 720),
                '1080p': (1920, 1080),
                '1440p': (2560, 1440),
                '2160p': (3840, 2160),
            }

            # Check for run-level resolution (from UI selection) or fall back to game config
            target_resolution = run.resolution or getattr(game_config, 'resolution', None)

            if target_resolution and not skip_resolution_change:
                # Parse resolution - could be preset (e.g., "1080p") or dimensions (e.g., "1920x1080")
                try:
                    if target_resolution in resolution_map:
                        target_width, target_height = resolution_map[target_resolution]
                        logger.info(f"Using run preset resolution: {target_resolution} -> {target_width}x{target_height}")
                    else:
                        target_width, target_height = map(int, target_resolution.lower().split('x'))

                    # Only change if different from current
                    if target_width != screen_width or target_height != screen_height:
                        if timeline:
                            timeline.info(f"Changing resolution from {screen_width}x{screen_height} to {target_width}x{target_height}")
                        logger.info(f"Target resolution {target_width}x{target_height} differs from current {screen_width}x{screen_height}")

                        # Store original resolution for run-level restore
                        original_resolution = (screen_width, screen_height)

                        # Check if target resolution is supported
                        if network.is_resolution_supported(target_width, target_height):
                            if network.set_resolution(target_width, target_height):
                                resolution_changed = True
                                screen_width, screen_height = target_width, target_height
                                if timeline:
                                    timeline.info(f"Resolution changed to {target_width}x{target_height}")
                                logger.info(f"Resolution changed to {target_width}x{target_height}")

                                # Update OmniParser client with new resolution
                                vision_model.screen_width = target_width
                                vision_model.screen_height = target_height

                                # Wait 5 seconds for display to settle after resolution change
                                logger.info("Waiting 5 seconds for display to settle...")
                                time.sleep(5)
                            else:
                                if timeline:
                                    timeline.warning(f"Failed to change resolution to {target_width}x{target_height}")
                                logger.warning(f"Failed to change resolution to {target_width}x{target_height}")
                        else:
                            if timeline:
                                timeline.warning(f"Resolution {target_width}x{target_height} not supported by SUT")
                            logger.warning(f"Resolution {target_width}x{target_height} not supported by SUT")
                    else:
                        logger.info(f"Resolution already at target {target_width}x{target_height}, no change needed")
                except ValueError:
                    logger.warning(f"Invalid resolution format in game config: {target_resolution}")

            # Discover game path from SUT or use YAML config as fallback
            game_path = self._discover_game_path(network, game_config)

            if game_path:
                # ===== Game Launch =====
                # SUT waits up to 60s for game process to appear
                process_wait_timeout = 60
                if timeline:
                    timeline.game_launching(game_config.name, game_path)
                    # Add process wait event - frontend shows 60s countdown
                    timeline.game_process_waiting(
                        process_name=game_config.process_id or game_config.name,
                        timeout_seconds=process_wait_timeout
                    )
                logger.info(f"Launching game: {game_path}")

                try:
                    # Pass process_id, startup_wait, and launch_args from game config
                    process_id = game_config.process_id or ''
                    startup_wait = game_config.startup_wait
                    launch_args = game_config.launch_args
                    logger.info(f"Launch params - process_id: {process_id}, startup_wait: {startup_wait}s, args: {launch_args}")
                    game_launcher.launch(game_path, process_id=process_id, startup_wait=startup_wait, launch_args=launch_args)
                    logger.info(f"Game launched successfully: {game_path}")
                    if timeline:
                        # Mark process as detected (replaces process wait event)
                        timeline.game_process_detected(
                            process_name=game_config.process_id or game_config.name
                        )
                        timeline.game_launched(game_config.name)

                    # NOTE: Steam dialog check is NOT run after successful launch.
                    # If the game process was detected within 60s, we assume no blocking
                    # Steam dialogs are present. Steam dialog checking only runs when
                    # the 60s process detection times out (handled in the exception block below).

                except Exception as e:
                    error_str = str(e)
                    error_msg = f"Failed to launch game '{game_config.name}': {error_str}"
                    logger.error(error_msg)

                    # Check if this might be a Steam dialog blocking (process not detected)
                    if "not detected" in error_str.lower() or "process" in error_str.lower():
                        # Mark process wait as timed out
                        if timeline:
                            timeline.game_process_timeout(
                                process_name=game_config.process_id or game_config.name,
                                timeout_seconds=process_wait_timeout
                            )

                        logger.info("Process not detected - checking for Steam dialogs...")
                        if timeline:
                            timeline.steam_dialog_checking()

                        # Run steam dialog check
                        dialog_result = self._check_steam_dialogs(
                            network=network,
                            device=device,
                            run=run,
                            game_config=game_config,
                            account_pool=account_pool,
                            timeline=timeline,
                            enabled=True
                        )

                        if dialog_result == "retry_with_alt_account":
                            logger.warning("Steam dialog detected (account busy) - will retry with alternative")
                            raise RuntimeError("STEAM_ACCOUNT_CONFLICT")
                        elif dialog_result is None:
                            # Dialog might have been dismissed - but launch already failed
                            logger.info("No Steam dialog found or dismissed, but launch already timed out")

                    # Check if it's a 404 error (SUT service issue)
                    if "404" in error_str or "NOT FOUND" in error_str:
                        error_msg = f"SUT service error: /launch endpoint not found on {device.ip}:{device.port}. Please ensure gemma_sut_service.py is running on the SUT."
                    elif "Connection" in error_str or "timeout" in error_str.lower():
                        # BUG-004 fix: Try to recover SUT connection before failing
                        logger.warning(f"SUT connection issue detected, attempting recovery...")
                        if timeline:
                            timeline.warning("SUT connection issue, attempting recovery...")

                        # Wait for SUT to recover (e.g., after game crash)
                        if self._verify_sut_connection(device, timeline, max_retries=3, retry_delay=15):
                            # SUT recovered - fail this iteration gracefully so campaign can continue
                            error_msg = f"Game launch failed but SUT recovered. Connection was temporarily lost."
                            if timeline:
                                timeline.warning(error_msg)
                            logger.warning(error_msg)
                            # Mark iteration as failed in storage
                            if self.storage:
                                self.storage.complete_iteration(run.run_id, iteration_num, success=False, error_message=error_msg)
                            return (False, original_resolution, resolution_changed)
                        else:
                            # SUT still unreachable after retries
                            error_msg = f"Connection error: Cannot reach SUT at {device.ip}:{device.port} after recovery attempts."

                    if timeline:
                        timeline.error(f"Game launch failed: {error_msg}")
                    raise RuntimeError(error_msg)

                # ===== Wait for actual game process (if launcher is separate) =====
                game_process_name = game_config.game_process
                if game_process_name and game_process_name != game_config.process_id:
                    # Game has a separate launcher - wait for the actual game process
                    if timeline:
                        timeline.info(f"Waiting for game process: {game_process_name}")
                    logger.info(f"Launcher started, waiting for actual game process: {game_process_name}")

                    game_process_timeout = 120  # 2 minutes to wait for game process
                    game_process_found = False
                    start_wait = time.time()

                    while time.time() - start_wait < game_process_timeout:
                        # Check if game process is running via SUT's /check_process endpoint
                        try:
                            check_resp = network.session.post(
                                f"{network.base_url}/check_process",
                                json={"process_name": game_process_name},
                                timeout=5
                            )
                            if check_resp.status_code == 200:
                                check_result = check_resp.json()
                                if check_result.get("running"):
                                    game_process_found = True
                                    detected_name = check_result.get("name", game_process_name)
                                    detected_pid = check_result.get("pid", "N/A")
                                    logger.info(f"Game process '{detected_name}' detected (PID: {detected_pid})!")
                                    if timeline:
                                        timeline.info(f"Game process detected: {detected_name} (PID: {detected_pid})")
                                    break
                        except Exception as e:
                            logger.debug(f"Process check failed: {e}")

                        time.sleep(5)  # Check every 5 seconds

                    if not game_process_found:
                        logger.warning(f"Game process '{game_process_name}' not detected within {game_process_timeout}s, continuing anyway")
                        if timeline:
                            timeline.warning(f"Game process '{game_process_name}' not detected, continuing with automation")

                # ===== Game Initialization Wait =====
                init_wait = startup_wait if startup_wait else 30  # Use config value or default 30s
                if timeline:
                    timeline.game_initializing(init_wait)
                logger.info(f"Game process detected, waiting {init_wait}s for full game initialization...")
                time.sleep(init_wait)
                if timeline:
                    timeline.game_ready()

            # Check if run was stopped during initialization
            if run.status != RunStatus.RUNNING:
                if timeline:
                    timeline.warning("Run stopped by user during initialization")
                # Mark iteration as failed in storage
                if self.storage:
                    self.storage.complete_iteration(run.run_id, iteration_num, success=False, error_message="Run stopped")
                return (False, original_resolution, resolution_changed)

            # ===== Execute Automation =====
            if timeline:
                timeline.info(f"Starting automation ({automation.config.get('steps', {}).__len__()} steps)")
            logger.info(f"Starting automation execution for iteration {iteration_num}")
            success = automation.run()

            logger.info(f"Iteration {iteration_num} completed with result: {success}")
            if timeline:
                if success:
                    timeline.info("Automation completed successfully")
                else:
                    timeline.error("Automation failed")

            # Mark iteration as completed in storage
            if self.storage:
                self.storage.complete_iteration(run.run_id, iteration_num, success=success)

            return (success, original_resolution, resolution_changed)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in iteration {iteration_num}: {error_msg}", exc_info=True)
            # Mark iteration as failed in storage
            if self.storage:
                self.storage.complete_iteration(run.run_id, iteration_num, success=False, error_message=error_msg)
            return (False, original_resolution, resolution_changed)
        finally:
            # Comprehensive cleanup to prevent hanging resources
            try:
                logger.debug(f"Cleaning up resources for iteration {iteration_num}")
                
                # Cleanup blackbox logging
                self._cleanup_blackbox_logging()

                # Close network connection
                if 'network' in locals():
                    network.close()

                # Close vision model/omniparser client
                if 'vision_model' in locals():
                    try:
                        vision_model.close()
                    except:
                        pass
                        
                # Clean up automation object
                if 'automation' in locals():
                    try:
                        # Set stop event to interrupt any running operations
                        if hasattr(automation, 'stop_event'):
                            automation.stop_event.set()
                    except:
                        pass

                # NOTE: Resolution is restored at the RUN level (after all iterations),
                # not here per-iteration. See the iteration loop in _execute_automation_run.

                # Force garbage collection
                import gc
                gc.collect()

                logger.debug(f"Cleanup completed for iteration {iteration_num}")
                
            except Exception as cleanup_error:
                logger.warning(f"Error during cleanup: {cleanup_error}")
                pass
    
    def _create_run_directory(self, run: AutomationRun, iteration_num: int) -> str:
        """Create directory structure for run outputs"""
        # Use storage path if available (new persistent structure)
        if self.storage:
            iter_dir = self.storage.get_iteration_dir(run.run_id, iteration_num)
            if iter_dir and iter_dir.exists():
                # Create screenshots subdirectory if not exists
                (iter_dir / "screenshots").mkdir(exist_ok=True)
                logger.info(f"Using storage iteration directory: {iter_dir}")
                return str(iter_dir)

        # Fallback to old directory structure
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create base logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Create game-specific directory
        game_dir = logs_dir / run.game_name.replace(" ", "_")
        game_dir.mkdir(exist_ok=True)

        # Create run-specific directory
        run_dir = game_dir / f"run_{run.run_id}_{timestamp}_iter{iteration_num}"
        run_dir.mkdir(exist_ok=True)

        # Create subdirectories
        (run_dir / "screenshots").mkdir(exist_ok=True)
        (run_dir / "blackbox").mkdir(exist_ok=True)

        return str(run_dir)

    def _setup_blackbox_logging(self, run_dir: str, game_name: str, run_id: str, iteration_num: int):
        """Setup blackbox logging to capture all console output for this run"""
        import logging
        from pathlib import Path

        run_dir_path = Path(run_dir)

        # For new storage structure, blackbox log goes directly in iteration folder
        # For old structure, it goes in blackbox subfolder
        if (run_dir_path / "blackbox").exists():
            blackbox_dir = run_dir_path / "blackbox"
            blackbox_file = blackbox_dir / f"console_output_iter{iteration_num}.log"
        else:
            # New storage structure - log file in iteration folder root
            # Name format: blackbox_perf-run{N}_{game}.log
            safe_game_name = game_name.replace(" ", "-")
            blackbox_file = run_dir_path / f"blackbox_perf-run{iteration_num}_{safe_game_name}.log"

        # Ensure parent directory exists
        blackbox_file.parent.mkdir(parents=True, exist_ok=True)

        # Create a file handler for blackbox logging
        blackbox_handler = logging.FileHandler(str(blackbox_file), mode='w', encoding='utf-8')
        blackbox_handler.setLevel(logging.DEBUG)

        # Format for blackbox logging (includes everything)
        blackbox_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        blackbox_handler.setFormatter(blackbox_formatter)

        # Add handler to root logger to capture all output
        root_logger = logging.getLogger()
        root_logger.addHandler(blackbox_handler)

        # Store handler reference for cleanup
        if not hasattr(self, '_blackbox_handlers'):
            self._blackbox_handlers = []
        self._blackbox_handlers.append(blackbox_handler)

        # Store the log file path for later retrieval
        self._current_blackbox_file = str(blackbox_file)

        logger.info(f"Blackbox logging initialized: {blackbox_file}")
        logger.info(f"Game: {game_name}, Run: {run_id}, Iteration: {iteration_num}")

    def _cleanup_blackbox_logging(self):
        """Clean up blackbox logging handlers"""
        if hasattr(self, '_blackbox_handlers'):
            root_logger = logging.getLogger()
            for handler in self._blackbox_handlers:
                root_logger.removeHandler(handler)
                handler.close()
            self._blackbox_handlers.clear()

    def _check_steam_dialogs(
        self,
        network,
        device,
        run: 'AutomationRun',
        game_config,
        account_pool,
        timeline=None,
        enabled: bool = True
    ) -> Optional[str]:
        """
        Check for Steam popup dialogs after game launch and handle them.

        Uses OmniParser to detect dialogs like:
        - "Account in use on another computer" (conflict)
        - "Graphics API selection" (DX11/DX12/Vulkan)
        - EULA agreements
        - Cloud sync conflicts

        Args:
            network: NetworkManager instance
            device: Device info with IP
            run: Current automation run
            game_config: GameConfig object
            account_pool: Steam account pool for handling conflicts
            timeline: TimelineManager for logging
            enabled: Whether to run the check (default True)

        Returns:
            None if no dialog, disabled, or handled successfully
            "retry_with_alt_account" if account conflict detected
            "fail" if dialog detected but cannot be handled
        """
        if not enabled:
            logger.debug("Steam dialog check disabled for this run")
            return None

        try:
            sut_base_url = f"http://{device.ip}:{device.port}"
            queue_service_url = "http://localhost:9000"  # Queue service for OmniParser

            # Load steam dialogs config
            if not STEAM_DIALOGS_CONFIG.exists():
                logger.warning(f"Steam dialogs config not found: {STEAM_DIALOGS_CONFIG}")
                return None

            with open(STEAM_DIALOGS_CONFIG, 'r', encoding='utf-8') as f:
                dialogs_config = yaml.safe_load(f)

            settings = dialogs_config.get('settings', {})
            dialogs = sorted(
                dialogs_config.get('dialogs', []),
                key=lambda d: d.get('priority', 99)
            )

            if not dialogs:
                return None

            # Get screen resolution from SUT
            try:
                screen_resp = network.session.get(f"{sut_base_url}/system_info", timeout=5)
                if screen_resp.status_code == 200:
                    system_info = screen_resp.json()
                    screen_width = system_info.get('screen', {}).get('width', 1920)
                    screen_height = system_info.get('screen', {}).get('height', 1080)
                else:
                    screen_width, screen_height = 1920, 1080
            except Exception:
                screen_width, screen_height = 1920, 1080

            if timeline:
                timeline.steam_dialog_checking()

            # Wait for dialog to appear
            initial_wait = settings.get('initial_wait', 3)
            time.sleep(initial_wait)

            max_attempts = settings.get('check_attempts', 3)
            check_interval = settings.get('check_interval', 2)
            omniparser_timeout = settings.get('omniparser_timeout', 60)

            for attempt in range(max_attempts):
                logger.debug(f"Steam dialog check attempt {attempt + 1}/{max_attempts}")

                # Focus Steam window before taking screenshot
                try:
                    focus_resp = requests.post(
                        f"{sut_base_url}/focus",
                        json={"process_name": "steam"},
                        timeout=5
                    )
                    if focus_resp.status_code == 200:
                        logger.debug("Steam window focused")
                    else:
                        logger.debug(f"Could not focus Steam: {focus_resp.status_code}")
                except Exception as e:
                    logger.debug(f"Focus Steam failed (may not be running): {e}")

                time.sleep(0.5)  # Brief pause after focus

                # Get screenshot from SUT
                try:
                    screenshot_resp = requests.get(f"{sut_base_url}/screenshot", timeout=10)
                    if screenshot_resp.status_code != 200:
                        logger.warning(f"Failed to get screenshot: {screenshot_resp.status_code}")
                        continue
                    screenshot_bytes = screenshot_resp.content
                except Exception as e:
                    logger.warning(f"Screenshot failed: {e}")
                    continue

                # Parse with OmniParser via queue service
                try:
                    img_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                    parse_resp = requests.post(
                        f"{queue_service_url}/parse/",
                        json={"base64_image": img_base64},
                        timeout=omniparser_timeout
                    )
                    if parse_resp.status_code != 200:
                        logger.warning(f"OmniParser failed: {parse_resp.status_code}")
                        continue
                    parse_result = parse_resp.json()
                except Exception as e:
                    logger.warning(f"OmniParser error: {e}")
                    continue

                # Extract text from parsed content
                content_list = parse_result.get('parsed_content_list', [])
                parsed_text = " ".join(
                    item.get('content', '') if isinstance(item, dict) else str(item)
                    for item in content_list
                ).lower()

                # Check each dialog pattern
                for dialog_cfg in dialogs:
                    detection = dialog_cfg.get('detection', {})
                    keywords = detection.get('keywords', [])
                    require_all = detection.get('require_all', False)

                    if require_all:
                        matched = keywords if all(kw.lower() in parsed_text for kw in keywords) else []
                    else:
                        matched = [kw for kw in keywords if kw.lower() in parsed_text]

                    if matched:
                        dialog_name = dialog_cfg.get('name', dialog_cfg['id'])
                        handler = dialog_cfg.get('handler', 'continue')
                        logger.info(f"Steam dialog detected: {dialog_name} (matched: {matched})")

                        if timeline:
                            timeline.steam_dialog_detected(dialog_name, handler)

                        # Find and click button (prefer exact matches)
                        action = dialog_cfg.get('action', {})
                        button_text = action.get('button_text', '')
                        alternatives = action.get('alternatives', [])
                        all_buttons = [button_text] + alternatives

                        # Two-pass: first exact match, then partial
                        button_coords = None
                        for exact_match in [True, False]:
                            if button_coords:
                                break
                            for item in content_list:
                                if isinstance(item, dict):
                                    content_str = item.get('content', '').lower().strip()
                                    bbox = item.get('bbox', [])
                                    for btn in all_buttons:
                                        btn_lower = btn.lower().strip()
                                        if exact_match:
                                            # Exact match only
                                            is_match = content_str == btn_lower
                                        else:
                                            # Partial match - but content must START with button text
                                            # Avoids "X CANCEL" matching "cancel"
                                            is_match = content_str.startswith(btn_lower)
                                        if is_match and bbox and len(bbox) >= 4:
                                            x = int((bbox[0] + bbox[2]) / 2 * screen_width)
                                            y = int((bbox[1] + bbox[3]) / 2 * screen_height)
                                            button_coords = (x, y)
                                            logger.debug(f"Found button '{btn}' (exact={exact_match}) at ({x}, {y})")
                                            break
                                    if button_coords:
                                        break

                        # Click the button
                        click_success = False
                        if button_coords:
                            try:
                                click_resp = requests.post(
                                    f"{sut_base_url}/action",
                                    json={"type": "click", "x": button_coords[0], "y": button_coords[1]},
                                    timeout=10
                                )
                                if click_resp.status_code == 200:
                                    logger.info(f"Clicked '{button_text}' at {button_coords}")
                                    click_success = True
                                time.sleep(0.5)
                            except Exception as e:
                                logger.warning(f"Click failed: {e}")
                        else:
                            # Try escape as fallback
                            try:
                                requests.post(
                                    f"{sut_base_url}/action",
                                    json={"type": "key", "key": "escape"},
                                    timeout=10
                                )
                                click_success = True
                                time.sleep(0.5)
                            except Exception:
                                pass

                        # Return based on handler
                        if handler == "try_alternative_account":
                            current_account = getattr(run, '_current_steam_username', None)
                            if timeline:
                                timeline.steam_account_busy(current_account or "unknown", game_config.name)
                            if account_pool and current_account:
                                account_pool.mark_account_externally_busy(
                                    run.sut_ip, current_account, game_config.name
                                )
                            return "retry_with_alt_account"
                        elif handler == "fail_run":
                            return "fail"
                        else:  # "continue", "retry_once", etc
                            if timeline:
                                timeline.steam_dialog_dismissed(dialog_name)
                            return None

                if attempt < max_attempts - 1:
                    time.sleep(check_interval)

            logger.debug("No Steam dialog detected")
            if timeline:
                timeline.steam_check_passed()
            return None

        except Exception as e:
            logger.warning(f"Error checking Steam dialogs: {e}")
            return None

    def _verify_sut_connection(self, device, timeline: TimelineManager = None, max_retries: int = 3, retry_delay: int = 10) -> bool:
        """
        Verify SUT is reachable and wait for recovery if not.

        This helps recover from BUG-004 where SUT becomes temporarily unreachable
        after a game crash or failed launch.

        Args:
            device: Device object with ip and port
            timeline: TimelineManager for event logging
            max_retries: Maximum number of retry attempts
            retry_delay: Seconds to wait between retries

        Returns:
            True if SUT is reachable, False after all retries exhausted
        """
        for attempt in range(max_retries + 1):
            try:
                response = requests.get(
                    f"http://{device.ip}:{device.port}/status",
                    timeout=10
                )
                if response.status_code == 200:
                    if attempt > 0:
                        logger.info(f"SUT connection recovered after {attempt} retries")
                        if timeline:
                            timeline.info(f"SUT connection recovered after {attempt} retries")
                    return True
            except Exception as e:
                if attempt < max_retries:
                    wait_msg = f"SUT unreachable, waiting {retry_delay}s before retry ({attempt + 1}/{max_retries})..."
                    logger.warning(wait_msg)
                    if timeline:
                        timeline.warning(wait_msg)
                    time.sleep(retry_delay)
                else:
                    logger.error(f"SUT unreachable after {max_retries} retries: {e}")
                    if timeline:
                        timeline.error(f"SUT unreachable after {max_retries} retries")
                    return False
        return False

    def _discover_game_path(self, network, game_config) -> Optional[str]:
        """
        Discover game from SUT's installed games and return Steam App ID or path.

        Priority order:
        1. Match by steam_app_id from YAML config (most reliable)
        2. Match by game name (fallback)
        3. Use YAML config path (last resort)

        Args:
            network: NetworkManager instance
            game_config: GameConfig object

        Returns:
            Steam App ID (preferred) or path to game executable
        """
        # If we have steam_app_id in YAML config, verify it's installed on SUT
        config_steam_app_id = getattr(game_config, 'steam_app_id', None)

        try:
            # Try to get installed games from SUT
            response = network.session.get(
                f"{network.base_url}/installed_games",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                installed_games = data.get("games", [])

                # PRIORITY 1: Match by Steam App ID from YAML config
                if config_steam_app_id:
                    for game in installed_games:
                        sut_app_id = game.get("steam_app_id")
                        if sut_app_id and str(sut_app_id) == str(config_steam_app_id):
                            if game.get("exists", True):
                                logger.info(f"Found game '{game.get('name')}' on SUT via Steam App ID: {config_steam_app_id}")
                                return config_steam_app_id

                    # steam_app_id in config but game not installed on SUT
                    logger.warning(f"Steam App ID {config_steam_app_id} from config not found in SUT's installed games")

                # PRIORITY 2: Match by game name (fallback for configs without steam_app_id)
                game_name_lower = game_config.name.lower()
                for game in installed_games:
                    installed_name = game.get("name", "").lower()
                    steam_app_id = game.get("steam_app_id")
                    install_path = game.get("install_path", "")

                    # Check if game names match (case-insensitive)
                    if game_name_lower in installed_name or installed_name in game_name_lower:
                        if game.get("exists", True):
                            # Prefer Steam App ID - SUT launcher handles it best
                            if steam_app_id:
                                logger.info(f"Discovered game '{game.get('name')}' on SUT with Steam App ID: {steam_app_id}")
                                return steam_app_id

                            # Fallback to install path
                            if install_path:
                                logger.info(f"Discovered game '{game.get('name')}' on SUT at: {install_path}")
                                return install_path

                logger.info(f"Game '{game_config.name}' not found in SUT installed games, using YAML config path")
            else:
                logger.warning(f"Could not get installed games from SUT (status {response.status_code})")

        except Exception as e:
            logger.warning(f"Error discovering game path from SUT: {e}")

        # PRIORITY 3: Use steam_app_id from config even if we couldn't verify on SUT
        # (SUT might not have /installed_games endpoint, but can still launch by app id)
        if config_steam_app_id:
            logger.info(f"Using Steam App ID from YAML config: {config_steam_app_id}")
            return config_steam_app_id

        # PRIORITY 4: Fallback to YAML config path
        if game_config.path:
            logger.info(f"Using YAML config path: {game_config.path}")
            return game_config.path

        return None

    def _get_run_directory(self, run: AutomationRun) -> str:
        """Get the base run directory path"""
        return f"logs/{run.game_name.replace(' ', '_')}/run_{run.run_id}"

    def _sync_preset_to_sut(self, game_config, device, run_quality: str = None, run_resolution: str = None) -> bool:
        """
        Sync game preset to SUT before launching.

        Uses the preset-manager service to push the appropriate preset level
        to the SUT device.

        Args:
            game_config: GameConfig object with game metadata
            device: Device proxy with unique_id

        Returns:
            True if sync successful, False otherwise (non-fatal)
        """
        import requests

        # Use preset_id from YAML if available (preferred, explicit mapping)
        if game_config.preset_id:
            game_short_name = game_config.preset_id
            logger.debug(f"Using preset_id from config: {game_short_name}")
        else:
            # Fallback: derive from game name
            # Convention: "Black Myth Wukong" -> "black-myth-wukong"
            game_short_name = game_config.name.lower().replace(" ", "-").replace(":", "").replace("'", "")

            # Legacy name mappings for games without preset_id in YAML
            name_mappings = {
                "black-myth-wukong": "black-myth-wukong",
                "shadow-of-the-tomb-raider": "shadow-of-tomb-raider",
                "red-dead-redemption-2": "red-dead-redemption-2",
                "cyberpunk2077": "cyberpunk-2077",
                "mirage": "ac-mirage",
                "hitman-3": "hitman-3-dubai",
                "horizon-zerodawn-remastered": "horizon-zero-dawn-remastered",
                "sid-meiers-civilization-vi": "sid-meier-civ-6",
                "ffxiv-dawntrail": "final-fantasy-xiv-dawntrail",
                "tiny-tinas-wonderlands": "tiny-tina-wonderlands",
                "far-cry-6": "far-cry-6",
            }
            game_short_name = name_mappings.get(game_short_name, game_short_name)
            logger.debug(f"Derived preset folder from name: {game_short_name}")

        # Build preset level from run params (priority) or game config preset and resolution
        # New structure uses quality-resolution format: high-1080p, medium-1440p, etc.

        # Priority: run_quality > game_config.preset
        quality = run_quality or getattr(game_config, 'preset', 'high').lower()

        # Priority: run_resolution > game_config.resolution
        resolution = run_resolution or getattr(game_config, 'resolution', '1920x1080')

        # Convert resolution to short format if needed
        res_map = {'1920x1080': '1080p', '2560x1440': '1440p', '3840x2160': '2160p', '1280x720': '720p'}
        # Handle both preset format (e.g., "1080p") and dimensions (e.g., "1920x1080")
        if resolution in ['720p', '1080p', '1440p', '2160p']:
            res_short = resolution
        else:
            res_short = res_map.get(resolution, '1080p')

        preset_level = f"{quality}-{res_short}"
        logger.info(f"Preset level for sync: {preset_level} (quality={quality}, resolution={resolution})")

        # Get device unique ID
        device_unique_id = getattr(device, 'unique_id', None)
        if not device_unique_id:
            logger.warning(f"Device {device.ip} has no unique_id, skipping preset sync")
            return False

        try:
            preset_manager_url = "http://localhost:5002"

            logger.info(f"Syncing preset '{preset_level}' for game '{game_short_name}' to SUT {device_unique_id}")

            response = requests.post(
                f"{preset_manager_url}/api/sync/push",
                json={
                    "game_short_name": game_short_name,
                    "preset_level": preset_level,
                    "sut_unique_ids": [device_unique_id]
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Preset sync successful: {result.get('message', 'OK')}")
                return True
            else:
                logger.warning(f"Preset sync failed (status {response.status_code}): {response.text}")
                return False

        except requests.exceptions.ConnectionError:
            logger.warning(f"Preset-manager not available at {preset_manager_url}, skipping preset sync")
            return False
        except Exception as e:
            logger.warning(f"Error syncing preset: {e}")
            return False
    
    def validate_prerequisites(self, run: AutomationRun) -> tuple[bool, Optional[str]]:
        """Validate that all prerequisites are met for running automation"""
        try:
            # Check game exists
            game_config = self.game_manager.get_game(run.game_name)
            if not game_config:
                return False, f"Game '{run.game_name}' not found"
            
            # Check game YAML file exists
            if not os.path.exists(game_config.yaml_path):
                return False, f"Game configuration file not found: {game_config.yaml_path}"
            
            # Check SUT is available
            device = None
            if self.discovery_client:
                try:
                    suts = self.discovery_client.get_suts_sync()
                    # Find an online SUT with matching IP (prefer online over offline)
                    matching_suts = [s for s in suts if s.get("ip") == run.sut_ip]
                    online_sut = next((s for s in matching_suts if s.get("status") == "online" or s.get("is_online")), None)

                    if online_sut:
                        device = online_sut
                    elif matching_suts:
                        # All matching SUTs are offline
                        return False, f"SUT {run.sut_ip} is not online"
                    else:
                        device = None
                except Exception as e:
                    logger.error(f"Error querying Discovery Service: {e}")
                    return False, f"Failed to query Discovery Service: {str(e)}"
            else:
                device = self.device_registry.get_device_by_ip(run.sut_ip)
                if device and not device.is_online:
                    return False, f"SUT {run.sut_ip} is not online"

            if not device:
                return False, f"SUT {run.sut_ip} not found in device registry"
            
            # Check OmniParser is available
            omniparser_status = self.omniparser_client.get_server_status()
            if omniparser_status.get('status') != 'online':
                logger.warning("OmniParser is not online - automation may fail")
            
            # Check modules directory exists
            if not os.path.exists(self.modules_path):
                return False, f"Automation modules not found at {self.modules_path}"
            
            return True, None
            
        except Exception as e:
            return False, f"Error validating prerequisites: {str(e)}"
    
    def get_estimated_duration(self, game_name: str, iterations: int) -> int:
        """Estimate total duration for a run in seconds"""
        try:
            game_config = self.game_manager.get_game(game_name)
            if not game_config:
                return 300  # Default 5 minutes per iteration
            
            # Use benchmark duration from config + overhead
            base_duration = getattr(game_config, 'benchmark_duration', 120)
            startup_overhead = 60  # Startup, shutdown, etc.
            
            return (base_duration + startup_overhead) * iterations
            
        except Exception:
            return 300 * iterations  # Fallback estimate