"""
Input Controller Module - Windows SendInput API
Provides low-level mouse and keyboard input automation.

Ported from KATANA Gemma v0.2
Author: SATYAJIT BHUYAN (satyajit.bhuyan@intel.com)
"""

import time
import ctypes
from ctypes import wintypes
import logging

import win32api
import win32con
import pyautogui

logger = logging.getLogger(__name__)

# Disable PyAutoGUI failsafe
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.01


# =============================================================================
# Windows API Structures for SendInput
# =============================================================================

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION)
    ]


# =============================================================================
# Constants
# =============================================================================

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_WHEEL = 0x0800

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# Virtual key codes
VK_CODES = {
    'left': 0x01, 'right': 0x02, 'middle': 0x04,
    'backspace': 0x08, 'tab': 0x09, 'enter': 0x0D, 'shift': 0x10,
    'ctrl': 0x11, 'alt': 0x12, 'pause': 0x13, 'caps_lock': 0x14,
    'escape': 0x1B, 'space': 0x20, 'page_up': 0x21, 'page_down': 0x22,
    'end': 0x23, 'home': 0x24, 'left_arrow': 0x25, 'up_arrow': 0x26,
    'right_arrow': 0x27, 'down_arrow': 0x28, 'insert': 0x2D, 'delete': 0x2E,
    'win': 0x5B, 'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
    'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77, 'f9': 0x78,
    'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B
}


# =============================================================================
# Input Controller Class
# =============================================================================

class InputController:
    """Enhanced input controller using Windows SendInput API."""

    def __init__(self):
        self.user32 = ctypes.windll.user32
        # Reusable null pointer for dwExtraInfo to reduce allocations
        self._null_ptr = ctypes.cast(
            ctypes.pointer(wintypes.ULONG(0)),
            ctypes.POINTER(wintypes.ULONG)
        )
        logger.info(f"InputController initialized: {self.screen_width}x{self.screen_height}")

    @property
    def screen_width(self) -> int:
        """Get current screen width."""
        return self.user32.GetSystemMetrics(0)

    @property
    def screen_height(self) -> int:
        """Get current screen height."""
        return self.user32.GetSystemMetrics(1)

    def _normalize_coordinates(self, x: int, y: int) -> tuple:
        """Convert screen coordinates to normalized coordinates (0-65535)."""
        width = self.screen_width
        height = self.screen_height
        normalized_x = int(x * 65535 / width)
        normalized_y = int(y * 65535 / height)
        return normalized_x, normalized_y

    def move_mouse(self, x: int, y: int, smooth: bool = True, duration: float = 0.3) -> bool:
        """
        Move mouse to absolute position using SendInput.

        Args:
            x, y: Screen coordinates
            smooth: If True, move smoothly; if False, move instantly
            duration: Duration of smooth movement in seconds
        """
        try:
            if smooth and duration > 0:
                # Get current position
                current_x, current_y = win32api.GetCursorPos()

                # Cap steps at 50 to reduce CPU load
                steps = min(50, max(10, int(duration * 60)))

                for i in range(steps + 1):
                    progress = i / steps
                    # Ease in-out cubic
                    if progress < 0.5:
                        eased = 4 * progress * progress * progress
                    else:
                        eased = 1 - pow(-2 * progress + 2, 3) / 2

                    inter_x = int(current_x + (x - current_x) * eased)
                    inter_y = int(current_y + (y - current_y) * eased)

                    self._move_mouse_absolute(inter_x, inter_y)
                    time.sleep(duration / steps)
            else:
                self._move_mouse_absolute(x, y)

            logger.debug(f"Mouse moved to ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Mouse move failed: {e}")
            return False

    def _move_mouse_absolute(self, x: int, y: int):
        """Move mouse using SendInput with absolute positioning."""
        norm_x, norm_y = self._normalize_coordinates(x, y)

        mouse_input = MOUSEINPUT()
        mouse_input.dx = norm_x
        mouse_input.dy = norm_y
        mouse_input.mouseData = 0
        mouse_input.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        mouse_input.time = 0
        mouse_input.dwExtraInfo = self._null_ptr

        input_struct = INPUT()
        input_struct.type = INPUT_MOUSE
        input_struct.union.mi = mouse_input

        result = self.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))

        if result == 0:
            # Fallback to win32api
            win32api.SetCursorPos((x, y))

    def click_mouse(self, x: int, y: int, button: str = 'left',
                    move_duration: float = 0.3, click_delay: float = 0.1) -> bool:
        """
        Click mouse at position using SendInput.

        Args:
            x, y: Screen coordinates
            button: 'left', 'right', or 'middle'
            move_duration: Time to move to position
            click_delay: Delay before clicking
        """
        try:
            # Move to position
            self.move_mouse(x, y, smooth=True, duration=move_duration)

            # Wait before clicking
            if click_delay > 0:
                time.sleep(click_delay)

            # Determine button flags
            if button == 'left':
                down_flag = MOUSEEVENTF_LEFTDOWN
                up_flag = MOUSEEVENTF_LEFTUP
            elif button == 'right':
                down_flag = MOUSEEVENTF_RIGHTDOWN
                up_flag = MOUSEEVENTF_RIGHTUP
            elif button == 'middle':
                down_flag = MOUSEEVENTF_MIDDLEDOWN
                up_flag = MOUSEEVENTF_MIDDLEUP
            else:
                logger.error(f"Invalid button: {button}")
                return False

            # Mouse down
            self._send_mouse_event(down_flag)
            time.sleep(0.05)

            # Mouse up
            self._send_mouse_event(up_flag)

            logger.info(f"{button.capitalize()} click at ({x}, {y})")
            return True

        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    def hold_click(self, x: int, y: int, button: str = 'left',
                   duration: float = 1.0, move_duration: float = 0.3) -> bool:
        """
        Hold mouse button at position for specified duration.

        Args:
            x, y: Screen coordinates
            button: 'left', 'right', or 'middle'
            duration: How long to hold the button in seconds
            move_duration: Time to move to position before clicking
        """
        try:
            # Move to position
            self.move_mouse(x, y, smooth=True, duration=move_duration)
            time.sleep(0.1)

            # Determine button flags
            if button == 'left':
                down_flag = MOUSEEVENTF_LEFTDOWN
                up_flag = MOUSEEVENTF_LEFTUP
            elif button == 'right':
                down_flag = MOUSEEVENTF_RIGHTDOWN
                up_flag = MOUSEEVENTF_RIGHTUP
            elif button == 'middle':
                down_flag = MOUSEEVENTF_MIDDLEDOWN
                up_flag = MOUSEEVENTF_MIDDLEUP
            else:
                logger.error(f"Invalid button for hold_click: {button}")
                return False

            # Mouse down
            self._send_mouse_event(down_flag)

            # Hold for specified duration
            time.sleep(duration)

            # Mouse up
            self._send_mouse_event(up_flag)

            logger.info(f"Held {button} click at ({x}, {y}) for {duration}s")
            return True

        except Exception as e:
            logger.error(f"Hold click failed: {e}")
            return False

    def _send_mouse_event(self, flags: int):
        """Send a mouse event using SendInput."""
        mouse_input = MOUSEINPUT()
        mouse_input.dx = 0
        mouse_input.dy = 0
        mouse_input.mouseData = 0
        mouse_input.dwFlags = flags
        mouse_input.time = 0
        mouse_input.dwExtraInfo = self._null_ptr

        input_struct = INPUT()
        input_struct.type = INPUT_MOUSE
        input_struct.union.mi = mouse_input

        result = self.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))

        if result == 0:
            # Fallback to win32api
            if flags == MOUSEEVENTF_LEFTDOWN:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
            elif flags == MOUSEEVENTF_LEFTUP:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
            elif flags == MOUSEEVENTF_RIGHTDOWN:
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0)
            elif flags == MOUSEEVENTF_RIGHTUP:
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0)

    def double_click(self, x: int, y: int, button: str = 'left',
                     move_duration: float = 0.3) -> bool:
        """Double-click at position."""
        try:
            # Move to position
            self.move_mouse(x, y, smooth=True, duration=move_duration)
            time.sleep(0.1)

            # Determine button flags
            if button == 'left':
                down_flag = MOUSEEVENTF_LEFTDOWN
                up_flag = MOUSEEVENTF_LEFTUP
            elif button == 'right':
                down_flag = MOUSEEVENTF_RIGHTDOWN
                up_flag = MOUSEEVENTF_RIGHTUP
            else:
                logger.error(f"Invalid button for double-click: {button}")
                return False

            # First click
            self._send_mouse_event(down_flag)
            time.sleep(0.05)
            self._send_mouse_event(up_flag)
            time.sleep(0.05)

            # Second click
            self._send_mouse_event(down_flag)
            time.sleep(0.05)
            self._send_mouse_event(up_flag)

            logger.info(f"Double-clicked {button} at ({x}, {y})")
            return True

        except Exception as e:
            logger.error(f"Double-click failed: {e}")
            return False

    def drag(self, x1: int, y1: int, x2: int, y2: int,
             button: str = 'left', duration: float = 1.0) -> bool:
        """
        Drag from one position to another.

        Args:
            x1, y1: Starting coordinates
            x2, y2: Ending coordinates
            button: Mouse button to use
            duration: Duration of drag in seconds
        """
        try:
            # Move to start position
            self.move_mouse(x1, y1, smooth=True, duration=0.3)
            time.sleep(0.1)

            # Determine button flags
            if button == 'left':
                down_flag = MOUSEEVENTF_LEFTDOWN
                up_flag = MOUSEEVENTF_LEFTUP
            elif button == 'right':
                down_flag = MOUSEEVENTF_RIGHTDOWN
                up_flag = MOUSEEVENTF_RIGHTUP
            else:
                logger.error(f"Invalid button for drag: {button}")
                return False

            # Press button down
            self._send_mouse_event(down_flag)
            time.sleep(0.1)

            # Move to end position while holding button
            self.move_mouse(x2, y2, smooth=True, duration=duration)
            time.sleep(0.1)

            # Release button
            self._send_mouse_event(up_flag)

            logger.info(f"Dragged from ({x1}, {y1}) to ({x2}, {y2})")
            return True

        except Exception as e:
            logger.error(f"Drag failed: {e}")
            return False

    def scroll(self, x: int, y: int, clicks: int, direction: str = 'up') -> bool:
        """Scroll at position."""
        try:
            # Move to position first
            self.move_mouse(x, y, smooth=False, duration=0)
            time.sleep(0.05)

            # Calculate scroll amount (120 units per click)
            scroll_amount = 120 if direction == 'up' else -120

            for _ in range(clicks):
                mouse_input = MOUSEINPUT()
                mouse_input.dx = 0
                mouse_input.dy = 0
                mouse_input.mouseData = scroll_amount
                mouse_input.dwFlags = MOUSEEVENTF_WHEEL
                mouse_input.time = 0
                mouse_input.dwExtraInfo = self._null_ptr

                input_struct = INPUT()
                input_struct.type = INPUT_MOUSE
                input_struct.union.mi = mouse_input

                self.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))
                time.sleep(0.02)

            logger.debug(f"Scrolled {direction} {clicks} times")
            return True

        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return False

    def press_key(self, key_name: str) -> bool:
        """Press and release a key using SendInput."""
        try:
            # Normalize key name
            key_lower = key_name.lower().replace('_', '')

            # Map common variations
            key_map = {
                'esc': 'escape',
                'return': 'enter',
                'up': 'up_arrow',
                'down': 'down_arrow',
                'left': 'left_arrow',
                'right': 'right_arrow',
                'pageup': 'page_up',
                'pagedown': 'page_down',
                'capslock': 'caps_lock'
            }

            key_lower = key_map.get(key_lower, key_lower)

            # Get virtual key code
            if key_lower in VK_CODES:
                vk_code = VK_CODES[key_lower]
            elif len(key_name) == 1:
                # Single character
                vk_code = ord(key_name.upper())
            else:
                logger.warning(f"Unknown key '{key_name}', trying pyautogui fallback")
                try:
                    pyautogui.press(key_name)
                    logger.info(f"Pressed key via pyautogui: {key_name}")
                    return True
                except Exception:
                    logger.error(f"Unknown key and fallback failed: {key_name}")
                    return False

            # Key down
            result1 = self._send_key_event(vk_code, False)
            time.sleep(0.1)  # Longer press duration (100ms) for better game compatibility

            # Key up
            result2 = self._send_key_event(vk_code, True)

            # Check if SendInput succeeded
            if result1 == 0 or result2 == 0:
                logger.warning(f"SendInput failed for key '{key_name}', using pyautogui fallback")
                try:
                    pyautogui.press(key_name)
                    logger.info(f"Pressed key via pyautogui: {key_name}")
                    return True
                except Exception as e:
                    logger.error(f"Fallback also failed: {e}")
                    return False

            logger.info(f"Pressed key: {key_name} (VK: 0x{vk_code:02X})")
            return True

        except Exception as e:
            logger.error(f"Key press failed: {e}")
            return False

    def hold_key(self, key_name: str, duration: float = 1.0) -> bool:
        """
        Hold a key for specified duration.

        Args:
            key_name: Name of key to hold (e.g., 'enter', 'space', 'f5')
            duration: How long to hold the key in seconds
        """
        try:
            # Normalize key name
            key_lower = key_name.lower().replace('_', '')

            # Map common variations
            key_map = {
                'esc': 'escape',
                'return': 'enter',
                'up': 'up_arrow',
                'down': 'down_arrow',
                'left': 'left_arrow',
                'right': 'right_arrow',
                'pageup': 'page_up',
                'pagedown': 'page_down',
                'capslock': 'caps_lock'
            }

            key_lower = key_map.get(key_lower, key_lower)

            # Get VK code
            if key_lower in VK_CODES:
                vk_code = VK_CODES[key_lower]
            elif len(key_lower) == 1 and key_lower.isalnum():
                vk_code = ord(key_lower.upper())
            else:
                logger.error(f"Unknown key for hold: {key_name}")
                return False

            # Key down
            self._send_key_event(vk_code, False)

            # Hold for specified duration
            time.sleep(duration)

            # Key up
            self._send_key_event(vk_code, True)

            logger.info(f"Held key: {key_name} for {duration}s (VK: 0x{vk_code:02X})")
            return True

        except Exception as e:
            logger.error(f"Hold key failed: {e}")
            return False

    def _send_key_event(self, vk_code: int, key_up: bool = False) -> int:
        """Send a keyboard event using SendInput."""
        # Get hardware scan code for the virtual key
        scan_code = self.user32.MapVirtualKeyW(vk_code, 0)

        kbd_input = KEYBDINPUT()
        kbd_input.wVk = vk_code
        kbd_input.wScan = scan_code
        kbd_input.dwFlags = KEYEVENTF_KEYUP if key_up else 0
        kbd_input.time = 0
        kbd_input.dwExtraInfo = self._null_ptr

        input_struct = INPUT()
        input_struct.type = INPUT_KEYBOARD
        input_struct.union.ki = kbd_input

        result = self.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))
        return result

    def press_hotkey(self, keys: list) -> bool:
        """
        Press multiple keys together (hotkey combination).

        Args:
            keys: List of key names to press together (e.g., ['ctrl', 's'])
        """
        try:
            # Normalize and get VK codes
            vk_codes = []
            for key in keys:
                key_lower = key.lower().replace('_', '')
                key_map = {
                    'esc': 'escape',
                    'return': 'enter',
                    'up': 'up_arrow',
                    'down': 'down_arrow',
                    'left': 'left_arrow',
                    'right': 'right_arrow'
                }
                key_lower = key_map.get(key_lower, key_lower)

                if key_lower in VK_CODES:
                    vk_codes.append(VK_CODES[key_lower])
                elif len(key) == 1:
                    vk_codes.append(ord(key.upper()))
                else:
                    logger.error(f"Unknown key in hotkey: {key}")
                    return False

            # Press all keys down
            for vk_code in vk_codes:
                self._send_key_event(vk_code, False)
                time.sleep(0.01)

            time.sleep(0.05)

            # Release all keys in reverse order
            for vk_code in reversed(vk_codes):
                self._send_key_event(vk_code, True)
                time.sleep(0.01)

            logger.info(f"Pressed hotkey: {'+'.join(keys)}")
            return True

        except Exception as e:
            logger.error(f"Hotkey press failed: {e}")
            return False

    def type_text(self, text: str, char_delay: float = 0.05) -> bool:
        """Type text character by character."""
        try:
            for char in text:
                if char == '\n':
                    self.press_key('enter')
                elif char == '\t':
                    self.press_key('tab')
                else:
                    # Use pyautogui for complex characters
                    pyautogui.write(char, interval=0)

                if char_delay > 0:
                    time.sleep(char_delay)

            logger.info(f"Typed text: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Type text failed: {e}")
            return False
