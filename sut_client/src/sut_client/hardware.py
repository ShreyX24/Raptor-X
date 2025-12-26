"""
Hardware detection utilities for SUT Client
Provides CPU model detection, cleanup for display names, and DPI awareness.

DPI awareness added from KATANA Gemma v0.2
"""

import platform
import re
import ctypes
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# DPI Awareness (from KATANA Gemma v0.2)
# =============================================================================

def set_dpi_awareness():
    """
    Set DPI awareness to get real physical screen resolution.
    Without this, GetSystemMetrics returns scaled coordinates on HiDPI displays.

    Should be called early, before any resolution queries or input operations.
    """
    if platform.system() != "Windows":
        return

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


def get_screen_resolution() -> tuple:
    """
    Get current screen resolution.

    Returns:
        tuple: (width, height)
    """
    if platform.system() != "Windows":
        return (0, 0)

    try:
        user32 = ctypes.windll.user32
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
        return (width, height)
    except Exception as e:
        logger.warning(f"Failed to get screen resolution: {e}")
        return (0, 0)


# =============================================================================
# CPU Detection (Original PM)
# =============================================================================


def get_cpu_model() -> str:
    """
    Get CPU model name.

    On Windows, uses WMI for accurate CPU name.
    Falls back to platform.processor() on other systems.

    Returns:
        Cleaned CPU model name (e.g., "Intel Core Ultra 9 285K")
    """
    cpu_name = ""

    if platform.system() == "Windows":
        try:
            import wmi
            w = wmi.WMI()
            processors = w.Win32_Processor()
            if processors:
                cpu_name = processors[0].Name
                logger.debug(f"WMI CPU name: {cpu_name}")
        except ImportError:
            logger.warning("WMI module not available, falling back to platform.processor()")
            cpu_name = platform.processor()
        except Exception as e:
            logger.warning(f"WMI CPU detection failed: {e}, falling back to platform.processor()")
            cpu_name = platform.processor()
    else:
        # Linux/Mac fallback
        cpu_name = platform.processor()

    if not cpu_name:
        cpu_name = "Unknown CPU"

    return clean_cpu_name(cpu_name)


def clean_cpu_name(raw_name: str) -> str:
    """
    Clean up verbose CPU names for display.

    Removes:
    - (R), (TM), (r), (tm) trademark symbols
    - "Processor" suffix
    - "CPU" suffix
    - Extra whitespace
    - "@ X.XXGHz" frequency suffix

    Examples:
        "Intel(R) Core(TM) Ultra 9 285K" -> "Intel Core Ultra 9 285K"
        "AMD Ryzen 9 9950X 16-Core Processor" -> "AMD Ryzen 9 9950X 16-Core"
        "Intel(R) Core(TM) i7-12700K CPU @ 3.60GHz" -> "Intel Core i7-12700K"

    Args:
        raw_name: Raw CPU name from WMI or platform

    Returns:
        Cleaned CPU name
    """
    if not raw_name:
        return "Unknown CPU"

    cleaned = raw_name

    # Remove trademark symbols
    cleaned = re.sub(r'\(R\)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\(TM\)', '', cleaned, flags=re.IGNORECASE)

    # Remove frequency suffix (@ X.XXGHz)
    cleaned = re.sub(r'\s*@\s*[\d.]+\s*[GM]Hz', '', cleaned, flags=re.IGNORECASE)

    # Remove "Processor" and "CPU" suffixes
    cleaned = re.sub(r'\s+Processor\s*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+CPU\s*$', '', cleaned, flags=re.IGNORECASE)

    # Normalize whitespace
    cleaned = ' '.join(cleaned.split())

    return cleaned.strip()


def get_short_cpu_name(cpu_model: str) -> str:
    """
    Get a shortened version of CPU name for display name suggestions.

    Extracts the most identifying part of the CPU name.

    Examples:
        "Intel Core Ultra 9 285K" -> "Ultra 9 285K"
        "AMD Ryzen 9 9950X 16-Core" -> "Ryzen 9 9950X"
        "Intel Core i7-12700K" -> "i7-12700K"

    Args:
        cpu_model: Cleaned CPU model name

    Returns:
        Short form for display name suggestions
    """
    if not cpu_model:
        return "Unknown"

    # Intel Core Ultra series (newest)
    match = re.search(r'Ultra\s+\d+\s+\w+', cpu_model, re.IGNORECASE)
    if match:
        return match.group(0)

    # Intel Core i-series (i3, i5, i7, i9)
    match = re.search(r'i[3579]-\w+', cpu_model, re.IGNORECASE)
    if match:
        return match.group(0)

    # AMD Ryzen series
    match = re.search(r'Ryzen\s+\d+\s+\w+', cpu_model, re.IGNORECASE)
    if match:
        return match.group(0)

    # AMD Threadripper
    match = re.search(r'Threadripper\s+\w+', cpu_model, re.IGNORECASE)
    if match:
        return match.group(0)

    # Fallback: return last meaningful parts
    parts = cpu_model.split()
    if len(parts) >= 2:
        return ' '.join(parts[-2:])

    return cpu_model


def get_gpu_model() -> str:
    """
    Get GPU model name (for future use).

    On Windows, uses WMI for GPU detection.

    Returns:
        GPU model name or "Unknown GPU"
    """
    if platform.system() != "Windows":
        return "Unknown GPU"

    try:
        import wmi
        w = wmi.WMI()
        gpus = w.Win32_VideoController()
        if gpus:
            # Return the first discrete GPU if available
            for gpu in gpus:
                name = gpu.Name
                # Skip integrated graphics if discrete GPU exists
                if len(gpus) > 1 and any(x in name.lower() for x in ['intel', 'microsoft basic']):
                    continue
                return name
            # Fallback to first GPU
            return gpus[0].Name
    except Exception as e:
        logger.warning(f"GPU detection failed: {e}")

    return "Unknown GPU"
