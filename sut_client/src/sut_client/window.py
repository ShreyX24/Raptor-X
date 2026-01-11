"""
Window Detection and Management Module
Provides pywinauto-based window detection with Win32 API fallback.

Ported from KATANA Gemma v0.2
Author: SATYAJIT BHUYAN (satyajit.bhuyan@intel.com)
"""

import time
import ctypes
from ctypes import wintypes
import logging

import win32api
import win32con
import win32gui
import win32process

logger = logging.getLogger(__name__)

# =============================================================================
# pywinauto availability check
# =============================================================================

try:
    from pywinauto import Application
    from pywinauto.timings import TimeoutError as PywinautoTimeoutError
    PYWINAUTO_AVAILABLE = True
    logger.info("pywinauto loaded - enhanced window detection enabled")
except ImportError:
    PYWINAUTO_AVAILABLE = False
    logger.info("pywinauto not available - using Win32 fallback")


# =============================================================================
# Windows API constants
# =============================================================================

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

# SystemParametersInfo constants for foreground lock timeout
SPI_GETFOREGROUNDLOCKTIMEOUT = 0x2000
SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001
SPIF_SENDCHANGE = 0x0002


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION)
    ]


# =============================================================================
# DPI Awareness
# =============================================================================

def set_dpi_awareness():
    """
    Set DPI awareness to get real physical screen resolution.
    Without this, GetSystemMetrics returns scaled coordinates on HiDPI displays.
    Should be called early, before any resolution queries.
    """
    try:
        # Try Windows 10+ method first (Per-Monitor DPI Aware v2)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        logger.info("DPI Awareness: Per-Monitor DPI Aware v2")
    except Exception:
        try:
            # Fall back to Windows 8.1+ method
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            logger.info("DPI Awareness: System DPI Aware")
        except Exception:
            try:
                # Fall back to Windows Vista+ method
                ctypes.windll.user32.SetProcessDPIAware()
                logger.info("DPI Awareness: Legacy DPI Aware")
            except Exception as e:
                logger.warning(f"Could not set DPI awareness: {e}")


# =============================================================================
# Window Detection Functions
# =============================================================================

def wait_for_window_ready_pywinauto(
    pid: int,
    process_name: str = None,
    visible_timeout: int = 60,
    ready_timeout: int = 30
) -> tuple:
    """
    Wait for window to be visible AND ready using pywinauto.

    'ready' means the window's message queue is idle (fully loaded).
    This is more reliable than just checking if window exists.

    Args:
        pid: Process ID to wait for
        process_name: Optional process name for fallback connection
        visible_timeout: Max seconds to wait for window to become visible
        ready_timeout: Max seconds to wait for window to become ready/idle

    Returns:
        tuple: (success: bool, window_handle: int or None, window_title: str or None)
    """
    if not PYWINAUTO_AVAILABLE:
        logger.debug("pywinauto not available, skipping wait_for_window_ready_pywinauto")
        return False, None, None

    logger.info(f"Waiting for window ready state (PID: {pid})")

    try:
        # Connect to the process using pywinauto
        # Try 'uia' backend first (works with modern apps), fall back to 'win32'
        app = None
        for backend in ['uia', 'win32']:
            try:
                logger.debug(f"Trying pywinauto backend: {backend}")
                app = Application(backend=backend).connect(process=pid, timeout=10)
                logger.debug(f"Connected with backend: {backend}")
                break
            except Exception as e:
                logger.debug(f"Backend {backend} failed: {e}")
                continue

        if not app:
            logger.warning(f"Could not connect pywinauto to PID {pid}")
            return False, None, None

        # Get the top-level window
        try:
            main_window = app.top_window()
            window_title = main_window.window_text()
            logger.debug(f"Found top window: '{window_title}'")
        except Exception as e:
            logger.warning(f"Could not get top window: {e}")
            return False, None, None

        # Phase 1: Wait for window to be VISIBLE
        logger.info(f"Phase 1: Waiting up to {visible_timeout}s for window to be visible...")
        try:
            # Use retry_interval=2.0 to reduce CPU polling frequency
            main_window.wait('visible', timeout=visible_timeout, retry_interval=2.0)
            logger.info(f"Window is visible: '{window_title}'")
        except PywinautoTimeoutError:
            logger.warning(f"Window not visible after {visible_timeout}s")
            return False, None, window_title

        # Phase 2: Wait for window to be READY (message queue idle)
        # This is the key improvement - waits until app is fully loaded
        logger.info(f"Phase 2: Waiting up to {ready_timeout}s for window to be ready/idle...")
        try:
            main_window.wait('ready', timeout=ready_timeout, retry_interval=2.0)
            logger.info(f"Window is ready (message queue idle): '{window_title}'")
        except PywinautoTimeoutError:
            logger.warning(f"Window not ready after {ready_timeout}s (may still work)")
            # Continue anyway - window is at least visible

        # Get window handle for foreground operations
        try:
            hwnd = main_window.handle
            logger.info(f"Window ready! HWND={hwnd}, Title='{window_title}'")
            return True, hwnd, window_title
        except Exception as e:
            logger.warning(f"Could not get window handle: {e}")
            return True, None, window_title

    except Exception as e:
        logger.error(f"wait_for_window_ready_pywinauto failed: {e}")
        return False, None, None


def bring_to_foreground_pywinauto(pid: int) -> bool:
    """
    Use pywinauto's set_focus() which is more reliable than Win32 APIs.

    Returns:
        bool: True if successfully brought to foreground
    """
    if not PYWINAUTO_AVAILABLE:
        return False

    try:
        for backend in ['uia', 'win32']:
            try:
                app = Application(backend=backend).connect(process=pid, timeout=5)
                main_window = app.top_window()

                # pywinauto's set_focus() handles all the Win32 complexity internally
                main_window.set_focus()
                time.sleep(0.3)

                # Verify
                if main_window.has_focus():
                    logger.info("pywinauto.set_focus() succeeded")
                    return True

            except Exception as e:
                logger.debug(f"pywinauto set_focus with {backend} failed: {e}")
                continue

        return False

    except Exception as e:
        logger.debug(f"bring_to_foreground_pywinauto failed: {e}")
        return False


def ensure_window_foreground_v2(pid: int, timeout: int = 5, use_pywinauto: bool = True) -> bool:
    """
    Ensure window is in foreground using best available method.

    Tries pywinauto first (more reliable), falls back to Win32 API.

    Args:
        pid: Process ID
        timeout: Timeout for Win32 fallback method
        use_pywinauto: If True, try pywinauto first

    Returns:
        bool: True if window is confirmed in foreground
    """
    # Try pywinauto first if available
    if use_pywinauto and PYWINAUTO_AVAILABLE:
        logger.debug(f"Trying pywinauto set_focus for PID {pid}")
        if bring_to_foreground_pywinauto(pid):
            return True
        logger.debug("pywinauto failed, falling back to Win32")

    # Fallback to original Win32 method
    return ensure_window_foreground(pid, timeout)


def ensure_window_foreground(pid: int, timeout: int = 5) -> bool:
    """
    Original Win32-based foreground method (used as fallback).

    Args:
        pid: Process ID
        timeout: Max time to try bringing window to foreground

    Returns:
        bool: True if window is confirmed in foreground
    """
    logger.debug(f"ensure_window_foreground called for PID {pid} with timeout={timeout}s")

    # Callback to find windows for PID
    def callback(hwnd, windows):
        try:
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == pid:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        windows.append((hwnd, title))
        except Exception:
            pass
        return True

    start_time = time.time()
    attempt = 0

    while time.time() - start_time < timeout:
        attempt += 1
        windows = []
        try:
            win32gui.EnumWindows(callback, windows)
        except Exception as e:
            logger.warning(f"Window enumeration failed: {e}")

        if windows:
            # Use first window with a title found
            target_hwnd, window_title = windows[0]
            logger.debug(f"Attempt {attempt}: Found {len(windows)} window(s) for PID {pid}. "
                        f"Target: HWND={target_hwnd}, Title='{window_title}'")

            # Helper to try forcing foreground
            current_tid = win32api.GetCurrentThreadId()
            target_tid, _ = win32process.GetWindowThreadProcessId(target_hwnd)

            try:
                # Disable foreground lock timeout temporarily
                # This is the most reliable way to bypass SetForegroundWindow restrictions
                old_timeout = ctypes.c_uint(0)
                ctypes.windll.user32.SystemParametersInfoW(
                    SPI_GETFOREGROUNDLOCKTIMEOUT, 0, ctypes.byref(old_timeout), 0
                )
                logger.debug(f"Saved foreground lock timeout: {old_timeout.value}ms")

                # Set timeout to 0 (disable lock)
                ctypes.windll.user32.SystemParametersInfoW(
                    SPI_SETFOREGROUNDLOCKTIMEOUT, 0, None, SPIF_SENDCHANGE
                )
                logger.debug("Disabled foreground lock timeout")

                # "Alt" key trick to bypass foreground lock
                logger.debug("Sending Alt key trick to enable foreground switch")

                _null_ptr = ctypes.cast(
                    ctypes.pointer(wintypes.ULONG(0)),
                    ctypes.POINTER(wintypes.ULONG)
                )

                alt_input = INPUT()
                alt_input.type = INPUT_KEYBOARD
                alt_input.union.ki.wVk = 0x12  # VK_MENU (Alt)
                alt_input.union.ki.wScan = 0
                alt_input.union.ki.dwFlags = 0
                alt_input.union.ki.time = 0
                alt_input.union.ki.dwExtraInfo = _null_ptr

                ctypes.windll.user32.SendInput(1, ctypes.byref(alt_input), ctypes.sizeof(INPUT))

                # Release Alt
                alt_input.union.ki.dwFlags = KEYEVENTF_KEYUP
                ctypes.windll.user32.SendInput(1, ctypes.byref(alt_input), ctypes.sizeof(INPUT))

                # Allow this process to set foreground (magic constant ASFW_ANY = -1)
                ctypes.windll.user32.AllowSetForegroundWindow(-1)

                # Attach input processing mechanism to target thread
                attached = False
                if current_tid != target_tid:
                    logger.debug(f"Attaching thread {current_tid} to target thread {target_tid}")
                    attached = win32process.AttachThreadInput(current_tid, target_tid, True)

                # Restore and Show
                if win32gui.IsIconic(target_hwnd):
                    logger.debug("Window is minimized, restoring...")
                    win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                else:
                    win32gui.ShowWindow(target_hwnd, win32con.SW_SHOW)

                # Bring to front
                logger.debug(f"Calling BringWindowToTop and SetForegroundWindow for HWND {target_hwnd}")
                win32gui.BringWindowToTop(target_hwnd)
                win32gui.SetForegroundWindow(target_hwnd)

                # Detach
                if attached:
                    logger.debug("Detaching thread input")
                    win32process.AttachThreadInput(current_tid, target_tid, False)

                # Restore foreground lock timeout
                if old_timeout.value > 0:
                    ctypes.windll.user32.SystemParametersInfoW(
                        SPI_SETFOREGROUNDLOCKTIMEOUT, 0,
                        ctypes.cast(old_timeout.value, ctypes.c_void_p),
                        SPIF_SENDCHANGE
                    )
                    logger.debug(f"Restored foreground lock timeout to {old_timeout.value}ms")

                # Verify
                foreground_hwnd = win32gui.GetForegroundWindow()
                if foreground_hwnd == target_hwnd:
                    logger.info(f"Successfully forced window {target_hwnd} to foreground.")
                    return True
                else:
                    logger.debug(f"Window {target_hwnd} brought to top but "
                                f"GetForegroundWindow is {foreground_hwnd}")
                    # Sometimes main window is wrapper, but child took focus
                    _, fg_pid = win32process.GetWindowThreadProcessId(foreground_hwnd)
                    if fg_pid == pid:
                        logger.info(f"Foreground window HWND differs but PID matches ({pid}). Accepting.")
                        return True

            except Exception as e:
                logger.warning(f"Failed to force foreground: {e}")
                # Ensure detach and timeout restore happen even on error
                try:
                    if 'attached' in locals() and attached:
                        win32process.AttachThreadInput(current_tid, target_tid, False)
                    if 'old_timeout' in locals() and old_timeout.value > 0:
                        ctypes.windll.user32.SystemParametersInfoW(
                            SPI_SETFOREGROUNDLOCKTIMEOUT, 0,
                            ctypes.cast(old_timeout.value, ctypes.c_void_p),
                            SPIF_SENDCHANGE
                        )
                except Exception:
                    pass
        else:
            logger.debug(f"Attempt {attempt}: No visible windows found for PID {pid}")

        time.sleep(0.5)

    logger.debug(f"ensure_window_foreground timed out after {timeout}s for PID {pid}")
    return False


def is_pywinauto_available() -> bool:
    """Check if pywinauto is available."""
    return PYWINAUTO_AVAILABLE


def minimize_other_windows(target_pid: int, exclude_titles: list = None, exclude_process_name: str = None) -> int:
    """
    Minimize all visible windows except the target process and system windows.

    This ensures the game window is the only visible application, preventing
    Steam or other windows from appearing in screenshots.

    Args:
        target_pid: Process ID of the game to keep visible
        exclude_titles: Additional window titles to exclude from minimizing
        exclude_process_name: Process name pattern to exclude (e.g., "RDR2" will exclude RDR2.exe)

    Returns:
        int: Number of windows minimized
    """
    if exclude_titles is None:
        exclude_titles = []

    # System windows and processes to never minimize
    system_titles = [
        "Program Manager",  # Desktop
        "Microsoft Text Input Application",
        "NVIDIA GeForce Overlay",
        "Windows Input Experience",
        "",  # No title
    ]
    exclude_titles.extend(system_titles)

    # Build list of PIDs to exclude based on process name pattern
    exclude_pids = {target_pid}
    if exclude_process_name:
        # Remove .exe suffix for matching
        name_pattern = exclude_process_name.lower().replace('.exe', '')
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name'].lower().replace('.exe', '')
                    # Match if process name contains our pattern or vice versa
                    if name_pattern in proc_name or proc_name in name_pattern:
                        exclude_pids.add(proc.info['pid'])
                        logger.debug(f"Excluding process by name: {proc.info['name']} (PID {proc.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            logger.warning(f"Could not scan processes for exclusion: {e}")

    minimized_count = 0

    def callback(hwnd, _):
        nonlocal minimized_count
        try:
            # Skip invisible windows
            if not win32gui.IsWindowVisible(hwnd):
                return True

            # Skip already minimized windows
            if win32gui.IsIconic(hwnd):
                return True

            # Get window info
            _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            title = win32gui.GetWindowText(hwnd)

            # Skip target process and any processes matching excluded names
            if window_pid in exclude_pids:
                logger.debug(f"Keeping excluded window: '{title}' (PID {window_pid})")
                return True

            # Skip excluded titles
            if title in exclude_titles or not title.strip():
                return True

            # Skip windows with no title or very small windows (likely system)
            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            if width < 50 or height < 50:
                return True

            # Minimize this window
            try:
                logger.info(f"Minimizing: '{title}' (PID {window_pid})")
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                minimized_count += 1
            except Exception as e:
                logger.debug(f"Failed to minimize '{title}': {e}")

        except Exception as e:
            logger.debug(f"Error processing window: {e}")

        return True

    try:
        win32gui.EnumWindows(callback, None)
        logger.info(f"Minimized {minimized_count} other window(s)")
    except Exception as e:
        logger.error(f"minimize_other_windows failed: {e}")

    return minimized_count
