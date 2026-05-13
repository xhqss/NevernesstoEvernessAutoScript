"""
Device control module - handles screenshot capture and input interaction.
Supports both emulator (ADB) and PC (Windows window) modes.
Forces 1280x720 resolution on all platforms.
"""

import io
import time
import subprocess
import numpy as np
from PIL import Image

from module.base.utils import load_image, image_size
from module.util.logger import logger

TARGET_WIDTH = 1280
TARGET_HEIGHT = 720


class Device:
    """
    Unified device controller supporting ADB (emulator) and Windows (PC) modes.
    Forces 1280x720 resolution for all screenshots.
    """

    def __init__(self, config=None):
        self.config = config or {}
        self._hwnd = 0
        self._adb = None
        self._serial = ''
        self._screenshot_method = None
        self._interaction_method = None
        self._last_screenshot = None
        self._last_screenshot_time = 0

        # Determine platform
        self.platform = self.config.get('platform', 'adb')
        
    def connect(self, serial=None):
        """Connect to device."""
        if self.platform == 'adb':
            self._connect_adb(serial)
        elif self.platform == 'pc':
            self._connect_pc()
        else:
            raise ValueError(f'Unknown platform: {self.platform}')
    
    def _connect_adb(self, serial=None):
        """Connect to ADB device."""
        from adb_shell.adb_device import AdbDeviceTcp
        from adb_shell.auth.sign_pythonrsa import PythonRSASigner
        
        self._serial = serial or self.config.get('serial', '127.0.0.1:5555')
        logger.info(f'Connecting to ADB device: {self._serial}')
        
        try:
            result = subprocess.run(
                ['adb', 'connect', self._serial],
                capture_output=True, text=True, timeout=10
            )
            logger.info(f'ADB connect: {result.stdout.strip()}')
        except Exception as e:
            logger.warning(f'ADB connect failed: {e}')
        
        self._screenshot_method = 'adb'
        self._interaction_method = 'adb'
    
    def _connect_pc(self):
        """Connect to Windows PC window."""
        import win32gui
        import win32con
        
        title = self.config.get('window_title', '')
        window_class = self.config.get('window_class', '')
        
        if title:
            self._hwnd = win32gui.FindWindow(None, title)
        elif window_class:
            self._hwnd = win32gui.FindWindow(window_class, None)
        
        if not self._hwnd:
            logger.warning(f'Window not found, trying enum')
            def enum_callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    wtext = win32gui.GetWindowText(hwnd)
                    if wtext:
                        logger.info(f'  HWND: {hwnd}, Title: {wtext}')
            win32gui.EnumWindows(enum_callback, None)
        
        self._screenshot_method = 'windows'
        self._interaction_method = 'postmessage'
        logger.info(f'Connected to PC window, HWND: {self._hwnd}')
    
    def _resize_to_target(self, image):
        """Resize image to target 1280x720 resolution."""
        if image is None:
            return None
        h, w = image.shape[:2]
        if w == TARGET_WIDTH and h == TARGET_HEIGHT:
            return image.copy()
        import cv2
        logger.debug(f'Resizing screenshot from {w}x{h} to {TARGET_WIDTH}x{TARGET_HEIGHT}')
        return cv2.resize(image, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_LINEAR)

    def screenshot(self):
        """Take a screenshot and return as numpy array (RGB), forced to 1280x720."""
        if self.platform == 'adb':
            img = self._screenshot_adb()
        elif self.platform == 'pc':
            img = self._screenshot_windows()
        else:
            raise ValueError(f'Unknown screenshot method: {self._screenshot_method}')
        return self._resize_to_target(img)
    
    def _screenshot_adb(self):
        """Take screenshot via ADB."""
        try:
            result = subprocess.run(
                ['adb', '-s', self._serial, 'exec-out', 'screencap', '-p'],
                capture_output=True, timeout=15
            )
            if result.returncode != 0:
                raise RuntimeError(f'ADB screencap failed: {result.stderr}')
            img = Image.open(io.BytesIO(result.stdout))
            self._last_screenshot = np.array(img.convert('RGB'))
            return self._last_screenshot
        except Exception as e:
            logger.error(f'Screenshot failed: {e}')
            return self._last_screenshot
    
    def _screenshot_windows(self):
        """Take screenshot via Windows API."""
        try:
            import win32gui
            import win32ui
            import win32con
            
            if not self._hwnd:
                raise RuntimeError('No window handle')
            
            # Get window dimensions
            left, top, right, bottom = win32gui.GetWindowRect(self._hwnd)
            w = right - left
            h = bottom - top
            
            # Get window DC
            hwnd_dc = win32gui.GetWindowDC(self._hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            
            # Create bitmap
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(bitmap)
            
            # Print window (capture)
            save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)
            
            # Convert to numpy
            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)
            img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((h, w, 4))
            img = img[:, :, :3]  # Remove alpha
            img = img[:, :, ::-1]  # BGR to RGB
            
            # Cleanup
            win32gui.ReleaseDC(self._hwnd, hwnd_dc)
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.DeleteObject(bitmap.GetHandle())
            
            self._last_screenshot = img
            return img
        except Exception as e:
            logger.error(f'Windows screenshot failed: {e}')
            return self._last_screenshot
    
    def click(self, x, y):
        """Click at (x, y) coordinates."""
        if self.platform == 'adb':
            return self._click_adb(x, y)
        elif self.platform == 'pc':
            return self._click_postmessage(x, y)
    
    def _click_adb(self, x, y):
        """Click via ADB."""
        try:
            subprocess.run(
                ['adb', '-s', self._serial, 'shell', 'input', 'tap', str(x), str(y)],
                capture_output=True, timeout=5
            )
            return True
        except Exception as e:
            logger.error(f'ADB click failed: {e}')
            return False
    
    def _click_postmessage(self, x, y):
        """Click via PostMessage."""
        try:
            import win32api
            import win32con
            
            lparam = win32api.MAKELONG(x, y)
            win32api.SendMessage(self._hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(0.05)
            win32api.SendMessage(self._hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            return True
        except Exception as e:
            logger.error(f'PostMessage click failed: {e}')
            return False
    
    def swipe(self, x1, y1, x2, y2, duration=0.5):
        """Swipe from (x1,y1) to (x2,y2)."""
        if self.platform == 'adb':
            return self._swipe_adb(x1, y1, x2, y2, duration)
        # PC swipe not implemented yet
        return False
    
    def _swipe_adb(self, x1, y1, x2, y2, duration=0.5):
        """Swipe via ADB."""
        ms = int(duration * 1000)
        try:
            subprocess.run(
                ['adb', '-s', self._serial, 'shell', 'input', 'swipe',
                 str(x1), str(y1), str(x2), str(y2), str(ms)],
                capture_output=True, timeout=10
            )
            return True
        except Exception as e:
            logger.error(f'ADB swipe failed: {e}')
            return False
    
    def get_resolution(self):
        """Get device resolution (always 1280x720)."""
        return (TARGET_WIDTH, TARGET_HEIGHT)
    
    def __repr__(self):
        return f'Device(platform={self.platform}, serial={self._serial}, hwnd={self._hwnd})'
