"""
Process utilities - mutex, GPU memory, window utilities.
Adapted from ok-script ok/util/process.py and ok/util/window.py
"""

import os
import sys
import ctypes
import subprocess

from module.util.logger import logger


def check_mutex(name='al-script'):
    """Ensure only one instance of the app is running."""
    import ctypes
    try:
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, name)
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            logger.warning('Another instance is already running')
            return False
        return True
    except Exception as e:
        logger.error(f'Mutex check failed: {e}')
        return True  # Continue running if check fails


def get_first_gpu_free_memory_mib():
    """Get free GPU memory in MiB using nvidia-smi."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            return int(lines[0].strip())
    except Exception:
        pass
    return 0


def windows_graphics_available():
    """Check if Windows Graphics Capture (DXGI) is available."""
    try:
        import win32con
        # Check Windows version >= 10 build 17763
        import platform
        ver = platform.version()
        build = int(ver.split('.')[-1]) if ver.split('.')[-1].isdigit() else 0
        return build >= 17763
    except Exception:
        return False


def get_focused_window():
    """Get foreground window handle."""
    return ctypes.windll.user32.GetForegroundWindow()


def set_focus_window(hwnd):
    """Set focus to a window."""
    ctypes.windll.user32.SetForegroundWindow(hwnd)


def get_window_title(hwnd):
    """Get window title as string."""
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def minimize_window(hwnd):
    """Minimize a window."""
    ctypes.windll.user32.ShowWindow(hwnd, 6)


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


def get_window_rect(hwnd):
    """Get window rectangle (left, top, right, bottom)."""
    import win32gui
    return win32gui.GetWindowRect(hwnd)


def get_client_rect(hwnd):
    """Get client area rectangle."""
    import win32gui
    return win32gui.GetClientRect(hwnd)


def print_all_windows():
    """Print all visible windows for debugging."""
    import win32gui

    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            wtext = win32gui.GetWindowText(hwnd)
            wclass = win32gui.GetClassName(hwnd)
            if wtext:
                rect = win32gui.GetWindowRect(hwnd)
                logger.info(f'HWND:{hwnd} Class:{wclass} Title:{wtext} Rect:{rect}')

    win32gui.EnumWindows(enum_callback, None)
