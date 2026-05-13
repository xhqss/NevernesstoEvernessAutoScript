"""
Interaction methods for device input.
Supports ADB, PostMessage, PyDirectInput, and other methods.
"""

import subprocess
import time

from module.util.logger import logger
from module.util.file import get_adb_exe


class InteractionMethod:
    """Base class for interaction (input) methods."""

    def __init__(self, config=None):
        self.config = config or {}

    def click(self, x, y):
        """Click at (x, y)."""
        raise NotImplementedError

    def swipe(self, x1, y1, x2, y2, duration=0.5):
        """Swipe from (x1,y1) to (x2,y2)."""
        raise NotImplementedError

    def send_key(self, key):
        """Send keyboard key."""
        raise NotImplementedError

    @property
    def name(self):
        return self.__class__.__name__


class ADBInteraction(InteractionMethod):
    """ADB shell input interaction. Uses embedded ADB if available."""

    def __init__(self, serial='127.0.0.1:5555', config=None):
        super().__init__(config)
        self.serial = serial
        self._adb = get_adb_exe()

    def click(self, x, y):
        subprocess.run(
            [self._adb, '-s', self.serial, 'shell', 'input', 'tap', str(x), str(y)],
            capture_output=True, timeout=5
        )

    def swipe(self, x1, y1, x2, y2, duration=0.5):
        ms = int(duration * 1000)
        subprocess.run(
            [self._adb, '-s', self.serial, 'shell', 'input', 'swipe',
             str(x1), str(y1), str(x2), str(y2), str(ms)],
            capture_output=True, timeout=10
        )

    def send_key(self, key):
        subprocess.run(
            [self._adb, '-s', self.serial, 'shell', 'input', 'keyevent', str(key)],
            capture_output=True, timeout=5
        )


class PostMessageInteraction(InteractionMethod):
    """Windows PostMessage interaction."""
    
    def __init__(self, hwnd=0, config=None):
        super().__init__(config)
        self.hwnd = hwnd
    
    def click(self, x, y):
        import win32api
        import win32con
        
        lparam = win32api.MAKELONG(x, y)
        win32api.SendMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(0.03)
        win32api.SendMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
    
    def swipe(self, x1, y1, x2, y2, duration=0.5):
        import win32api
        import win32con
        
        steps = int(duration * 20)
        for i in range(steps + 1):
            t = i / steps
            x = int(x1 + (x2 - x1) * t)
            y = int(y1 + (y2 - y1) * t)
            lparam = win32api.MAKELONG(x, y)
            if i == 0:
                win32api.SendMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            else:
                win32api.SendMessage(self.hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lparam)
            time.sleep(duration / steps)
        win32api.SendMessage(self.hwnd, win32con.WM_LBUTTONUP, 0,
                             win32api.MAKELONG(x2, y2))
    
    def send_key(self, key):
        import win32api
        import win32con
        
        key_map = {
            'esc': win32con.VK_ESCAPE, 'return': win32con.VK_RETURN,
            'enter': win32con.VK_RETURN, 'space': win32con.VK_SPACE,
            'tab': win32con.VK_TAB, 'backspace': win32con.VK_BACK,
            'up': win32con.VK_UP, 'down': win32con.VK_DOWN,
            'left': win32con.VK_LEFT, 'right': win32con.VK_RIGHT,
        }
        
        vk = key_map.get(key.lower())
        if vk:
            win32api.SendMessage(self.hwnd, win32con.WM_KEYDOWN, vk, 0)
            win32api.SendMessage(self.hwnd, win32con.WM_KEYUP, vk, 0)


class PyDirectInteraction(InteractionMethod):
    """pydirectinput interaction for PC games."""
    
    def __init__(self, config=None):
        super().__init__(config)
        import pydirectinput
        self.di = pydirectinput
    
    def click(self, x, y):
        self.di.moveTo(x, y)
        self.di.click()
    
    def swipe(self, x1, y1, x2, y2, duration=0.5):
        self.di.moveTo(x1, y1)
        self.di.drag(x2 - x1, y2 - y1, duration=duration)
    
    def send_key(self, key):
        self.di.press(key)
