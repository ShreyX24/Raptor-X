"""
Steam Integration Module
Handles Steam installation detection, library paths, and auto-login.

Merged from KATANA Gemma v0.2 and Preset Manager
"""

import os
import re
import time
import winreg
import subprocess
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Steam Installation Detection
# =============================================================================

def get_steam_install_path() -> Optional[str]:
    """
    Get Steam installation path from Windows Registry.

    Tries HKCU first, then HKLM for 32-bit and 64-bit locations.

    Returns:
        Steam installation path or None if not found
    """
    # Try HKEY_CURRENT_USER first
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        path, _ = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)
        if path and os.path.exists(path):
            return path
    except Exception:
        pass

    # Try HKEY_LOCAL_MACHINE (64-bit)
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")
        path, _ = winreg.QueryValueEx(key, "InstallPath")
        winreg.CloseKey(key)
        if path and os.path.exists(path):
            return path
    except Exception:
        pass

    # Try HKEY_LOCAL_MACHINE (32-bit)
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam")
        path, _ = winreg.QueryValueEx(key, "InstallPath")
        winreg.CloseKey(key)
        if path and os.path.exists(path):
            return path
    except Exception:
        pass

    logger.warning("Steam installation not found in registry")
    return None


def get_steam_library_folders() -> List[str]:
    """
    Get all Steam library folders (including alternate locations).

    Returns:
        List of Steam library folder paths
    """
    steam_path = get_steam_install_path()
    if not steam_path:
        return []

    libraries = [steam_path]

    # Parse libraryfolders.vdf
    vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
    if os.path.exists(vdf_path):
        try:
            with open(vdf_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Regex to find "path" "..." entries
            matches = re.findall(r'"path"\s+"([^"]+)"', content)
            for match in matches:
                # Unescape double backslashes
                path = match.replace('\\\\', '\\')
                if path not in libraries and os.path.exists(path):
                    libraries.append(path)

        except Exception as e:
            logger.warning(f"Failed to parse libraryfolders.vdf: {e}")

    return libraries


def find_steam_game_path(app_id: str) -> Optional[str]:
    """
    Find the installation path for a Steam game by App ID.

    Args:
        app_id: Steam application ID

    Returns:
        Path to game installation folder or None
    """
    libraries = get_steam_library_folders()

    for lib in libraries:
        manifest_path = os.path.join(lib, "steamapps", f"appmanifest_{app_id}.acf")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                match = re.search(r'"installdir"\s+"([^"]+)"', content)
                if match:
                    install_dir = match.group(1)
                    full_path = os.path.join(lib, "steamapps", "common", install_dir)
                    if os.path.exists(full_path):
                        return full_path

            except Exception as e:
                logger.warning(f"Failed to parse manifest for app {app_id}: {e}")

    return None


# =============================================================================
# Steam Auto-Login
# =============================================================================

def set_steam_auto_login(username: str) -> bool:
    """
    Set the AutoLoginUser registry key to enable auto-login for specified user.

    Args:
        username: Steam username to set for auto-login

    Returns:
        True if successful
    """
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Valve\Steam",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "AutoLoginUser", 0, winreg.REG_SZ, username)
        winreg.SetValueEx(key, "RememberPassword", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
        logger.info(f"Registry: Set AutoLoginUser to '{username}'")
        return True
    except Exception as e:
        logger.warning(f"Failed to set AutoLoginUser registry: {e}")
        return False


def get_steam_auto_login_user() -> Optional[str]:
    """
    Get the current AutoLoginUser from registry.

    Returns:
        Username or None
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        username, _ = winreg.QueryValueEx(key, "AutoLoginUser")
        winreg.CloseKey(key)
        return username if username else None
    except Exception:
        return None


def verify_steam_login(timeout: int = 45) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Verify that Steam is logged in via registry check (ActiveUser != 0).

    NOTE: Steam conflict detection (account in use elsewhere) is now handled
    by the Gemma backend using OmniParser to parse screenshots after game launch.
    This function only checks the registry for successful login.

    Args:
        timeout: Maximum seconds to wait for login

    Returns:
        tuple: (success: bool, user_id: int or None, error_reason: str or None)
               error_reason can be: "timeout", None (success)
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Check registry for successful login
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess")
            active_user, _ = winreg.QueryValueEx(key, "ActiveUser")
            winreg.CloseKey(key)

            if active_user and active_user != 0:
                logger.info(f"Steam login verified! ActiveUser ID: {active_user}")
                return True, active_user, None
            else:
                logger.debug("Steam ActiveUser is 0, login in progress...")

        except Exception as e:
            logger.debug(f"Waiting for Steam registry... {e}")

        time.sleep(2)

    logger.warning(f"Steam login verification timed out after {timeout}s")
    return False, None, "timeout"


def is_steam_running() -> bool:
    """Check if Steam is currently running."""
    import psutil
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == 'steam.exe':
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def kill_steam() -> bool:
    """Kill Steam and related processes."""
    import psutil
    killed = False

    for process_name in ['steam.exe', 'steamwebhelper.exe']:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
                    psutil.Process(proc.info['pid']).terminate()
                    killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    return killed


def login_steam(username: str, password: str, timeout: int = 180) -> Dict[str, Any]:
    """
    Login to Steam using steam.exe -login command.

    Flow:
    1. Check if already logged in (skip if so)
    2. Kill existing Steam processes
    3. Set registry for the desired user
    4. Launch steam.exe with -login credentials
    5. Wait and verify login via registry

    NOTE: Steam conflict detection (account in use elsewhere) is now handled
    by the Gemma backend using OmniParser after game launch.

    Args:
        username: Steam username
        password: Steam password
        timeout: Max time to wait for login verification

    Returns:
        dict: Result with status, message, user_id, error_reason
              status: "success", "warning", "error"
              error_reason: None, "timeout", "not_found"
    """
    logger.info(f"===== Steam Login Request: {username} =====")

    # 1. Check if already logged in as this user
    if is_steam_running():
        current_user = get_steam_auto_login_user()
        logger.info(f"Current AutoLoginUser: {current_user}")

        if current_user and current_user.lower() == username.lower():
            verified, user_id, error_reason = verify_steam_login(timeout=5)
            if verified:
                logger.info(f"Already logged in as {username}")
                return {
                    "status": "success",
                    "message": "Already logged in",
                    "user_id": user_id
                }

    # 2. Kill all Steam processes
    logger.info("Killing Steam processes...")
    kill_steam()
    time.sleep(3)

    # 3. Set registry for auto-login
    set_steam_auto_login(username)

    # 4. Get Steam path
    steam_path = get_steam_install_path()
    if not steam_path:
        return {"status": "error", "message": "Steam not found", "error_reason": "not_found"}

    steam_exe = os.path.join(steam_path, "steam.exe")
    if not os.path.exists(steam_exe):
        return {"status": "error", "message": f"steam.exe not found: {steam_exe}", "error_reason": "not_found"}

    # 5. Launch Steam with -login credentials
    cmd = [steam_exe, "-login", username, password]
    logger.info(f"Launching: steam.exe -login {username} ********")
    subprocess.Popen(cmd)

    # 6. Wait for login verification
    logger.info("Waiting for Steam login...")
    verified, user_id, error_reason = verify_steam_login(timeout=timeout)

    if verified:
        logger.info(f"===== Steam Login SUCCESS: {username} (ID: {user_id}) =====")
        return {
            "status": "success",
            "message": "Steam login successful",
            "user_id": user_id
        }
    else:
        logger.warning("Steam login verification failed - check SUT")
        return {
            "status": "warning",
            "message": "Steam launched but login unverified (timeout)",
            "error_reason": error_reason or "timeout"
        }
