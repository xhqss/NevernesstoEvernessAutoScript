"""
Device Manager - manages screenshot capture and interaction methods.
Adapted from ok-script ok/device/DeviceManager.py
Forces 1280x720 resolution on all platforms.
"""

import time

import numpy as np

from module.util.logger import logger
from module.util.process import (
    find_window_by_title, find_window_by_class,
    get_window_title, get_window_rect
)


TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
TARGET_RESOLUTION = (TARGET_WIDTH, TARGET_HEIGHT)


class DeviceManager:
    """
    Manages device capture and interaction for automation.

    Auto-detects the best available capture/interaction methods.
    Forces 1280x720 resolution for all screenshots.
    """

    def __init__(self, config=None, exit_event=None, global_config=None):
        self.config = config or {}
        self.exit_event = exit_event
        self.global_config = global_config

        self._capture = None
        self._interaction = None
        self._hwnd = 0
        self._hwnd_window = 0
        self._serial = ''

        self.width = TARGET_WIDTH
        self.height = TARGET_HEIGHT

        self._last_screenshot = None
        self._last_screenshot_time = 0

        self._init_device()

    def _init_device(self):
        """Initialize device based on platform config."""
        platform = self.config.get('Device', {}).get('Platform', 'auto')
        if isinstance(platform, dict):
            platform = platform.get('value', 'auto')

        if platform == 'auto':
            self._init_auto()
        elif platform == 'pc':
            self._init_pc()
        elif platform == 'adb':
            self._init_adb()

    def _init_auto(self):
        """Auto-detect the best device configuration."""
        # Try PC window first if a window title is configured
        window_title = self.config.get('Window', {}).get('Title', '')
        if isinstance(window_title, dict):
            window_title = window_title.get('value', '')

        if window_title:
            self._init_pc()
            if self._hwnd:
                return

        # Try ADB
        serial = self.config.get('Device', {}).get('Serial', 'auto')
        if isinstance(serial, dict):
            serial = serial.get('value', 'auto')

        if serial and serial != 'auto':
            self._init_adb()
            return

        # Fall back to PC desktop window
        self._init_pc()

    def _init_pc(self):
        """Initialize PC (Windows window) device."""
        window_title = self.config.get('Window', {}).get('Title', '')
        if isinstance(window_title, dict):
            window_title = window_title.get('value', '')
        window_class = self.config.get('Window', {}).get('Class', '')
        if isinstance(window_class, dict):
            window_class = window_class.get('value', '')

        if window_title:
            self._hwnd = find_window_by_title(window_title)
        elif window_class:
            self._hwnd = find_window_by_class(window_class)

        if self._hwnd:
            self._hwnd_window = self._hwnd
            title = get_window_title(self._hwnd)
            rect = get_window_rect(self._hwnd)
            logger.info(f'PC window found: HWND={self._hwnd}, Title="{title}", Rect={rect}')
        else:
            logger.warning('PC window not found, using desktop')

        # Select capture method
        self._capture = self._select_capture_pc()
        self._interaction = self._select_interaction_pc()

    def _get_adb_binary(self):
        """Get ADB binary path, preferring embedded toolkit ADB."""
        from module.util.file import get_adb_exe
        return get_adb_exe()

    def _init_adb(self):
        """Initialize ADB device."""
        serial = self.config.get('Device', {}).get('Serial', '127.0.0.1:5555')
        if isinstance(serial, dict):
            serial = serial.get('value', '127.0.0.1:5555')
        self._serial = serial

        import subprocess
        adb_bin = self._get_adb_binary()
        try:
            result = subprocess.run(
                [adb_bin, 'connect', self._serial],
                capture_output=True, text=True, timeout=10
            )
            logger.info(f'ADB connect ({adb_bin}): {result.stdout.strip()}')
        except Exception as e:
            logger.warning(f'ADB connect failed: {e}')

        self._capture = self._select_capture_adb()
        self._interaction = self._select_interaction_adb()

    def _select_capture_pc(self):
        """Select best capture method for PC."""
        screenshot_method = self.config.get('Device', {}).get('ScreenshotMethod', 'auto')
        if isinstance(screenshot_method, dict):
            screenshot_method = screenshot_method.get('value', 'auto')

        if screenshot_method == 'auto':
            from module.util.process import windows_graphics_available
            if windows_graphics_available():
                from module.device.screenshot import WindowsGraphicsScreenshot
                logger.info('Selected WindowsGraphics screenshot')
                return WindowsGraphicsScreenshot(hwnd=self._hwnd)
            else:
                from module.device.screenshot import BitBltScreenshot
                logger.info('Selected BitBlt screenshot')
                return BitBltScreenshot(hwnd=self._hwnd)
        elif screenshot_method == 'WindowsGraphics':
            from module.device.screenshot import WindowsGraphicsScreenshot
            return WindowsGraphicsScreenshot(hwnd=self._hwnd)
        elif screenshot_method == 'BitBlt':
            from module.device.screenshot import BitBltScreenshot
            return BitBltScreenshot(hwnd=self._hwnd)
        elif screenshot_method == 'ADB':
            return self._select_capture_adb()
        else:
            from module.device.screenshot import WindowsGraphicsScreenshot
            return WindowsGraphicsScreenshot(hwnd=self._hwnd)

    def _select_capture_adb(self):
        """Select capture method for ADB."""
        from module.device.screenshot import ADBScreenshot
        return ADBScreenshot(serial=self._serial)

    def _select_interaction_pc(self):
        """Select best interaction method for PC."""
        control_method = self.config.get('Device', {}).get('ControlMethod', 'auto')
        if isinstance(control_method, dict):
            control_method = control_method.get('value', 'auto')

        if control_method == 'auto' or control_method == 'PostMessage':
            from module.device.control import PostMessageInteraction
            return PostMessageInteraction(hwnd=self._hwnd)
        elif control_method == 'PyDirectInput':
            from module.device.control import PyDirectInteraction
            return PyDirectInteraction()
        elif control_method == 'ADB':
            return self._select_interaction_adb()
        else:
            from module.device.control import PostMessageInteraction
            return PostMessageInteraction(hwnd=self._hwnd)

    def _select_interaction_adb(self):
        """Select interaction method for ADB."""
        from module.device.control import ADBInteraction
        return ADBInteraction(serial=self._serial)

    def screenshot(self):
        """Take a screenshot and force to 1280x720 resolution."""
        if self._capture is None:
            logger.error('No capture method available')
            return self._last_screenshot

        try:
            img = self._capture.grab()
            if img is not None:
                img = self._resize_to_target(img)
            self._last_screenshot = img
            self._last_screenshot_time = time.time()
            return img
        except Exception as e:
            logger.error(f'Screenshot failed: {e}')
            return self._last_screenshot

    def _resize_to_target(self, image):
        """Resize image to target 1280x720 resolution if needed."""
        if image is None:
            return None
        h, w = image.shape[:2]
        if w == TARGET_WIDTH and h == TARGET_HEIGHT:
            return image.copy()
        import cv2
        logger.debug(f'Resizing screenshot from {w}x{h} to {TARGET_WIDTH}x{TARGET_HEIGHT}')
        return cv2.resize(image, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_LINEAR)

    @property
    def hwnd_window(self):
        """Get the game window handle."""
        return self._hwnd_window or self._hwnd

    @property
    def is_pc(self):
        return self._hwnd != 0 and not self._serial

    @property
    def is_adb(self):
        return bool(self._serial)

    @property
    def capture(self):
        return self._capture

    @property
    def interaction(self):
        return self._interaction

    def click(self, x, y):
        """Click at coordinates (in 1280x720 space)."""
        if self._interaction:
            return self._interaction.click(x, y)
        return False

    def swipe(self, x1, y1, x2, y2, duration=0.5):
        """Swipe from (x1,y1) to (x2,y2)."""
        if self._interaction:
            return self._interaction.swipe(x1, y1, x2, y2, duration)
        return False

    def send_key(self, key):
        """Send keyboard key."""
        if self._interaction:
            return self._interaction.send_key(key)
        return False

    def reconnect(self):
        """Re-establish device connection."""
        logger.info('Reconnecting device...')
        if self.is_adb:
            self._init_adb()
        elif self.is_pc:
            self._init_pc()
        return True

    def latency_profile(self) -> dict:
        """Return device capability profile for timing compensation."""
        return {
            "type": "adb" if self.is_adb else "pc",
            "screenshot_latency_ms": 45 if self.is_adb else 15,
            "screenshot_jitter_ms": 10 if self.is_adb else 5,
            "input_latency_ms": 30 if self.is_adb else 10,
            "input_jitter_ms": 8 if self.is_adb else 3,
            "refresh_rate": 60,
            "resolution": [TARGET_WIDTH, TARGET_HEIGHT],
        }

    def __repr__(self):
        return (f'DeviceManager(pc={self.is_pc}, adb={self.is_adb}, '
                f'hwnd={self._hwnd}, serial={self._serial}, '
                f'resolution={TARGET_WIDTH}x{TARGET_HEIGHT})')
