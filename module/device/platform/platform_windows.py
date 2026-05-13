"""
Windows platform utilities - window management, process management.
"""

import ctypes
import re
import subprocess

import psutil

from module.device.platform.emulator_base import EmulatorManagerBase
from module.util.logger import logger


def get_focused_window():
    """Get foreground window handle."""
    return ctypes.windll.user32.GetForegroundWindow()


def set_focus_window(hwnd):
    """Set focus to a window."""
    ctypes.windll.user32.SetForegroundWindow(hwnd)


def minimize_window(hwnd):
    """Minimize a window."""
    ctypes.windll.user32.ShowWindow(hwnd, 6)


def get_window_title(hwnd):
    """Get window title as string."""
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def flash_window(hwnd, flash=True):
    """Flash a window in taskbar."""
    ctypes.windll.user32.FlashWindow(hwnd, flash)


def find_window_by_title(title, partial_match=True):
    """Find window handle by title."""
    import win32gui
    
    hwnds = []
    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            wtext = win32gui.GetWindowText(hwnd)
            if partial_match:
                if title.lower() in wtext.lower():
                    hwnds.append(hwnd)
            else:
                if title == wtext:
                    hwnds.append(hwnd)
    
    win32gui.EnumWindows(enum_callback, None)
    return hwnds[0] if hwnds else 0


def find_window_by_class(window_class):
    """Find window handle by class name."""
    import win32gui
    return win32gui.FindWindow(window_class, None)


class PlatformWindows(EmulatorManagerBase):
    """Windows platform operations."""
    
    @classmethod
    def execute(cls, command):
        """Execute a command."""
        logger.info(f'Execute: {command}')
        command = command.replace('\\', '/')
        return subprocess.Popen(command, close_fds=True, start_new_session=True)
    
    @classmethod
    def kill_process_by_regex(cls, regex: str) -> int:
        """Kill processes matching regex."""
        import psutil
        count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if re.search(regex, cmdline, re.IGNORECASE):
                    logger.info(f'Kill process: {cmdline}')
                    proc.kill()
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return count
