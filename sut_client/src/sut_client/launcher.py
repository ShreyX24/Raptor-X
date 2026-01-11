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


def get_steam_executable_path() -> Optional[str]:
    """Get the path to steam.exe"""
    steam_path = get_steam_install_path()
    if steam_path:
        steam_exe = os.path.join(steam_path, "steam.exe")
        if os.path.exists(steam_exe):
            return steam_exe
    return None

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

def find_process_by_name(process_name: str, exact_only: bool = False, debug_log_similar: bool = False) -> Optional[psutil.Process]:
    """
    Find a running process by its name.

    Args:
        process_name: Name of process to find (e.g., "RDR2.exe" or "b1")
        exact_only: If True, only exact matches are returned.
                    If False (default), substring matches are also allowed.
        debug_log_similar: If True, log processes with similar names when not found

    Returns:
        psutil.Process or None
    """
    similar_processes = []  # For debugging
    search_term = process_name.lower().replace('.exe', '')  # e.g., "rdr2"

    try:
        # Use process_iter with field selection (same as system.py - proven to work)
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_name = proc.info['name']
                proc_exe = os.path.basename(proc.info['exe']) if proc.info['exe'] else None
                pid = proc.info['pid']

                if exact_only:
                    # EXACT match only (case-insensitive)
                    if (proc_name and proc_name.lower() == process_name.lower()) or \
                       (proc_exe and proc_exe.lower() == process_name.lower()):
                        logger.info(f"[EXACT] Found process: {proc_name} (PID: {pid})")
                        return psutil.Process(pid)
                else:
                    # Partial/substring match (case-insensitive)
                    if (proc_name and process_name.lower() in proc_name.lower()) or \
                       (proc_exe and process_name.lower() in proc_exe.lower()):
                        logger.info(f"[SUBSTRING] Found process: {proc_name} (PID: {pid})")
                        return psutil.Process(pid)

                # Track similar processes for debugging
                if debug_log_similar and proc_name:
                    name_lower = proc_name.lower()
                    # Check if any part of the search term matches
                    if search_term[:3] in name_lower or name_lower[:3] in search_term:
                        similar_processes.append(f"{proc_name} (PID:{pid})")

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as e:
        logger.error(f"Error searching for process {process_name}: {str(e)}")

    # Log similar processes if debugging enabled and process not found
    if debug_log_similar and similar_processes:
        logger.debug(f"Similar processes to '{process_name}': {similar_processes[:10]}")

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
    launch_args: Optional[str] = None,  # Command-line arguments for the game
    # Legacy parameters for backwards compatibility
    game_path: Optional[str] = None,
    process_id: str = '',
    visible_timeout: int = 40,   # Reduced from 120 - window should be visible quickly
    ready_timeout: int = 10,     # Reduced from 30 - window ready state is fast
    retry_count: int = 5,        # Keep at 5 retries
    retry_interval: int = 5,     # Reduced from 10 - faster retry cycle
    process_detection_timeout: int = 60  # Timeout for initial process detection
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
        launch_args: Command-line arguments to pass to the game (e.g., "-benchmark test.xml")
        game_path: Legacy param - Path to executable or Steam App ID
        process_id: Legacy param - Expected process name
        visible_timeout: Timeout for window visibility detection
        ready_timeout: Timeout for window ready detection
        retry_count: Number of retries for foreground detection
        retry_interval: Seconds between retries
        process_detection_timeout: Timeout for initial process detection (default 60s)

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

    # Handle force relaunch - kill existing game before launching
    # This handles both: (1) tracked game from previous launch, (2) game running from before SUT started
    if force_relaunch:
        # First, try to kill by tracked name (from previous launch in this session)
        if current_game_process_name:
            logger.info(f"Force relaunch: terminating tracked game {current_game_process_name}")
            terminate_process_by_name(current_game_process_name)
            time.sleep(2)
        # Also kill by target process name (handles SUT restart case where tracking is lost)
        if process_id and process_id != current_game_process_name:
            # Check if target process is already running
            existing_proc = find_process_by_name(process_id, exact_only=True)
            if existing_proc:
                logger.info(f"Force relaunch: terminating existing {process_id} (PID {existing_proc.pid})")
                terminate_process_by_name(process_id)
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
        if steam_app_id and not launch_args:
            # Launch via Steam protocol (no args)
            steam_url = f"steam://rungameid/{steam_app_id}"
            logger.info(f"Launching game via Steam protocol: {steam_url}")
            os.startfile(steam_url)
            game_process = None
        elif steam_app_id and launch_args:
            # Launch via Steam CLI with arguments (handles DRM properly)
            # steam.exe -applaunch <appid> <args>
            import shlex
            steam_exe = get_steam_executable_path()
            if not steam_exe:
                steam_exe = "steam.exe"  # Fallback, hope it's in PATH

            # Parse launch_args if it's a string
            if isinstance(launch_args, str):
                args_list = shlex.split(launch_args)
            else:
                args_list = list(launch_args)

            cmd = [steam_exe, "-applaunch", steam_app_id] + args_list
            logger.info(f"Launching via Steam CLI with args: {cmd}")
            game_process = subprocess.Popen(cmd)
            subprocess_status = "steam_cli"
        else:
            # Direct exe launch (no Steam app ID, with optional args)
            logger.info(f"Launching game directly: {game_path}")
            if launch_args:
                logger.info(f"With launch arguments: {launch_args}")

            game_dir = os.path.dirname(game_path)
            try:
                if launch_args:
                    # Build command with arguments
                    import shlex
                    # Handle both string and list args
                    if isinstance(launch_args, str):
                        cmd = [game_path] + shlex.split(launch_args)
                    else:
                        cmd = [game_path] + list(launch_args)
                    logger.info(f"Launch command: {cmd}")
                    game_process = subprocess.Popen(cmd, cwd=game_dir)
                else:
                    game_process = subprocess.Popen(game_path, cwd=game_dir)
                subprocess_status = "direct_exe"
            except Exception as e:
                logger.warning(f"Failed to launch with cwd, trying direct: {e}")
                if launch_args:
                    import shlex
                    cmd = [game_path] + shlex.split(launch_args) if isinstance(launch_args, str) else [game_path] + list(launch_args)
                    game_process = subprocess.Popen(cmd)
                else:
                    game_process = subprocess.Popen(game_path)

        # Log launch status
        if game_process:
            logger.info(f"Subprocess started with PID: {game_process.pid}")
        else:
            logger.info("Game launched via Steam protocol (no direct PID)")

        time.sleep(3)  # Initial wait for process spawn

        # NOTE: Steam conflict detection (account in use on another computer) is now
        # handled by the Gemma backend using OmniParser to parse screenshots after launch.
        # This allows for reliable detection of the SDL-rendered dialog.

        if game_process:
            subprocess_status = "running" if game_process.poll() is None else "exited"
            logger.info(f"Subprocess status after checks: {subprocess_status}")

        # Wait for actual game process
        max_wait_time = process_detection_timeout
        actual_process = None
        foreground_confirmed = False

        logger.info(f"Waiting up to {max_wait_time}s for process '{current_game_process_name}' to appear...")

        # Phase 1: Detect Process - poll every 2s with progress logging
        start_wait = time.time()
        cancelled = False
        check_count = 0
        last_log_time = 0
        while time.time() - start_wait < max_wait_time:
            check_count += 1
            elapsed = int(time.time() - start_wait)

            # Enable debug logging every 30s to see similar processes
            debug_mode = elapsed > 0 and elapsed % 30 == 0 and elapsed != last_log_time

            actual_process = find_process_by_name(current_game_process_name, debug_log_similar=debug_mode)
            if actual_process:
                logger.info(f"Process found after {elapsed}s (check #{check_count}): {actual_process.name()} (PID: {actual_process.pid})")
                break

            # Log progress every 10s with process scan
            if elapsed > 0 and elapsed % 10 == 0 and elapsed != last_log_time:
                logger.info(f"Still waiting for '{current_game_process_name}'... ({elapsed}s/{max_wait_time}s, check #{check_count})")
                # Log any RDR/Rockstar processes we can see (helpful for debugging)
                try:
                    rockstar_procs = []
                    for p in psutil.process_iter(['pid', 'name']):
                        try:
                            pname = p.info['name'].lower()
                            if 'rdr' in pname or 'rockstar' in pname or 'launcher' in pname or 'social' in pname:
                                rockstar_procs.append(f"{p.info['name']}({p.info['pid']})")
                        except:
                            pass
                    if rockstar_procs:
                        logger.info(f"  Rockstar processes visible: {', '.join(rockstar_procs)}")
                    else:
                        logger.info(f"  No Rockstar/RDR processes visible yet")
                except Exception as e:
                    logger.warning(f"  Could not scan processes: {e}")
                last_log_time = elapsed

            if launch_cancel_flag.wait(timeout=2):  # Poll every 2s (faster than 3s)
                logger.info("Launch cancelled during process detection")
                cancelled = True
                break

        if cancelled:
            return {"status": "cancelled", "message": "Launch cancelled by user"}

        if actual_process:
            # Early exit check: Is window already in foreground?
            # This avoids expensive pywinauto detection if game is already focused
            try:
                import win32gui
                import win32process
                foreground_hwnd = win32gui.GetForegroundWindow()
                if foreground_hwnd:
                    _, fg_pid = win32process.GetWindowThreadProcessId(foreground_hwnd)
                    if fg_pid == actual_process.pid:
                        logger.info(f"[FAST PATH] Game window already in foreground (PID {actual_process.pid})")
                        foreground_confirmed = True
                        # Skip all the expensive detection, go straight to response
                        response_data = {
                            "status": "success",
                            "subprocess_pid": game_process.pid if game_process else None,
                            "subprocess_status": subprocess_status,
                            "resolved_path": game_path if is_steam_id else None,
                            "launch_method": "steam" if is_steam_id else "direct_exe",
                            "game_process_pid": actual_process.pid,
                            "game_process_name": actual_process.name(),
                            "game_process_status": actual_process.status(),
                            "foreground_confirmed": True,
                            "fast_path": True,  # Indicator that we skipped detection
                            "pywinauto_available": is_pywinauto_available(),
                        }
                        logger.info(f"[OK] Launch Complete (fast path): {actual_process.name()} already in foreground.")
                        minimized = minimize_other_windows(actual_process.pid, exclude_process_name=current_game_process_name)
                        response_data["windows_minimized"] = minimized
                        return response_data
            except Exception as e:
                logger.debug(f"Early foreground check failed (non-fatal): {e}")

            # Phase 2: Wait for window, then bring to foreground
            # Once process is detected, window should appear shortly
            # Poll for window existence (up to 15s), then try foreground
            logger.info("Process detected, waiting for window to appear...")

            # Wait for window to exist (poll every 2s for up to 15s)
            window_wait_start = time.time()
            window_found = False
            while time.time() - window_wait_start < 15:
                try:
                    import win32gui
                    import win32process

                    def find_window_for_pid(hwnd, pid_windows):
                        try:
                            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                            if found_pid == actual_process.pid and win32gui.IsWindowVisible(hwnd):
                                pid_windows.append(hwnd)
                        except:
                            pass
                        return True

                    windows = []
                    win32gui.EnumWindows(find_window_for_pid, windows)
                    if windows:
                        window_found = True
                        logger.info(f"Window found for PID {actual_process.pid} after {time.time() - window_wait_start:.1f}s")
                        break
                except Exception as e:
                    logger.debug(f"Window search error: {e}")

                if launch_cancel_flag.wait(timeout=2):
                    logger.info("Launch cancelled during window wait")
                    return {"status": "cancelled", "message": "Launch cancelled by user"}

            if not window_found:
                logger.info("No window found after 15s, but process is running - continuing")

            # Now try to bring to foreground
            logger.info("Attempting to bring window to foreground...")

            # Try modern method first (5s max)
            # Skip pywinauto - it hangs on fullscreen games
            foreground_confirmed = ensure_window_foreground_v2(actual_process.pid, timeout=5, use_pywinauto=False)

            if not foreground_confirmed:
                # Try legacy method once (5s max)
                logger.info("Modern foreground failed, trying legacy method...")
                foreground_confirmed = ensure_window_foreground(actual_process.pid, timeout=5)

            # If still not foreground, that's OK - process is running, startup_wait will handle it
            if not foreground_confirmed:
                logger.info("Foreground not confirmed, but process is running - continuing (startup_wait will handle)")

            # Minimize other windows to help with focus (but not the game process itself)
            minimize_other_windows(actual_process.pid, exclude_process_name=current_game_process_name)

            # Build response - handle case where original process exited (launcher spawned real game)
            # This is common with Ubisoft/launcher-based games where launcher exits after spawning game
            try:
                process_name = actual_process.name()
                process_status = actual_process.status()
                process_pid = actual_process.pid
            except psutil.NoSuchProcess:
                # Original process exited (likely a launcher) - try to find the game again
                logger.info(f"Original process {actual_process.pid} exited, re-detecting by name...")
                new_process = find_process_by_name(current_game_process_name)
                if new_process:
                    logger.info(f"Found game process with new PID: {new_process.name()} (PID: {new_process.pid})")
                    actual_process = new_process
                    process_name = new_process.name()
                    process_status = new_process.status()
                    process_pid = new_process.pid
                else:
                    # Process really is gone - but still return success since we detected it
                    logger.warning(f"Process '{current_game_process_name}' no longer running, but was detected earlier")
                    process_name = current_game_process_name
                    process_status = "exited"
                    process_pid = None

            # Always return success if process was running - startup_wait handles the rest
            response_data = {
                "status": "success",
                "subprocess_pid": game_process.pid if game_process else None,
                "subprocess_status": subprocess_status,
                "resolved_path": game_path if is_steam_id else None,
                "launch_method": "steam" if is_steam_id else "direct_exe",
                "game_process_pid": process_pid,
                "game_process_name": process_name,
                "game_process_status": process_status,
                "window_found": window_found,
                "foreground_confirmed": foreground_confirmed,
                "pywinauto_available": is_pywinauto_available(),
            }

            logger.info(f"[OK] Launch Complete: {process_name} (PID: {process_pid}) is running. Window: {window_found}, Foreground: {foreground_confirmed}")

        else:
            logger.error(f"LAUNCH FAILED: Game process '{current_game_process_name}' not found within {max_wait_time}s")
            response_data = {
                "status": "error",
                "error": f"Game process '{current_game_process_name}' not detected after {max_wait_time}s. Game may not be installed, process name is incorrect, or a Steam dialog may be blocking launch.",
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
