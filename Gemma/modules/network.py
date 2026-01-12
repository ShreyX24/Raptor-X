"""
Network communication module for ARL-SUT interaction.
Handles all network operations between the development PC and the system under test.
"""

import socket
import json
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class NetworkManager:
    """Manages network communication with the SUT."""
    
    def __init__(self, sut_ip: str, sut_port: int):
        """
        Initialize the network manager.
        
        Args:
            sut_ip: IP address of the system under test
            sut_port: Port number for communication
        """
        self.sut_ip = sut_ip
        self.sut_port = sut_port
        self.base_url = f"http://{sut_ip}:{sut_port}"
        self.session = requests.Session()
        logger.info(f"NetworkManager initialized with SUT at {self.base_url}")
        
        # Verify connection
        try:
            self._check_connection()
        except Exception as e:
            logger.error(f"Failed to connect to SUT: {str(e)}")
            raise
    
    def _check_connection(self) -> bool:
        """
        Check if the SUT is reachable.
        
        Returns:
            True if connection is successful
        
        Raises:
            ConnectionError: If SUT is not reachable
        """
        try:
            response = self.session.get(f"{self.base_url}/status", timeout=5)
            response.raise_for_status()
            logger.info("Successfully connected to SUT")
            return True
        except requests.RequestException as e:
            logger.error(f"Connection check failed: {str(e)}")
            raise ConnectionError(f"Cannot connect to SUT at {self.base_url}: {str(e)}")
    
    def get_resolution(self) -> dict:
        """
        Get the current display resolution of the SUT.

        Uses /display/current endpoint for accurate dynamic resolution,
        with fallback to /status endpoint.

        Returns:
            Dictionary with 'width' and 'height' keys
        """
        try:
            # Use /display/current for accurate current resolution
            response = self.session.get(f"{self.base_url}/display/current", timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success" and data.get("resolution"):
                res = data["resolution"]
                logger.info(f"SUT current display resolution: {res.get('width')}x{res.get('height')}")
                return {
                    "width": res.get("width", 1920),
                    "height": res.get("height", 1080)
                }
        except Exception as e:
            logger.warning(f"Failed to get resolution from /display/current: {e}")

        # Fallback to /status endpoint
        try:
            response = self.session.get(f"{self.base_url}/status", timeout=5)
            response.raise_for_status()
            data = response.json()
            return {
                "width": data.get("screen_width", 1920),
                "height": data.get("screen_height", 1080)
            }
        except Exception as e:
            logger.warning(f"Failed to get resolution from SUT, defaulting to 1920x1080: {e}")
            return {"width": 1920, "height": 1080}

    def get_current_steam_user(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently logged-in Steam user on the SUT.

        Returns:
            Dictionary with logged_in, username, user_id, or None if request fails
            Example: {"logged_in": True, "username": "steam_user", "user_id": 123456}
        """
        try:
            response = self.session.get(f"{self.base_url}/steam/current", timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                return {
                    "logged_in": data.get("logged_in", False),
                    "username": data.get("username"),
                    "user_id": data.get("user_id"),
                    "steam_running": data.get("steam_running", False)
                }
            return None
        except Exception as e:
            logger.warning(f"Failed to get current Steam user: {e}")
            return None

    def login_steam(self, username: str, password: str, timeout: int = 180) -> dict:
        """
        Login to Steam via SUT service.

        Args:
            username: Steam username
            password: Steam password
            timeout: Max seconds to wait for login (default 180 for slow connections)

        Returns:
            dict: Result with 'success' bool, 'status' string, and optional 'error_reason'
                  status can be: 'success', 'warning', 'error', 'conflict'
                  error_reason can be: 'conflict' (account in use elsewhere), 'timeout', 'not_found'
        """
        try:
            payload = {"username": username, "password": password, "timeout": timeout}
            logger.info(f"[Steam] Logging in as: {username} (timeout: {timeout}s)")

            # HTTP timeout: login timeout + 20s buffer for network overhead
            http_timeout = timeout + 20
            response = self.session.post(f"{self.base_url}/login_steam", json=payload, timeout=http_timeout)

            result = response.json()
            status = result.get('status', 'unknown')
            message = result.get('message', '')
            user_id = result.get('user_id', '')
            error_reason = result.get('error_reason')

            if status == 'success':
                logger.info(f"[Steam] Login successful: {message}")
                if user_id:
                    logger.info(f"[Steam] User ID: {user_id}")
                return {'success': True, 'status': 'success', 'user_id': user_id}
            elif status == 'warning':
                logger.warning(f"[Steam] Warning: {message}")
                return {'success': True, 'status': 'warning', 'message': message}
            elif status == 'conflict':
                logger.error(f"[Steam] CONFLICT: {message}")
                logger.error(f"[Steam] Account '{username}' is in use on another device!")
                return {'success': False, 'status': 'conflict', 'error_reason': 'conflict', 'message': message}
            else:
                logger.error(f"[Steam] Login failed: {message or result.get('error', 'Unknown error')}")
                return {'success': False, 'status': 'error', 'error_reason': error_reason or 'unknown', 'message': message}

        except Exception as e:
            logger.error(f"[Steam] Request failed: {e}")
            return {'success': False, 'status': 'error', 'error_reason': 'request_failed', 'message': str(e)}

    def send_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send an action command to the SUT.
        
        Args:
            action: Dictionary containing action details
                   Example: {"type": "click", "x": 100, "y": 200}
        
        Returns:
            Response from the SUT as a dictionary
        
        Raises:
            RequestException: If the request fails
        """
        try:
            # Scroll actions with multiple clicks can take longer
            timeout = 30 if action.get("type") == "scroll" else 10
            response = self.session.post(
                f"{self.base_url}/action",
                json=action,
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Action sent: {action}, Response: {result}")
            return result
        except requests.RequestException as e:
            logger.error(f"Failed to send action {action}: {str(e)}")
            raise
    
    def get_screenshot(self) -> bytes:
        """
        Request a screenshot from the SUT.

        Returns:
            Raw screenshot data as bytes

        Raises:
            RequestException: If the request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/screenshot",
                timeout=15
            )
            response.raise_for_status()
            logger.debug("Screenshot retrieved successfully")
            return response.content
        except requests.RequestException as e:
            logger.error(f"Failed to get screenshot: {str(e)}")
            raise

    def focus_game(self, minimize_others: bool = False, retries: int = 2) -> bool:
        """
        Focus the game window on the SUT to ensure it's in foreground.
        Should be called before each automation step to prevent focus loss.

        Args:
            minimize_others: If True, also minimize other windows on SUT
            retries: Number of retry attempts on timeout (default: 2)

        Returns:
            True if focus was successful, False otherwise
        """
        import time

        for attempt in range(retries + 1):
            try:
                # Increased timeout from 5s to 15s for heavy games like RDR2, BMW
                response = self.session.post(
                    f"{self.base_url}/focus",
                    json={"minimize_others": minimize_others},
                    timeout=15
                )
                result = response.json()
                status = result.get("status", "error")

                if status == "success":
                    logger.debug(f"Game window focused: {result.get('message')}")
                    return True
                elif status == "warning":
                    logger.warning(f"Focus warning: {result.get('message')}")
                    return True  # Proceed anyway
                else:
                    logger.warning(f"Could not focus game: {result.get('message')}")
                    return False
            except requests.exceptions.Timeout as e:
                if attempt < retries:
                    logger.warning(f"Focus request timed out (attempt {attempt + 1}/{retries + 1}), retrying...")
                    time.sleep(2)
                else:
                    logger.warning(f"Focus request timed out after {retries + 1} attempts")
                    return False
            except requests.RequestException as e:
                logger.warning(f"Focus request failed (game may not be running): {e}")
                return False

        return False

    def launch_game(self, game_path: str, process_id: str = '', startup_wait: int = 15, launch_args: str = None) -> Dict[str, Any]:
        """
        Request the SUT to launch a game.

        Args:
            game_path: Path to the game executable or Steam app ID on the SUT
            process_id: Optional process name to wait for after launch (e.g., 'Launcher', 'Game')
            startup_wait: Maximum seconds to wait for process to appear (default: 15)
            launch_args: Optional command-line arguments to pass to the game (e.g., "-benchmark test.xml")

        Returns:
            Response from the SUT as a dictionary

        Raises:
            RequestException: If the request fails
        """
        try:
            # Detect if game_path is a Steam App ID (purely numeric)
            is_steam_app_id = game_path.isdigit()

            # Prepare request payload with game metadata
            # Always use force_relaunch to ensure any existing game is killed first
            if is_steam_app_id:
                # Use steam_app_id field for Steam launches
                payload = {
                    "steam_app_id": game_path,
                    "process_id": process_id,
                    "process_name": process_id,  # For force_relaunch to know what to kill
                    "startup_wait": startup_wait,
                    "force_relaunch": True  # Kill existing game before launching
                }
                logger.info(f"Launching via Steam App ID: {game_path}")
            else:
                # Use path field for executable launches (legacy)
                payload = {
                    "path": game_path,
                    "process_id": process_id,
                    "process_name": process_id,  # For force_relaunch to know what to kill
                    "startup_wait": startup_wait,
                    "force_relaunch": True  # Kill existing game before launching
                }
                logger.info(f"Launching via executable path: {game_path}")

            # Add launch_args if provided (used for command-line benchmarks like F1 24)
            if launch_args:
                payload["launch_args"] = launch_args
                logger.info(f"With launch args: {launch_args}")

            logger.debug(f"Sending launch request to {self.base_url}/launch with payload: {payload}")

            # Timeout must be longer than startup_wait (SUT waits for process to appear)
            # Add 60s buffer for process detection retries and response time
            http_timeout = max(120, startup_wait + 60)
            response = self.session.post(
                f"{self.base_url}/launch",
                json=payload,
                timeout=http_timeout
            )
            response.raise_for_status()
            result = response.json()
            
            logger.debug(f"Launch response received: status={result.get('status')}, foreground={result.get('foreground_confirmed')}")
            logger.info(f"Game launch request sent: {game_path}, process_id: {process_id}, startup_wait: {startup_wait}")
            return result
        except requests.RequestException as e:
            logger.error(f"Failed to launch game {game_path}: {str(e)}")
            raise
    
    def get_sut_status(self) -> Dict[str, Any]:
        """Get the current status of the SUT including game state."""
        try:
            response = self.session.get(f"{self.base_url}/status", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get SUT status: {str(e)}")
            raise

    # =========================================================================
    # DISPLAY RESOLUTION MANAGEMENT
    # =========================================================================

    def get_supported_resolutions(self, common_only: bool = False) -> list:
        """
        Get list of supported display resolutions from the SUT.

        Args:
            common_only: If True, only return common gaming resolutions (720p, 1080p, 1440p, 4K)

        Returns:
            List of resolution dicts with width, height, refresh_rate
        """
        try:
            params = {"common_only": "true"} if common_only else {}
            response = self.session.get(
                f"{self.base_url}/display/resolutions",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                return data.get("resolutions", [])
            else:
                logger.warning(f"Failed to get resolutions: {data.get('message')}")
                return []
        except requests.RequestException as e:
            logger.error(f"Failed to get supported resolutions: {e}")
            return []

    def get_current_resolution(self) -> Optional[Dict[str, int]]:
        """
        Get the current display resolution from the SUT.

        Returns:
            Dict with width, height, refresh_rate or None if failed
        """
        try:
            response = self.session.get(
                f"{self.base_url}/display/current",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                return data.get("resolution")
            else:
                logger.warning(f"Failed to get current resolution: {data.get('message')}")
                return None
        except requests.RequestException as e:
            logger.error(f"Failed to get current resolution: {e}")
            return None

    def set_resolution(self, width: int, height: int, refresh_rate: int = None) -> bool:
        """
        Set the display resolution on the SUT.

        Args:
            width: Target width in pixels
            height: Target height in pixels
            refresh_rate: Optional refresh rate (uses highest available if not specified)

        Returns:
            True if resolution change succeeded, False otherwise
        """
        try:
            payload = {"width": width, "height": height}
            if refresh_rate:
                payload["refresh_rate"] = refresh_rate

            logger.info(f"Setting SUT resolution to {width}x{height}" +
                       (f"@{refresh_rate}Hz" if refresh_rate else ""))

            response = self.session.post(
                f"{self.base_url}/display/resolution",
                json=payload,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                logger.info(f"Resolution changed: {data.get('message')}")
                return True
            else:
                logger.error(f"Failed to set resolution: {data.get('message')}")
                return False
        except requests.RequestException as e:
            logger.error(f"Failed to set resolution: {e}")
            return False

    def restore_resolution(self) -> bool:
        """
        Restore the original display resolution on the SUT.

        Call this after automation completes to restore the resolution
        that was active before any changes were made.

        Returns:
            True if restore succeeded, False otherwise
        """
        try:
            logger.info("Restoring original SUT resolution...")

            response = self.session.post(
                f"{self.base_url}/display/restore",
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                logger.info(f"Resolution restored: {data.get('message')}")
                return True
            else:
                logger.warning(f"Resolution restore: {data.get('message')}")
                return data.get("status") != "error"
        except requests.RequestException as e:
            logger.error(f"Failed to restore resolution: {e}")
            return False

    def is_resolution_supported(self, width: int, height: int) -> bool:
        """
        Check if a specific resolution is supported by the SUT.

        Args:
            width: Target width in pixels
            height: Target height in pixels

        Returns:
            True if resolution is supported, False otherwise
        """
        resolutions = self.get_supported_resolutions()
        return any(r.get("width") == width and r.get("height") == height for r in resolutions)

    def kill_process(self, process_name: str) -> Dict[str, Any]:
        """
        Kill a process by name on the SUT.

        Args:
            process_name: Name of the process to kill (e.g., "RDR2.exe")

        Returns:
            Response dict from SUT with 'status', 'killed', 'message'
        """
        try:
            response = self.session.post(
                f"{self.base_url}/kill",
                json={"process_name": process_name},
                timeout=10
            )
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Kill process result for {process_name}: {result}")
                return result
            else:
                logger.warning(f"Kill process failed for {process_name}: {response.status_code} - {response.text}")
                return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            logger.error(f"Error killing process {process_name}: {e}")
            return {"status": "error", "message": str(e)}

    def check_process(self, process_name: str) -> bool:
        """
        Check if a process is running on the SUT.

        Args:
            process_name: Name of the process to check (e.g., "RDR2.exe")

        Returns:
            True if process is running, False otherwise
        """
        try:
            response = self.session.post(
                f"{self.base_url}/check_process",
                json={"process_name": process_name},
                timeout=5
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("running", False)
            return False
        except Exception as e:
            logger.error(f"Error checking process {process_name}: {e}")
            return False

    def close(self):
        """Close the network session."""
        self.session.close()
        logger.info("Network session closed")