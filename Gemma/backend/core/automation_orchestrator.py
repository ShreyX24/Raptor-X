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
from typing import Dict, Any, Optional
from datetime import datetime

# Add the main directory to the path to import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from .run_manager import AutomationRun, RunResult, RunStatus

logger = logging.getLogger(__name__)


class AutomationOrchestrator:
    """Orchestrates automation execution using the existing engine from modules/"""

    def __init__(self, game_manager, device_registry, omniparser_client, discovery_client=None):
        self.game_manager = game_manager
        self.device_registry = device_registry
        self.omniparser_client = omniparser_client
        self.discovery_client = discovery_client

        # Import paths for the automation modules
        self.modules_path = os.path.join(os.path.dirname(__file__), '../..', 'modules')

        logger.info("AutomationOrchestrator initialized")
    
    def execute_run(self, run: AutomationRun) -> tuple[bool, Optional[RunResult], Optional[str]]:
        """
        Execute a single automation run using the existing automation engine
        
        Returns:
            (success, results, error_message)
        """
        logger.info(f"Starting execution of {run.game_name} on SUT {run.sut_ip}")

        try:
            # Reload game configs from disk to pick up any YAML changes
            self.game_manager.reload_configurations()

            # Get game configuration
            game_config = self.game_manager.get_game(run.game_name)
            if not game_config:
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
                        return False, None, f"SUT {run.sut_ip} is not online"
                except Exception as e:
                    logger.error(f"Error querying Discovery Service: {e}")
            else:
                device = self.device_registry.get_device_by_ip(run.sut_ip)
                if device and not device.is_online:
                    return False, None, f"SUT {run.sut_ip} is not online"

            if not device:
                return False, None, f"SUT {run.sut_ip} not found"
            
            # Execute multiple iterations
            successful_runs = 0
            total_runs = run.iterations
            error_logs = []
            
            for iteration in range(run.iterations):
                logger.info(f"Starting iteration {iteration + 1}/{run.iterations} for run {run.run_id}")
                
                # Check if run was stopped
                if run.status != RunStatus.RUNNING:
                    logger.info(f"Run {run.run_id} was stopped during iteration {iteration + 1}")
                    break
                
                try:
                    # Execute single iteration
                    iteration_success = self._execute_single_iteration(
                        run, game_config, device, iteration + 1
                    )
                    
                    if iteration_success:
                        successful_runs += 1
                        logger.info(f"Iteration {iteration + 1} completed successfully")
                    else:
                        error_msg = f"Iteration {iteration + 1} failed"
                        error_logs.append(error_msg)
                        logger.warning(error_msg)
                        
                except FileNotFoundError as e:
                    error_msg = f"Game file not found (iteration {iteration + 1}): {str(e)}"
                    error_logs.append(error_msg)
                    logger.error(error_msg)
                    # For file not found, fail fast - no point retrying other iterations
                    break
                except RuntimeError as e:
                    error_msg = f"Game launch failed (iteration {iteration + 1}): {str(e)}"
                    error_logs.append(error_msg)
                    logger.error(error_msg)
                    # For launch failures, also fail fast
                    break
                except Exception as e:
                    error_msg = f"Unexpected error in iteration {iteration + 1}: {str(e)}"
                    error_logs.append(error_msg)
                    logger.error(error_msg, exc_info=True)
            
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
            
            return overall_success, results, None
            
        except Exception as e:
            error_msg = f"Critical error in run execution: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg
    
    def _execute_single_iteration(self, run: AutomationRun, game_config, device, iteration_num: int) -> bool:
        """Execute a single automation iteration"""
        try:
            # Import automation modules dynamically
            from modules.network import NetworkManager
            from modules.screenshot import ScreenshotManager  
            from modules.omniparser_client import OmniparserClient
            from modules.simple_automation import SimpleAutomation
            from modules.game_launcher import GameLauncher
            
            # Create run directory
            run_dir = self._create_run_directory(run, iteration_num)

            # Setup blackbox logging for this run
            self._setup_blackbox_logging(run_dir, game_config.name, run.run_id, iteration_num)
            
            # Initialize components
            logger.info(f"Connecting to SUT at {device.ip}:{device.port}")
            network = NetworkManager(device.ip, device.port)
            screenshot_mgr = ScreenshotManager(network)
            
            # Get actual screen resolution from SUT
            try:
                screen_width, screen_height = network.get_screen_resolution()
                logger.info(f"Using SUT screen resolution: {screen_width}x{screen_height}")
            except Exception as e:
                logger.warning(f"Failed to get SUT resolution, using default 1920x1080: {e}")
                screen_width, screen_height = 1920, 1080
            
            # Use OmniParser for vision with correct resolution
            # In microservices mode, omniparser_client is QueueServiceClient with queue_url
            # In standalone mode, it's OmniparserClient with api_url
            omniparser_url = getattr(self.omniparser_client, 'queue_url', None) or getattr(self.omniparser_client, 'api_url', 'http://localhost:9000')
            vision_model = OmniparserClient(
                omniparser_url,
                screen_width=screen_width,
                screen_height=screen_height
            )
            game_launcher = GameLauncher(network)
            
            # Create a stop event for this iteration
            stop_event = threading.Event()

            # Initialize SimpleAutomation
            automation = SimpleAutomation(
                config_path=game_config.yaml_path,
                network=network,
                screenshot_mgr=screenshot_mgr,
                vision_model=vision_model,
                stop_event=stop_event,
                run_dir=run_dir,
            )

            # Sync preset to SUT before launching (uses preset-manager service)
            self._sync_preset_to_sut(game_config, device)

            # Discover game path from SUT or use YAML config as fallback
            game_path = self._discover_game_path(network, game_config)

            if game_path:
                logger.info(f"Launching game: {game_path}")

                try:
                    # Pass process_id and startup_wait from game config
                    process_id = game_config.process_id or ''
                    startup_wait = game_config.startup_wait
                    logger.info(f"Launch params - process_id: {process_id}, startup_wait: {startup_wait}s")
                    game_launcher.launch(game_path, process_id=process_id, startup_wait=startup_wait)
                    logger.info(f"Game launched successfully: {game_path}")
                except Exception as e:
                    error_msg = f"Failed to launch game '{game_config.name}': {str(e)}"
                    logger.error(error_msg)

                    # Check if it's a 404 error (SUT service issue)
                    if "404" in str(e) or "NOT FOUND" in str(e):
                        error_msg = f"SUT service error: /launch endpoint not found on {device.ip}:{device.port}. Please ensure gemma_sut_service.py is running on the SUT."
                    elif "Connection" in str(e) or "timeout" in str(e).lower():
                        error_msg = f"Connection error: Cannot reach SUT at {device.ip}:{device.port}. Please check if the SUT service is running."

                    raise RuntimeError(error_msg)

                # Wait for game to fully initialize
                # SUT returns after process detection, game needs more time to load UI
                # Use the startup_wait from game config (e.g., 80s for Cyberpunk, 50s for Wukong)
                init_wait = startup_wait if startup_wait else 30  # Use config value or default 30s
                logger.info(f"Game process detected, waiting {init_wait}s for full game initialization...")
                time.sleep(init_wait)
            
            # Check if run was stopped during initialization
            if run.status != RunStatus.RUNNING:
                return False
            
            # Execute the automation
            logger.info(f"Starting automation execution for iteration {iteration_num}")
            success = automation.run()
            
            logger.info(f"Iteration {iteration_num} completed with result: {success}")
            return success
            
        except Exception as e:
            logger.error(f"Error in iteration {iteration_num}: {str(e)}", exc_info=True)
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
                        
                # Force garbage collection
                import gc
                gc.collect()
                
                logger.debug(f"Cleanup completed for iteration {iteration_num}")
                
            except Exception as cleanup_error:
                logger.warning(f"Error during cleanup: {cleanup_error}")
                pass
    
    def _create_run_directory(self, run: AutomationRun, iteration_num: int) -> str:
        """Create directory structure for run outputs"""
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

        # Create blackbox log file
        blackbox_dir = Path(run_dir) / "blackbox"
        blackbox_file = blackbox_dir / f"console_output_iter{iteration_num}.log"

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

        # Default preset level (could be made configurable per game)
        preset_level = "ppg-high-1080p"

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