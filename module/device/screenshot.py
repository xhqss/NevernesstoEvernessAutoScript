"""
Screenshot methods for device control.
Supports ADB, Windows Graphics, BitBlt, and other methods.
"""

import io
import subprocess
import time
import numpy as np
from PIL import Image

from module.util.logger import logger
from module.util.file import get_adb_exe


class ScreenshotMethod:
    """Base class for screenshot capture methods."""

    def __init__(self, config=None):
        self.config = config or {}

    def grab(self):
        """Take a screenshot and return as numpy array (RGB)."""
        raise NotImplementedError

    @property
    def name(self):
        return self.__class__.__name__


class ADBScreenshot(ScreenshotMethod):
    """ADB screencap screenshot method."""

    def __init__(self, serial='127.0.0.1:5555', config=None):
        super().__init__(config)
        self.serial = serial
        self._adb = get_adb_exe()

    def grab(self):
        result = subprocess.run(
            [self._adb, '-s', self.serial, 'exec-out', 'screencap', '-p'],
            capture_output=True, timeout=15
        )
        if result.returncode != 0:
            raise RuntimeError(f'ADB screencap failed: {result.stderr}')
        img = Image.open(io.BytesIO(result.stdout))
        return np.array(img.convert('RGB'))


class WindowsGraphicsScreenshot(ScreenshotMethod):
    """Windows Graphics Capture (DXGI) - fastest method."""
    
    def __init__(self, hwnd=0, config=None):
        super().__init__(config)
        self.hwnd = hwnd
    
    def grab(self):
        import win32gui
        import win32ui
        import win32con
        
        if not self.hwnd:
            self.hwnd = win32gui.GetDesktopWindow()
        
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        w = right - left
        h = bottom - top
        
        hwnd_dc = win32gui.GetWindowDC(self.hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bitmap)
        
        save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)
        
        bmpinfo = bitmap.GetInfo()
        bmpstr = bitmap.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((h, w, 4))
        img = img[:, :, :3][:, :, ::-1]  # BGRA -> RGB
        
        win32gui.ReleaseDC(self.hwnd, hwnd_dc)
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.DeleteObject(bitmap.GetHandle())
        
        return img


class BitBltScreenshot(ScreenshotMethod):
    """BitBlt screenshot - slower fallback."""
    
    def __init__(self, hwnd=0, config=None):
        super().__init__(config)
        self.hwnd = hwnd
    
    def grab(self):
        import win32gui
        import win32ui
        import win32con
        
        if self.hwnd:
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        else:
            left = top = 0
            right = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            bottom = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        
        w, h = right - left, bottom - top
        
        hwnd_dc = win32gui.GetWindowDC(self.hwnd) if self.hwnd else win32gui.GetDC(0)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bitmap)
        
        save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)
        
        bmpinfo = bitmap.GetInfo()
        bmpstr = bitmap.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((h, w, 4))
        img = img[:, :, :3][:, :, ::-1]
        
        if self.hwnd:
            win32gui.ReleaseDC(self.hwnd, hwnd_dc)
        else:
            win32gui.ReleaseDC(0, hwnd_dc)
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.DeleteObject(bitmap.GetHandle())
        
        return img
