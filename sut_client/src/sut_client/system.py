"""
System utilities for SUT Client
Provides PC rename, process management, and other system-level operations

Merged with KATANA Gemma v0.2 process management functions
"""

import os
import platform
import subprocess
import re
import logging
from typing import Dict, Any, Optional

import psutil

logger = logging.getLogger(__name__)


# =============================================================================
# Process Detection (from KATANA Gemma v0.2)
# =============================================================================

def find_process_by_name(process_name: str, exact_only: bool = True) -> Optional[psutil.Process]:
    """
    Find a running process by its name.

    Args:
        process_name: Name of process to find (e.g., "RDR2.exe")
        exact_only: If True (default), only exact matches are returned.
                    If False, substring matches are also allowed.

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
                    # Partial/substring match
                    if (proc_name and process_name.lower() in proc_name.lower()) or \
                       (proc_exe and process_name.lower() in proc_exe.lower()):
                        logger.info(f"[PARTIAL] Found process: {proc_name} (PID: {proc.info['pid']})")
                        return psutil.Process(proc.info['pid'])

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as e:
        logger.error(f"Error searching for process {process_name}: {str(e)}")
    return None


def check_process(process_name: str) -> Dict[str, Any]:
    """
    Check if a process is running by name.

    Args:
        process_name: Process name to check

    Returns:
        dict with running status, pid, and name
    """
    logger.debug(f"[Process] Checking if '{process_name}' is running")
    proc = find_process_by_name(process_name)

    if proc:
        logger.debug(f"[Process] '{process_name}' is running: PID={proc.pid}, name={proc.name()}")
        return {
            "status": "success",
            "running": True,
            "pid": proc.pid,
            "name": proc.name()
        }
    else:
        logger.debug(f"[Process] '{process_name}' is not running")
        return {
            "status": "success",
            "running": False
        }


def terminate_process_by_name(process_name: str) -> bool:
    """
    Terminate a process by its name using psutil.

    Args:
        process_name: Name of process to terminate

    Returns:
        True if any process was terminated
    """
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
# Admin Privileges Check
# =============================================================================

def is_admin() -> bool:
    """Check if running with administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


# =============================================================================
# PC Rename Functions (Original PM)
# =============================================================================


def rename_computer(new_name: str) -> Dict[str, Any]:
    """
    Rename the Windows computer hostname.

    Uses PowerShell Rename-Computer command. Requires admin privileges.
    The change takes effect after a system restart.

    Args:
        new_name: New computer name (hostname)

    Returns:
        Dict with:
            - success: bool - Whether rename command succeeded
            - requires_reboot: bool - Always True for Windows hostname changes
            - message: str - Status message
            - error: str - Error message if failed
    """
    result = {
        "success": False,
        "requires_reboot": True,
        "message": "",
        "error": None
    }

    # Validate platform
    if platform.system() != "Windows":
        result["error"] = "PC rename is only supported on Windows"
        result["message"] = "Rename failed: Not a Windows system"
        return result

    # Validate new name
    if not new_name:
        result["error"] = "New name cannot be empty"
        result["message"] = "Rename failed: Empty name provided"
        return result

    # Validate hostname format (Windows NetBIOS name rules)
    # - Max 15 characters
    # - No special characters except hyphen
    # - Cannot start or end with hyphen
    if not is_valid_hostname(new_name):
        result["error"] = f"Invalid hostname: '{new_name}'. Must be 1-15 chars, alphanumeric and hyphens only, cannot start/end with hyphen."
        result["message"] = "Rename failed: Invalid hostname format"
        return result

    try:
        # Use PowerShell to rename the computer
        # -Force bypasses confirmation prompts
        # Note: Requires elevated privileges (run as Administrator)
        cmd = [
            "powershell",
            "-Command",
            f'Rename-Computer -NewName "{new_name}" -Force'
        ]

        logger.info(f"Executing PC rename: {new_name}")

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if process.returncode == 0:
            result["success"] = True
            result["message"] = f"Computer renamed to '{new_name}'. Restart required for changes to take effect."
            logger.info(f"PC rename successful: {new_name}")
        else:
            error_msg = process.stderr.strip() if process.stderr else "Unknown error"

            # Check for common errors
            if "Access is denied" in error_msg or "PermissionDenied" in error_msg:
                result["error"] = "Access denied. SUT Client must run as Administrator."
                result["message"] = "Rename failed: Administrator privileges required"
            elif "already in use" in error_msg.lower():
                result["error"] = f"The name '{new_name}' is already in use on the network."
                result["message"] = "Rename failed: Name already in use"
            else:
                result["error"] = error_msg
                result["message"] = f"Rename failed: {error_msg}"

            logger.error(f"PC rename failed: {error_msg}")

    except subprocess.TimeoutExpired:
        result["error"] = "Command timed out"
        result["message"] = "Rename failed: Command timed out"
        logger.error("PC rename command timed out")

    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Rename failed: {str(e)}"
        logger.error(f"PC rename exception: {e}")

    return result


def is_valid_hostname(name: str) -> bool:
    """
    Validate Windows hostname (NetBIOS name).

    Rules:
    - 1-15 characters
    - Alphanumeric and hyphens only
    - Cannot start or end with hyphen
    - Cannot be all digits

    Args:
        name: Proposed hostname

    Returns:
        True if valid, False otherwise
    """
    if not name:
        return False

    if len(name) > 15:
        return False

    # Check allowed characters (alphanumeric and hyphen)
    if not re.match(r'^[a-zA-Z0-9-]+$', name):
        return False

    # Cannot start or end with hyphen
    if name.startswith('-') or name.endswith('-'):
        return False

    # Cannot be all digits
    if name.isdigit():
        return False

    return True


def get_current_hostname() -> str:
    """
    Get current computer hostname.

    Returns:
        Current hostname
    """
    import socket
    return socket.gethostname()


def reboot_computer(delay_seconds: int = 0) -> Dict[str, Any]:
    """
    Reboot the computer.

    Args:
        delay_seconds: Delay before reboot (0 = immediate)

    Returns:
        Dict with success status and message
    """
    result = {
        "success": False,
        "message": "",
        "error": None
    }

    if platform.system() != "Windows":
        result["error"] = "Reboot command is only supported on Windows"
        return result

    try:
        cmd = ["shutdown", "/r", "/t", str(delay_seconds)]

        if delay_seconds > 0:
            cmd.extend(["/c", f"System will restart in {delay_seconds} seconds"])

        process = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if process.returncode == 0:
            result["success"] = True
            result["message"] = f"Reboot initiated (delay: {delay_seconds}s)"
        else:
            result["error"] = process.stderr.strip() if process.stderr else "Unknown error"
            result["message"] = f"Reboot failed: {result['error']}"

    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Reboot failed: {str(e)}"

    return result


def kill_process(process_name: str) -> Dict[str, Any]:
    """
    Kill a process by name.

    Args:
        process_name: Process name (e.g., "game.exe")

    Returns:
        Dict with success status and message
    """
    result = {
        "success": False,
        "message": "",
        "error": None,
        "killed": False
    }

    if platform.system() != "Windows":
        result["error"] = "Kill process is only supported on Windows"
        return result

    # Ensure .exe extension
    if not process_name.lower().endswith('.exe'):
        process_name = f"{process_name}.exe"

    try:
        # Use taskkill to forcefully terminate the process
        cmd = ["taskkill", "/F", "/IM", process_name]

        logger.info(f"Killing process: {process_name}")
        logger.debug(f"[Process] Executing: {' '.join(cmd)}")

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

        if process.returncode == 0:
            result["success"] = True
            result["killed"] = True
            result["message"] = f"Process '{process_name}' terminated"
            logger.info(f"Process killed: {process_name}")
        elif "not found" in process.stderr.lower() or process.returncode == 128:
            # Process wasn't running - that's okay
            result["success"] = True
            result["killed"] = False
            result["message"] = f"Process '{process_name}' was not running"
            logger.debug(f"Process not running: {process_name}")
        else:
            result["error"] = process.stderr.strip() if process.stderr else "Unknown error"
            result["message"] = f"Failed to kill process: {result['error']}"
            logger.error(f"Failed to kill {process_name}: {result['error']}")

    except subprocess.TimeoutExpired:
        result["error"] = "Command timed out"
        result["message"] = "Kill process timed out"
        logger.error(f"Kill process timed out: {process_name}")

    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Kill process failed: {str(e)}"
        logger.error(f"Kill process exception: {e}")

    return result
