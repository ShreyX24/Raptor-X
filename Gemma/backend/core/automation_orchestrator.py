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

    def __init__(self, game_manager, device_registry, omniparser_client, discovery_client=None):
        self.game_manager = game_manager
        self.device_registry = device_registry
        self.omniparser_client = omniparser_client
        self.discovery_client = discovery_client

        # Storage manager reference (set by RunManager)
        self.storage: Optional['RunStorageManager'] = None

        # Import paths for the automation modules
        self.modules_path = os.path.join(os.path.dirname(__file__), '../..', 'modules')

        logger.info("AutomationOrchestrator initialized")

    def set_storage(self, storage: 'RunStorageManager'):
        """Set the storage manager for persistent run storage"""
        self.storage = storage
        logger.info("Storage manager attached to orchestrator")
    
    def execute_run(self, run: AutomationRun) -> tuple[bool, Optional[RunResult], Optional[str]]:
        """
        Execute a single automation run using the existing automation engine

        Returns:
            (success, results, error_message)
        """
        logger.info(f"Starting execution of {run.game_name} on SUT {run.sut_ip}")

        # Create run directory early for timeline storage
        base_run_dir = self._get_run_directory(run)
        os.makedirs(base_run_dir, exist_ok=True)

        # Create timeline manager for comprehensive run tracking
        timeline = TimelineManager(run.run_id, base_run_dir)
        timeline.run_started(run.game_name, run.sut_ip, run.iterations)

        # Store timeline reference on run for API access
        run.timeline = timeline

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

            for iteration in range(run.iterations):
                logger.info(f"Starting iteration {iteration + 1}/{run.iterations} for run {run.run_id}")
                timeline.iteration_started(iteration + 1, run.iterations)
                
                # Check if run was stopped
                if run.status != RunStatus.RUNNING:
                    logger.info(f"Run {run.run_id} was stopped during iteration {iteration + 1}")
                    break
                
                try:
                    # Execute single iteration (pass timeline for detailed events)
                    iteration_success = self._execute_single_iteration(
                        run, game_config, device, iteration + 1, timeline
                    )

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
            if overall_success:
                timeline.run_completed(successful_runs, total_runs)
            else:
                timeline.run_failed(f"All {total_runs} iterations failed")

            return overall_success, results, None

        except Exception as e:
            error_msg = f"Critical error in run execution: {str(e)}"
            logger.error(error_msg, exc_info=True)
            timeline.run_failed(error_msg)
            return False, None, error_msg

        finally:
            # Release Steam account pair if we acquired one
            if account_acquired:
                account_pool.release_account_pair(run.sut_ip)
                logger.info(f"Released Steam account pair for SUT {run.sut_ip}")

    def _execute_single_iteration(self, run: AutomationRun, game_config, device, iteration_num: int, timeline: TimelineManager = None) -> bool:
        """Execute a single automation iteration"""
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
            # If an account pair was acquired, check if we need to switch accounts
            account_pool = get_account_pool()
            if account_pool.has_allocation(run.sut_ip):
                credentials = account_pool.get_account_for_game(run.sut_ip, run.game_name)
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
                                timeline.warning(f"Steam: Account '{username}' is in use on another device!")
                            logger.warning(f"Steam account '{username}' is in use on another device")

                            # Mark this account as externally busy
                            account_pool.mark_account_externally_busy(run.sut_ip, username, run.game_name)

                            # Try to get an alternative account
                            if timeline:
                                timeline.info("Checking for alternative Steam account...")
                            logger.info(f"Looking for alternative Steam account for SUT {run.sut_ip}")

                            alternative = account_pool.try_alternative_account(run.sut_ip, run.game_name)

                            if alternative:
                                alt_username, alt_password = alternative
                                if timeline:
                                    timeline.info(f"Steam: Trying alternative account '{alt_username}'")
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
                                    timeline.error("No alternative Steam accounts available!")
                                    timeline.error("All configured account pairs are either allocated or in use elsewhere")
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
                                return False
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
                            return False
                else:
                    logger.debug(f"No credentials returned for SUT {run.sut_ip}, using existing Steam session")

            # Create a stop event for this iteration
            stop_event = threading.Event()

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
            preset_result = self._sync_preset_to_sut(game_config, device)
            if timeline:
                if preset_result:
                    timeline.preset_synced(game_config.name)
                else:
                    timeline.preset_skipped("No preset configured or sync failed")

            # ===== Resolution Switching =====
            # Check if game config has a target resolution different from current
            resolution_changed = False
            target_resolution = getattr(game_config, 'resolution', None)
            if target_resolution:
                # Parse resolution string like "1920x1080"
                try:
                    target_width, target_height = map(int, target_resolution.lower().split('x'))

                    # Only change if different from current
                    if target_width != screen_width or target_height != screen_height:
                        if timeline:
                            timeline.info(f"Changing resolution from {screen_width}x{screen_height} to {target_width}x{target_height}")
                        logger.info(f"Target resolution {target_width}x{target_height} differs from current {screen_width}x{screen_height}")

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

                                # Wait for display to settle
                                time.sleep(2)
                            else:
                                if timeline:
                                    timeline.warning(f"Failed to change resolution to {target_width}x{target_height}")
                                logger.warning(f"Failed to change resolution to {target_width}x{target_height}")
                        else:
                            if timeline:
                                timeline.warning(f"Resolution {target_width}x{target_height} not supported by SUT")
                            logger.warning(f"Resolution {target_width}x{target_height} not supported by SUT")
                except ValueError:
                    logger.warning(f"Invalid resolution format in game config: {target_resolution}")

            # Discover game path from SUT or use YAML config as fallback
            game_path = self._discover_game_path(network, game_config)

            if game_path:
                # ===== Game Launch =====
                if timeline:
                    timeline.game_launching(game_config.name, game_path)
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
                        timeline.game_launched(game_config.name)

                    # ===== Check for Steam Dialogs (Optional) =====
                    # Steam may show popups like "account in use" or "graphics API selection"
                    # after game launch. We detect and handle them via OmniParser.
                    # Can be disabled per-game via steam_dialog_check: false in game YAML
                    steam_check_enabled = game_config.metadata.get('steam_dialog_check', True) if hasattr(game_config, 'metadata') else True
                    steam_dialog_result = self._check_steam_dialogs(
                        network=network,
                        device=device,
                        run=run,
                        game_config=game_config,
                        account_pool=account_pool,
                        timeline=timeline,
                        enabled=steam_check_enabled
                    )
                    if steam_dialog_result == "retry_with_alt_account":
                        # Account conflict - need to retry with different account
                        logger.warning("Steam account conflict - will retry with alternative account")
                        if timeline:
                            timeline.warning("Steam account conflict detected, trying alternative account")
                        raise RuntimeError("STEAM_ACCOUNT_CONFLICT")
                    elif steam_dialog_result == "fail":
                        # Dialog detected but cannot be handled
                        raise RuntimeError("Steam dialog could not be handled")

                except Exception as e:
                    error_msg = f"Failed to launch game '{game_config.name}': {str(e)}"
                    logger.error(error_msg)

                    # Check if it's a 404 error (SUT service issue)
                    if "404" in str(e) or "NOT FOUND" in str(e):
                        error_msg = f"SUT service error: /launch endpoint not found on {device.ip}:{device.port}. Please ensure gemma_sut_service.py is running on the SUT."
                    elif "Connection" in str(e) or "timeout" in str(e).lower():
                        error_msg = f"Connection error: Cannot reach SUT at {device.ip}:{device.port}. Please check if the SUT service is running."

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
                return False

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

            return success

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in iteration {iteration_num}: {error_msg}", exc_info=True)
            # Mark iteration as failed in storage
            if self.storage:
                self.storage.complete_iteration(run.run_id, iteration_num, success=False, error_message=error_msg)
            return False
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

                # Restore resolution if we changed it
                if 'resolution_changed' in locals() and resolution_changed and 'network' in locals():
                    try:
                        logger.info("Restoring original SUT resolution...")
                        network.restore_resolution()
                    except Exception as res_err:
                        logger.warning(f"Failed to restore resolution: {res_err}")

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
                timeline.info("Checking for Steam dialogs...")

            # Wait for dialog to appear
            initial_wait = settings.get('initial_wait', 3)
            time.sleep(initial_wait)

            max_attempts = settings.get('check_attempts', 3)
            check_interval = settings.get('check_interval', 2)
            omniparser_timeout = settings.get('omniparser_timeout', 60)

            for attempt in range(max_attempts):
                logger.debug(f"Steam dialog check attempt {attempt + 1}/{max_attempts}")

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
                            timeline.warning(f"Steam dialog detected: {dialog_name}")

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
                        if button_coords:
                            try:
                                click_resp = requests.post(
                                    f"{sut_base_url}/action",
                                    json={"type": "click", "x": button_coords[0], "y": button_coords[1]},
                                    timeout=10
                                )
                                if click_resp.status_code == 200:
                                    logger.info(f"Clicked '{button_text}' at {button_coords}")
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
                                time.sleep(0.5)
                            except Exception:
                                pass

                        # Return based on handler
                        if handler == "try_alternative_account":
                            if account_pool:
                                current_account = getattr(run, '_current_steam_username', None)
                                if current_account:
                                    account_pool.mark_account_externally_busy(
                                        run.sut_ip, current_account, game_config.name
                                    )
                            return "retry_with_alt_account"
                        elif handler == "fail_run":
                            return "fail"
                        else:  # "continue", "retry_once", etc
                            return None

                if attempt < max_attempts - 1:
                    time.sleep(check_interval)

            logger.debug("No Steam dialog detected")
            return None

        except Exception as e:
            logger.warning(f"Error checking Steam dialogs: {e}")
            return None

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

    def _sync_preset_to_sut(self, game_config, device) -> bool:
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

        # Build preset level from game config preset and resolution
        # New structure uses quality-resolution format: high-1080p, medium-1440p, etc.
        quality = getattr(game_config, 'preset', 'high').lower()
        resolution = getattr(game_config, 'resolution', '1920x1080')
        # Convert resolution like "1920x1080" to "1080p"
        res_map = {'1920x1080': '1080p', '2560x1440': '1440p', '3840x2160': '2160p', '1280x720': '720p'}
        res_short = res_map.get(resolution, '1080p')
        preset_level = f"{quality}-{res_short}"

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