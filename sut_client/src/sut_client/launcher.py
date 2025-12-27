"""
Game Launcher Module
Handles game launching via Steam protocol and direct executable.

Ported from KATANA Gemma v0.2
Author: SATYAJIT BHUYAN (satyajit.bhuyan@intel.com)
"""

import os
import re
import time
import subprocess
import threading
import logging
from typing import Dict, Any, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import SUTSettings

import psutil

from .window import (
    wait_for_window_ready_pywinauto,
    ensure_window_foreground_v2,
    ensure_window_foreground,
    is_pywinauto_available,
    minimize_other_windows
)
from .steam import get_steam_install_path

logger = logging.getLogger(__name__)

# =============================================================================
# Global State
# =============================================================================

# Current game process tracking
game_process: Optional[subprocess.Popen] = None
game_lock = threading.Lock()
current_game_process_name: Optional[str] = None

# Launch cancellation support
launch_cancel_flag = threading.Event()


# =============================================================================
# Process Detection
# =============================================================================

def find_process_by_name(process_name: str, exact_only: bool = False) -> Optional[psutil.Process]:
    """
    Find a running process by its name.

    Args:
        process_name: Name of process to find (e.g., "RDR2.exe" or "b1")
        exact_only: If True, only exact matches are returned.
                    If False (default), substring matches are also allowed.

    Returns:
        psutil.Process or None
    """
    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_name = proc.info['name']
                proc_exe = os.path.basename(proc.info['exe']) if proc.info['exe'] else None

                if exact_only:
                    # EXACT match only (case-insensitive)
                    if (proc_name and proc_name.lower() == process_name.lower()) or \
                       (proc_exe and proc_exe.lower() == process_name.lower()):
                        logger.info(f"[EXACT] Found process: {proc_name} (PID: {proc.info['pid']})")
                        return psutil.Process(proc.info['pid'])
                else:
                    # Partial/substring match (like old gemma_client_0.2.py)
                    if (proc_name and process_name.lower() in proc_name.lower()) or \
                       (proc_exe and process_name.lower() in proc_exe.lower()):
                        logger.info(f"[SUBSTRING] Found process: {proc_name} (PID: {proc.info['pid']})")
                        return psutil.Process(proc.info['pid'])

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as e:
        logger.error(f"Error searching for process {process_name}: {str(e)}")
    return None


def terminate_process_by_name(process_name: str) -> bool:
    """Terminate a process by its name."""
    try:
        processes_terminated = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                if (proc.info['name'] and process_name.lower() in proc.info['name'].lower()) or \
                   (proc.info['exe'] and process_name.lower() in os.path.basename(proc.info['exe']).lower()):

                    process = psutil.Process(proc.info['pid'])
                    logger.info(f"Terminating process: {proc.info['name']} (PID: {proc.info['pid']})")

                    process.terminate()
                    try:
                        process.wait(timeout=5)
                        processes_terminated.append(proc.info['name'])
                    except psutil.TimeoutExpired:
                        logger.warning(f"Force killing process: {proc.info['name']}")
                        process.kill()
                        processes_terminated.append(proc.info['name'])

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if processes_terminated:
            logger.info(f"Successfully terminated processes: {processes_terminated}")
            return True
        else:
            logger.info(f"No processes found with name: {process_name}")
            return False

    except Exception as e:
        logger.error(f"Error terminating process {process_name}: {str(e)}")
        return False


# =============================================================================
# Steam Path Resolution
# =============================================================================

def resolve_steam_app_path(app_id: str, target_process_name: str = '') -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve Steam App ID to executable path by parsing manifest files.

    Args:
        app_id: Steam application ID
        target_process_name: Optional target process name to find

    Returns:
        tuple: (executable_path or None, error_message or None)
    """
    steam_path = get_steam_install_path()
    if not steam_path:
        return None, "Steam installation not found in registry"

    logger.info(f"Steam path found: {steam_path}")

    # Library folders config
    vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
    if not os.path.exists(vdf_path):
        libraries = [steam_path]
    else:
        libraries = []
        try:
            with open(vdf_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Regex to find "path" "..." entries
            matches = re.findall(r'"path"\s+"([^"]+)"', content)
            if matches:
                libraries.extend(matches)
                # Unescape double backslashes
                libraries = [lib.replace('\\\\', '\\') for lib in libraries]
            else:
                libraries = [steam_path]
        except Exception as e:
            logger.warning(f"Failed to parse libraryfolders.vdf: {e}")
            libraries = [steam_path]

    logger.info(f"Checking Steam libraries: {libraries}")

    # Search for app manifest
    manifest_file = f"appmanifest_{app_id}.acf"
    found_manifest = None
    game_library = None

    for lib in libraries:
        manifest_path = os.path.join(lib, "steamapps", manifest_file)
        if os.path.exists(manifest_path):
            found_manifest = manifest_path
            game_library = lib
            break

    if not found_manifest:
        return None, f"App ID {app_id} not installed (manifest not found)"

    # Parse manifest for installdir
    install_dir_name = None
    try:
        with open(found_manifest, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'"installdir"\s+"([^"]+)"', content)
        if match:
            install_dir_name = match.group(1)
    except Exception as e:
        return None, f"Failed to parse manifest: {e}"

    if not install_dir_name:
        return None, "Could not find 'installdir' in manifest"

    full_game_path = os.path.join(game_library, "steamapps", "common", install_dir_name)
    logger.info(f"Game folder resolved: {full_game_path}")

    if not os.path.exists(full_game_path):
        return None, f"Game folder does not exist: {full_game_path}"

    # Find executable
    # Strategy 1: Target process name
    if target_process_name:
        exe_path = os.path.join(full_game_path, f"{target_process_name}.exe")
        if os.path.exists(exe_path):
            return exe_path, None

        # Search recursively for target process name
        for root, dirs, files in os.walk(full_game_path):
            if f"{target_process_name}.exe" in files:
                return os.path.join(root, f"{target_process_name}.exe"), None

    # Strategy 2: Folder name matcher
    exe_path = os.path.join(full_game_path, f"{install_dir_name}.exe")
    if os.path.exists(exe_path):
        return exe_path, None

    # Strategy 3: Find largest .exe in the folder
    exe_files = []
    for root, dirs, files in os.walk(full_game_path):
        for file in files:
            if file.lower().endswith(".exe"):
                path = os.path.join(root, file)
                size = os.path.getsize(path)
                exe_files.append((path, size))

    if exe_files:
        exe_files.sort(key=lambda x: x[1], reverse=True)
        best_match = exe_files[0][0]
        logger.info(f"Selected largest executable: {best_match}")
        return best_match, None

    return None, "No executable found in game directory"


# =============================================================================
# Game Launch
# =============================================================================

def cancel_launch():
    """Cancel an ongoing launch operation."""
    global launch_cancel_flag
    logger.info("Launch cancellation requested - setting cancel flag")
    launch_cancel_flag.set()


def launch_game(
    steam_app_id: Optional[str] = None,
    exe_path: Optional[str] = None,
    process_name: Optional[str] = None,
    force_relaunch: bool = False,
    settings: Optional[Any] = None,
    # Legacy parameters for backwards compatibility
    game_path: Optional[str] = None,
    process_id: str = '',
    visible_timeout: int = 120,
    ready_timeout: int = 30,
    retry_count: int = 5,
    retry_interval: int = 10
) -> Dict[str, Any]:
    """
    Launch a game with process tracking and window detection.

    Supports both exe paths and Steam app IDs.

    Args:
        steam_app_id: Steam application ID (e.g., "1234567")
        exe_path: Direct path to executable
        process_name: Expected process name (optional)
        force_relaunch: Kill existing game before launch
        settings: SUTSettings instance for timeouts
        game_path: Legacy param - Path to executable or Steam App ID
        process_id: Legacy param - Expected process name
        visible_timeout: Timeout for window visibility detection
        ready_timeout: Timeout for window ready detection
        retry_count: Number of retries for foreground detection
        retry_interval: Seconds between retries

    Returns:
        dict: Launch result with status, process info, etc.
    """
    global game_process, current_game_process_name, launch_cancel_flag

    # Clear cancel flag at start of new launch
    launch_cancel_flag.clear()

    # Resolve game_path from new-style parameters
    if steam_app_id:
        game_path = steam_app_id
    elif exe_path:
        game_path = exe_path
    # game_path may also be passed directly for backwards compatibility

    # Process name from new-style or legacy
    if process_name:
        process_id = process_name

    # Get timeouts from settings if provided
    if settings:
        visible_timeout = getattr(settings, 'pywinauto_visible_timeout', visible_timeout)
        ready_timeout = getattr(settings, 'pywinauto_ready_timeout', ready_timeout)
        retry_count = getattr(settings, 'launch_retry_count', retry_count)
        retry_interval = getattr(settings, 'launch_retry_interval', retry_interval)

    # Handle force relaunch
    if force_relaunch and current_game_process_name:
        logger.info(f"Force relaunch: terminating existing game {current_game_process_name}")
        terminate_process_by_name(current_game_process_name)
        time.sleep(2)

    # Validate game_path is provided
    if not game_path:
        logger.error("No game path provided")
        return {"status": "error", "error": "Game path is required (steam_app_id or exe_path)"}

    # Convert game_path to string
    game_path = str(game_path)
    is_steam_id = False

    # Check if it's a numeric Steam App ID
    if game_path.isdigit():
        is_steam_id = True
        logger.info(f"Detected Steam App ID: {game_path}")
    elif game_path.startswith('steam://'):
        # Legacy handling, try to extract ID
        match = re.search(r'run/(\d+)', game_path) or re.search(r'rungameid/(\d+)', game_path)
        if match:
            game_path = match.group(1)
            is_steam_id = True
            logger.info(f"Extracted Steam App ID from URL: {game_path}")

    # Resolve Steam App ID to Executable
    steam_app_id = None
    if is_steam_id:
        steam_app_id = game_path
        logger.info(f"Resolving Steam App ID: {game_path}")
        resolved_path, error = resolve_steam_app_path(game_path, process_id)
        if resolved_path:
            logger.info(f"Resolved Steam ID {game_path} to: {resolved_path}")
            game_path = resolved_path
            if not process_id:
                new_process_name = os.path.splitext(os.path.basename(resolved_path))[0]
            else:
                new_process_name = process_id
        else:
            logger.error(f"Failed to resolve Steam ID: {error}")
            return {"status": "error", "error": f"Failed to resolve Steam ID: {error}"}
    else:
        if not os.path.exists(game_path):
            logger.error(f"Game path not found: {game_path}")
            return {"status": "error", "error": "Game executable not found"}
        new_process_name = process_id if process_id else os.path.splitext(os.path.basename(game_path))[0]

    with game_lock:
        # Terminate existing game if running
        if current_game_process_name:
            logger.info(f"Terminating existing game: {current_game_process_name}")
            terminate_process_by_name(current_game_process_name)
            if game_process and game_process.poll() is None:
                try:
                    game_process.terminate()
                    game_process.wait(timeout=2)
                except Exception:
                    pass
            current_game_process_name = None

        # Set the new global process name
        current_game_process_name = new_process_name

        # Launch game
        subprocess_status = "steam_protocol"
        if steam_app_id:
            # Launch via Steam protocol
            steam_url = f"steam://rungameid/{steam_app_id}"
            logger.info(f"Launching game via Steam protocol: {steam_url}")
            os.startfile(steam_url)
            game_process = None
        else:
            # Direct exe launch
            logger.info(f"Launching game directly: {game_path}")
            game_dir = os.path.dirname(game_path)
            try:
                game_process = subprocess.Popen(game_path, cwd=game_dir)
            except Exception as e:
                logger.warning(f"Failed to launch with cwd, trying direct: {e}")
                game_process = subprocess.Popen(game_path)

        # Log launch status
        if game_process:
            logger.info(f"Subprocess started with PID: {game_process.pid}")
        else:
            logger.info("Game launched via Steam protocol (no direct PID)")

        time.sleep(3)  # Initial wait for process spawn

        if game_process:
            subprocess_status = "running" if game_process.poll() is None else "exited"
            logger.info(f"Subprocess status after 3 seconds: {subprocess_status}")

        # Wait for actual game process
        max_wait_time = 60
        actual_process = None
        foreground_confirmed = False

        logger.info(f"Waiting up to {max_wait_time}s for process '{current_game_process_name}' to appear...")

        # Phase 1: Detect Process
        start_wait = time.time()
        cancelled = False
        while time.time() - start_wait < max_wait_time:
            actual_process = find_process_by_name(current_game_process_name)
            if actual_process:
                logger.info(f"Process found: {actual_process.name()} (PID: {actual_process.pid})")
                break

            if launch_cancel_flag.wait(timeout=3):
                logger.info("Launch cancelled during process detection")
                cancelled = True
                break

        if cancelled:
            return {"status": "cancelled", "message": "Launch cancelled by user"}

        if actual_process:
            # Phase 2: Enhanced foreground detection
            logger.info("Starting enhanced foreground detection...")

            window_ready, hwnd, window_title = wait_for_window_ready_pywinauto(
                actual_process.pid,
                process_name=current_game_process_name,
                visible_timeout=visible_timeout,
                ready_timeout=ready_timeout
            )

            if window_ready:
                logger.info("Window is ready, bringing to foreground...")
                foreground_confirmed = ensure_window_foreground_v2(actual_process.pid, timeout=5)
            else:
                logger.warning("pywinauto window detection failed, using legacy method")
                foreground_confirmed = ensure_window_foreground(actual_process.pid, timeout=5)

            # Retry with longer waits for slow-loading games
            if not foreground_confirmed:
                for attempt in range(1, retry_count + 1):
                    logger.warning(f"Foreground attempt failed. Retry {attempt}/{retry_count} in {retry_interval}s...")

                    if launch_cancel_flag.wait(timeout=retry_interval):
                        logger.info("Launch cancelled during retry wait")
                        return {"status": "cancelled", "message": "Launch cancelled by user"}

                    actual_process = find_process_by_name(current_game_process_name)
                    if actual_process:
                        logger.info(f"Retry {attempt}: Process found: {actual_process.name()} (PID: {actual_process.pid})")

                        window_ready, hwnd, _ = wait_for_window_ready_pywinauto(
                            actual_process.pid,
                            visible_timeout=15,
                            ready_timeout=10
                        )

                        foreground_confirmed = ensure_window_foreground_v2(actual_process.pid, timeout=5)
                        if foreground_confirmed:
                            logger.info(f"Retry {attempt}: Successfully brought to foreground!")
                            break
                    else:
                        logger.warning(f"Retry {attempt}: Process '{current_game_process_name}' no longer found")

            response_data = {
                "status": "success" if foreground_confirmed else "warning",
                "subprocess_pid": game_process.pid if game_process else None,
                "subprocess_status": subprocess_status,
                "resolved_path": game_path if is_steam_id else None,
                "launch_method": "steam" if is_steam_id else "direct_exe",
                "game_process_pid": actual_process.pid,
                "game_process_name": actual_process.name(),
                "game_process_status": actual_process.status(),
                "foreground_confirmed": foreground_confirmed,
                "pywinauto_available": is_pywinauto_available(),
                "window_ready_detected": window_ready if 'window_ready' in dir() else False
            }

            if foreground_confirmed:
                logger.info(f"[OK] Launch Complete: {actual_process.name()} is running and in foreground.")
                # Minimize other windows (Steam, etc.) to ensure clean screenshots
                minimized = minimize_other_windows(actual_process.pid)
                response_data["windows_minimized"] = minimized
            else:
                logger.warning(f"[WARN] Launch Warning: Process {actual_process.pid} exists but could not confirm foreground status.")
                response_data["warning"] = "Process launched but window not in foreground (timeout)"

        else:
            logger.error(f"LAUNCH FAILED: Game process '{current_game_process_name}' not found within {max_wait_time} seconds")
            response_data = {
                "status": "error",
                "error": f"Game process '{current_game_process_name}' not detected after {max_wait_time}s. Game may not be installed or process name is incorrect.",
                "subprocess_pid": game_process.pid if game_process else None,
                "subprocess_status": subprocess_status,
                "resolved_path": game_path if is_steam_id else None,
                "launch_method": "steam" if is_steam_id else "direct_exe",
                "expected_process": current_game_process_name
            }

    return response_data


def terminate_game() -> Dict[str, Any]:
    """Terminate the currently tracked game."""
    global game_process, current_game_process_name

    with game_lock:
        terminated = False

        if current_game_process_name:
            if terminate_process_by_name(current_game_process_name):
                terminated = True

        if game_process and game_process.poll() is None:
            game_process.terminate()
            try:
                game_process.wait(timeout=5)
                terminated = True
            except subprocess.TimeoutExpired:
                game_process.kill()
                terminated = True

        message = "Game terminated" if terminated else "No game running"
        return {
            "status": "success",
            "action": "terminate_game",
            "message": message
        }


def get_current_game_info() -> Dict[str, Any]:
    """Get information about the currently tracked game."""
    global current_game_process_name, game_process

    info = {
        "process_name": current_game_process_name,
        "running": False,
        "pid": None
    }

    if current_game_process_name:
        proc = find_process_by_name(current_game_process_name)
        if proc:
            info["running"] = True
            info["pid"] = proc.pid
            info["status"] = proc.status()

    return info


def get_game_status() -> Dict[str, Any]:
    """Alias for get_current_game_info - returns game status for /status endpoint."""
    return get_current_game_info()
