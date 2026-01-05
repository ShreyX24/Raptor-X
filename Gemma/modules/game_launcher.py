"""
Game Launcher module for starting games on the SUT.
"""

import logging
import requests
from typing import Dict, Any

from modules.network import NetworkManager

logger = logging.getLogger(__name__)

class GameLauncher:
    """Handles launching games on the SUT."""
    
    def __init__(self, network_manager: NetworkManager):
        """
        Initialize the game launcher.
        
        Args:
            network_manager: NetworkManager instance for communication with SUT
        """
        self.network_manager = network_manager
        logger.info("GameLauncher initialized")
    
    def launch(self, game_path: str, process_id: str = '', startup_wait: int = 15, launch_args: str = None) -> bool:
        """
        Launch a game on the SUT.

        Args:
            game_path: Path to the game executable or Steam app ID on the SUT
            process_id: Optional process name to wait for after launch (e.g., 'Launcher', 'Game')
            startup_wait: Maximum seconds to wait for process to appear (default: 15)
            launch_args: Optional command-line arguments for the game (e.g., "-benchmark test.xml")

        Returns:
            True if the game was successfully launched

        Raises:
            RuntimeError: If the game fails to launch
        """
        import time

        try:
            # Log launch parameters at debug level
            logger.debug(f"Launch request - path: {game_path}, process_id: {process_id}, startup_wait: {startup_wait}, args: {launch_args}")

            # Send launch command to SUT with process tracking metadata
            response = self.network_manager.launch_game(game_path, process_id, startup_wait, launch_args)

            # Log full response at debug level
            logger.debug(f"SUT launch response: {response}")

            # Check response
            status = response.get("status")
            if status == "success":
                # Parse detailed status
                proc_name = response.get("game_process_name", "Unknown")
                proc_pid = response.get("game_process_pid", "N/A")
                fg_confirmed = response.get("foreground_confirmed", False)
                launch_method = response.get("launch_method", "unknown")
                subprocess_pid = response.get("subprocess_pid", "N/A")
                subprocess_status = response.get("subprocess_status", "unknown")

                logger.info(f"Game launched successfully: {game_path}")
                logger.debug(f"  - Subprocess PID: {subprocess_pid} ({subprocess_status})")
                logger.info(f"  - Launch Method: {launch_method}")
                logger.info(f"  - Process Detected: {proc_name} (PID: {proc_pid})")
                logger.info(f"  - Foreground Confirmed: {fg_confirmed}")
                return True
            elif status == "warning":
                # Game process is running but foreground not confirmed
                # Try explicit focus retries before failing (BUG-003 fix)
                warning_msg = response.get("warning", "Unknown warning")
                logger.warning(f"Game launched with warning: {warning_msg}")
                logger.info("Attempting explicit focus retries...")

                # Try to focus the game window explicitly (3 attempts with 5s intervals)
                for attempt in range(3):
                    logger.info(f"Focus retry attempt {attempt + 1}/3...")
                    time.sleep(5)  # Wait for game to settle

                    if self.network_manager.focus_game(minimize_others=True):
                        logger.info(f"Focus succeeded on attempt {attempt + 1}")
                        return True
                    else:
                        logger.warning(f"Focus attempt {attempt + 1} failed")

                # All focus attempts failed
                logger.error(f"Game launch failed after focus retries: {warning_msg}")
                raise RuntimeError(f"Game launch failed: {warning_msg}")
            else:
                error_msg = response.get("error", "Unknown error")
                logger.error(f"Failed to launch game: {error_msg}")
                raise RuntimeError(f"Game launch failed: {error_msg}")

        except requests.exceptions.ReadTimeout as e:
            # Timeout occurred - check if game is actually running
            logger.warning(f"Launch request timed out, checking if game is running...")
            try:
                status = self.network_manager.get_sut_status()
                game_info = status.get("game", {})
                if game_info.get("running") and game_info.get("process_name"):
                    proc_name = game_info.get("process_name")
                    proc_pid = game_info.get("pid")
                    logger.info(f"Game is running despite timeout: {proc_name} (PID: {proc_pid})")
                    logger.info("Proceeding with automation - SUT foreground detection was slow")
                    return True
                else:
                    logger.error(f"Game not running after timeout: {str(e)}")
                    raise RuntimeError(f"Game launch timed out and game is not running")
            except Exception as check_err:
                logger.error(f"Failed to verify game status after timeout: {check_err}")
                raise RuntimeError(f"Game launch error: {str(e)}")
        except Exception as e:
            logger.error(f"Error launching game: {str(e)}")
            raise RuntimeError(f"Game launch error: {str(e)}")
    
    def terminate(self) -> bool:
        """
        Terminate the currently running game on the SUT.
        
        Returns:
            True if the game was successfully terminated
        
        Raises:
            RuntimeError: If the game fails to terminate
        """
        try:
            # Send terminate command to SUT
            response = self.network_manager.send_action({
                "type": "terminate_game"
            })
            
            # Check response
            if response.get("status") == "success":
                logger.info("Game terminated successfully")
                return True
            else:
                error_msg = response.get("error", "Unknown error")
                logger.error(f"Failed to terminate game: {error_msg}")
                raise RuntimeError(f"Game termination failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error terminating game: {str(e)}")
            raise RuntimeError(f"Game termination error: {str(e)}")