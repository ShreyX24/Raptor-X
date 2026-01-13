"""
Update Handler for SUT Client.

Manages update notifications, prompts, and execution.
Updates are pulled from Master via SSH/SCP.
"""
import os
import sys
import subprocess
import threading
import time
import logging
import select
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# Windows-specific imports for taskbar flash
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    FLASHW_STOP = 0
    FLASHW_CAPTION = 1
    FLASHW_TRAY = 2
    FLASHW_ALL = 3
    FLASHW_TIMER = 4
    FLASHW_TIMERNOFG = 12

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("hwnd", wintypes.HWND),
            ("dwFlags", wintypes.DWORD),
            ("uCount", wintypes.UINT),
            ("dwTimeout", wintypes.DWORD),
        ]


class UpdateHandler:
    """
    Handles update notifications and execution for SUT Client.

    Features:
    - Receives update notifications via WebSocket
    - Prompts every hour (if not during automation)
    - Flashes Windows taskbar badge
    - Executes update via SSH/SCP pull from Master
    """

    CHECK_INTERVAL = 3600  # 1 hour between prompts
    PROMPT_TIMEOUT = 60    # 60s to respond before skipping

    def __init__(
        self,
        current_version: str,
        sut_client_path: Optional[Path] = None,
        on_update_available: Optional[Callable[[str, str], None]] = None
    ):
        self.current_version = current_version
        self.sut_client_path = sut_client_path or Path(__file__).parent.parent.parent
        self.on_update_available = on_update_available

        self.available_version: Optional[str] = None
        self.master_ip: Optional[str] = None
        self.ssh_user: str = os.environ.get("RPX_SSH_USER", os.getlogin())
        self.master_rpx_path: str = os.environ.get("RPX_MASTER_PATH", "C:/Code/RPX")

        self._update_available = threading.Event()
        self._automation_running = False
        self._queue_has_pending = False
        self._prompt_timer: Optional[threading.Timer] = None
        self._running = False
        self._last_prompt_time: Optional[datetime] = None

        # Console window handle for flashing
        self._console_hwnd: Optional[int] = None
        if sys.platform == "win32":
            try:
                self._console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            except Exception:
                pass

    def start(self):
        """Start the update handler"""
        self._running = True
        logger.info("Update handler started")

    def stop(self):
        """Stop the update handler"""
        self._running = False
        if self._prompt_timer:
            self._prompt_timer.cancel()
            self._prompt_timer = None
        logger.info("Update handler stopped")

    def set_automation_state(self, running: bool):
        """
        Set automation state.
        Prevents prompts during automation.
        """
        was_running = self._automation_running
        self._automation_running = running

        if was_running and not running:
            # Automation just completed - check if we should prompt
            if self._update_available.is_set():
                logger.info("Automation completed, checking for pending update prompt")
                self._schedule_prompt(delay=1)  # Prompt after 1 second

    def set_queue_state(self, has_pending: bool):
        """
        Set queue state.
        Affects timeout behavior for prompts.
        """
        self._queue_has_pending = has_pending

    def notify_update_available(self, new_version: str, master_ip: str):
        """
        Called when Master broadcasts an update notification.

        Args:
            new_version: New version/commit hash
            master_ip: Master server IP for SSH pull
        """
        logger.info(f"Update notification received: {self.current_version} -> {new_version}")

        self.available_version = new_version
        self.master_ip = master_ip
        self._update_available.set()

        # Flash taskbar to get attention
        self._flash_taskbar()

        # Trigger callback
        if self.on_update_available:
            self.on_update_available(self.current_version, new_version)

        # If not in automation, schedule prompt
        if not self._automation_running:
            self._schedule_prompt(delay=0)

    def _schedule_prompt(self, delay: float = CHECK_INTERVAL):
        """Schedule the next update prompt"""
        if not self._running:
            return

        if self._prompt_timer:
            self._prompt_timer.cancel()

        self._prompt_timer = threading.Timer(delay, self._show_prompt)
        self._prompt_timer.daemon = True
        self._prompt_timer.start()

    def _show_prompt(self):
        """Show update prompt in terminal"""
        if not self._running or self._automation_running:
            return

        if not self._update_available.is_set():
            return

        self._last_prompt_time = datetime.now()

        # Print colored prompt
        print()
        print("\033[93m" + "=" * 64 + "\033[0m")
        print("\033[93m  UPDATE AVAILABLE!\033[0m")
        print(f"\033[93m  Current version: {self.current_version}\033[0m")
        print(f"\033[93m  New version:     {self.available_version}\033[0m")
        print("\033[93m" + "=" * 64 + "\033[0m")
        print()

        if self._queue_has_pending:
            # Prompt with timeout if queue has pending runs
            self._prompt_with_timeout()
        else:
            # Persistent prompt when queue is empty
            print("  To update, run: \033[96msut-client --update\033[0m")
            print()
            # Re-schedule prompt for 1 hour later
            self._schedule_prompt(delay=self.CHECK_INTERVAL)

    def _prompt_with_timeout(self):
        """Show prompt with 60s timeout for queue scenario"""
        print(f"  Update now? (queued runs waiting)")
        print(f"  [Y]es / [N]o / timeout in {self.PROMPT_TIMEOUT}s")
        print()
        print("  Or run manually: \033[96msut-client --update\033[0m")
        print()

        # Note: In a terminal environment, we can't easily do non-blocking input
        # The actual input handling would need to be done differently
        # For now, we'll just show the message and schedule the next check
        self._schedule_prompt(delay=self.PROMPT_TIMEOUT)

    def _flash_taskbar(self):
        """Flash the Windows taskbar icon"""
        if sys.platform != "win32" or not self._console_hwnd:
            return

        try:
            flash_info = FLASHWINFO(
                cbSize=ctypes.sizeof(FLASHWINFO),
                hwnd=self._console_hwnd,
                dwFlags=FLASHW_ALL | FLASHW_TIMERNOFG,
                uCount=5,  # Flash 5 times
                dwTimeout=0  # Use default cursor blink rate
            )
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(flash_info))
            logger.debug("Taskbar flashed for update notification")
        except Exception as e:
            logger.warning(f"Failed to flash taskbar: {e}")

    def execute_update(self, master_ip: Optional[str] = None) -> bool:
        """
        Execute the update by launching ssh_ops in a new terminal.

        This opens a separate terminal window that shows progress,
        handles the update, and restarts the SUT client.

        Args:
            master_ip: Master server IP (uses stored value if not provided)

        Returns:
            True if update was launched successfully
        """
        master_ip = master_ip or self.master_ip
        if not master_ip:
            logger.error("No master IP specified for update")
            print("\033[91mError: No master IP specified. Use --master-ip flag.\033[0m")
            return False

        # Find ssh_ops.py
        ssh_ops_path = Path(__file__).parent / "ssh_ops.py"
        if not ssh_ops_path.exists():
            logger.error(f"ssh_ops.py not found at {ssh_ops_path}")
            print("\033[91mError: ssh_ops.py not found\033[0m")
            return False

        print()
        print("\033[96mLaunching update in new terminal...\033[0m")
        print()

        try:
            if sys.platform == "win32":
                # Launch in new terminal window with title
                cmd = [
                    "cmd", "/c", "start",
                    "RPX Update",  # Window title
                    "python", str(ssh_ops_path),
                    "update",
                    "--master", master_ip,
                    "--user", self.ssh_user,
                ]
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # Linux/Mac - use gnome-terminal or xterm
                cmd = [
                    "python", str(ssh_ops_path),
                    "update",
                    "--master", master_ip,
                    "--user", self.ssh_user,
                ]
                subprocess.Popen(cmd)

            print("\033[92mUpdate terminal opened!\033[0m")
            print("The update will proceed in the new window.")
            print("This client will be restarted automatically when complete.")
            print()

            self._update_available.clear()
            return True

        except Exception as e:
            logger.error(f"Failed to launch update terminal: {e}")
            print(f"\033[91mError launching update: {e}\033[0m")
            return False

    def execute_update_inline(self, master_ip: Optional[str] = None) -> bool:
        """
        Execute the update inline (legacy method for CLI --update flag).

        Args:
            master_ip: Master server IP (uses stored value if not provided)

        Returns:
            True if update succeeded
        """
        master_ip = master_ip or self.master_ip
        if not master_ip:
            logger.error("No master IP specified for update")
            print("\033[91mError: No master IP specified. Use --master-ip flag.\033[0m")
            return False

        print()
        print(f"Updating SUT Client from {self.ssh_user}@{master_ip}...")
        print()

        # Step 1: Test SSH connectivity
        print("  [1/4] Testing SSH connection...")
        if not self._test_ssh_connection(master_ip):
            print("\033[91m  Failed: SSH connection failed\033[0m")
            print(f"  Make sure SSH key is authorized on Master ({master_ip})")
            return False
        print("  \033[92mOK\033[0m")

        # Step 2: Pull sut_client directory via SCP
        print("  [2/4] Pulling updated code...")
        if not self._scp_pull(master_ip):
            print("\033[91m  Failed: SCP transfer failed\033[0m")
            return False
        print("  \033[92mOK\033[0m")

        # Step 3: Reinstall package
        print("  [3/4] Reinstalling package...")
        if not self._reinstall_package():
            print("\033[91m  Failed: pip install failed\033[0m")
            return False
        print("  \033[92mOK\033[0m")

        # Step 4: Done
        print("  [4/4] Update complete!")
        print()
        print("\033[92m" + "=" * 64 + "\033[0m")
        print("\033[92m  UPDATE SUCCESSFUL!\033[0m")
        print("\033[92m  Please restart sut-client to apply changes.\033[0m")
        print("\033[92m" + "=" * 64 + "\033[0m")
        print()

        self._update_available.clear()
        return True

    def _test_ssh_connection(self, master_ip: str) -> bool:
        """Test SSH connectivity to Master"""
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o", "BatchMode=yes",
                    "-o", "ConnectTimeout=10",
                    "-o", "StrictHostKeyChecking=no",
                    f"{self.ssh_user}@{master_ip}",
                    "echo", "OK"
                ],
                capture_output=True,
                text=True,
                timeout=15
            )
            return result.returncode == 0 and "OK" in result.stdout
        except subprocess.TimeoutExpired:
            logger.error("SSH connection timed out")
            return False
        except FileNotFoundError:
            logger.error("SSH not found in PATH")
            print("  Error: 'ssh' command not found. Install OpenSSH client.")
            return False
        except Exception as e:
            logger.error(f"SSH test failed: {e}")
            return False

    def _scp_pull(self, master_ip: str) -> bool:
        """Pull sut_client directory from Master via SCP"""
        try:
            # Source: master's sut_client directory
            source = f"{self.ssh_user}@{master_ip}:{self.master_rpx_path}/sut_client/"

            # Destination: parent of current sut_client
            dest = str(self.sut_client_path.parent)

            logger.info(f"SCP: {source} -> {dest}")

            result = subprocess.run(
                [
                    "scp",
                    "-r",
                    "-o", "StrictHostKeyChecking=no",
                    source,
                    dest
                ],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"SCP failed: {result.stderr}")
                return False

            return True

        except subprocess.TimeoutExpired:
            logger.error("SCP transfer timed out")
            return False
        except FileNotFoundError:
            logger.error("SCP not found in PATH")
            print("  Error: 'scp' command not found. Install OpenSSH client.")
            return False
        except Exception as e:
            logger.error(f"SCP failed: {e}")
            return False

    def _reinstall_package(self) -> bool:
        """Reinstall sut_client package with pip"""
        try:
            result = subprocess.run(
                ["pip", "install", "-e", "."],
                cwd=str(self.sut_client_path),
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                logger.error(f"pip install failed: {result.stderr}")
                return False

            return True

        except subprocess.TimeoutExpired:
            logger.error("pip install timed out")
            return False
        except Exception as e:
            logger.error(f"pip install failed: {e}")
            return False


# Global update handler instance
_update_handler: Optional[UpdateHandler] = None


def get_update_handler() -> Optional[UpdateHandler]:
    """Get the global update handler instance"""
    return _update_handler


def init_update_handler(current_version: str) -> UpdateHandler:
    """Initialize the global update handler"""
    global _update_handler
    _update_handler = UpdateHandler(current_version)
    _update_handler.start()
    return _update_handler
