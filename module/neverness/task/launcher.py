"""
LauncherTask - Finds HTGame.exe, waits for window, brings to front.

Simplified launcher for Neverness-to-Everness.
"""

import os
import re
import time

import psutil
import win32con
import win32gui
import win32process

from module.task.exceptions import TaskDisabledError
from module.util.logger import logger

from module.neverness.task.base import BaseNTETask


GAME_EXE = "HTGame.exe"
LAUNCHER_EXE = "NTEGame.exe"


class LauncherTask(BaseNTETask):
    """Launcher task: finds the game process/window and brings it to foreground."""

    CONF_PATH = "launcher_path"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "start_game"
        self.enable_after_start = True
        self.config.setdefault(self.CONF_PATH, "")

    def run(self):
        self.log_info("launcher task started")
        game_proc = self._find_process(GAME_EXE)
        self.log_info(f"game process: {self._fmt_proc(game_proc)}")

        if game_proc:
            self.log_info("game is already running")
            self._update_launcher_path_from_game(game_proc.get("exe"))
            if not self._wait_for_process(GAME_EXE):
                raise TaskDisabledError("timeout waiting for game window")
            self._capture_game()
            return

        launcher_proc = self._find_process(LAUNCHER_EXE)
        self.log_info(f"launcher process: {self._fmt_proc(launcher_proc)}")

        if launcher_proc:
            self.log_info("launcher is already running")
            self._update_launcher_path(launcher_proc.get("exe"))
            if not self._wait_for_process(LAUNCHER_EXE):
                raise TaskDisabledError("timeout waiting for launcher window")
            self._capture_launcher()
            if not self._click_start_game():
                raise TaskDisabledError("timeout waiting for launcher to minimize")
            self._wait_for_game_and_capture()
            return

        launcher_path = self._get_launcher_path()
        if not launcher_path:
            self.log_error("launcher path not found in config or registry")
            raise TaskDisabledError("launcher path not found, set NTEGame.exe path")

        self.log_info(f"starting launcher: {launcher_path}")
        os.startfile(launcher_path)
        self.sleep(5)

        if not self._wait_for_process(LAUNCHER_EXE, settle_window=True):
            self.log_error("timeout waiting for launcher process")
            raise TaskDisabledError("timeout waiting for launcher process")

        launcher_proc = self._find_process(LAUNCHER_EXE)
        if launcher_proc:
            self._update_launcher_path(launcher_proc.get("exe"))

        self._capture_launcher()
        if not self._click_start_game():
            raise TaskDisabledError("timeout waiting for launcher to minimize")
        self._wait_for_game_and_capture()

    # ------------------------------------------------------------------
    # Process / window helpers
    # ------------------------------------------------------------------

    def _find_process(self, exe_name):
        exe_name = exe_name.lower()
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                name = proc.info.get("name") or ""
                if name.lower() == exe_name:
                    return proc.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def _find_window_for_process(self, proc_info):
        pid = proc_info.get("pid")
        if not pid:
            return 0
        matches = []

        def _callback(hwnd, _):
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowEnabled(hwnd):
                return True
            try:
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if window_pid == pid:
                matches.append(hwnd)
            return True

        win32gui.EnumWindows(_callback, None)
        if not matches:
            return 0
        visible = [h for h in matches if win32gui.IsWindowVisible(h)]
        return visible[0] if visible else matches[0]

    def _get_window_size(self, hwnd):
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            return max(0, right - left), max(0, bottom - top)
        except Exception:
            return 0, 0

    def _wait_for_process(self, exe_name, time_out=120, settle_window=False):
        self.log_info(f"waiting for {exe_name} (timeout={time_out}s)")
        start = time.time()
        while time.time() - start < time_out:
            proc = self._find_process(exe_name)
            if proc:
                hwnd = self._find_window_for_process(proc)
                if hwnd:
                    self._restore_window_if_minimized(hwnd, exe_name)
                    size = self._get_window_size(hwnd)
                    if size[0] > 200 and size[1] > 200:
                        self.log_info(f"found {exe_name}: hwnd={hwnd}, size={size[0]}x{size[1]}")
                        return True
            self.sleep(1)
        self.log_warning(f"{exe_name} not found within {time_out}s")
        return False

    def _restore_window_if_minimized(self, hwnd, exe_name):
        if win32gui.IsIconic(hwnd):
            self.log_info(f"restoring minimized {exe_name} window")
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    def _click_start_game(self, time_out=120):
        self.log_info(f"looking for start game button (timeout={time_out}s)")
        start = time.time()
        clicked = False
        while time.time() - start < time_out:
            if self._is_launcher_minimized():
                self.log_info("launcher minimized, start succeeded")
                return True
            # Fallback: click center area
            if not clicked:
                self.click(0.5269, 0.6122, after_sleep=2)
                clicked = True
            self.sleep(1)
        return False

    def _is_launcher_minimized(self):
        proc = self._find_process(LAUNCHER_EXE)
        if not proc:
            return False
        hwnd = self._find_window_for_process(proc)
        return bool(hwnd and win32gui.IsIconic(hwnd))

    def _wait_for_game_and_capture(self, time_out=600):
        self.log_info(f"waiting for game process (timeout={time_out}s)")
        if not self._wait_for_process(GAME_EXE, time_out=time_out, settle_window=True):
            raise TaskDisabledError("timeout waiting for game process")
        self._capture_game()

    def _get_launcher_path(self):
        configured = self.config.get(self.CONF_PATH, "").strip()
        if configured and os.path.exists(configured):
            return configured
        # Check registry
        return self._find_launcher_from_registry()

    def _update_launcher_path(self, path):
        if path and os.path.basename(path).lower() == LAUNCHER_EXE.lower() and os.path.exists(path):
            self.config[self.CONF_PATH] = path

    def _update_launcher_path_from_game(self, game_path):
        if not game_path:
            return
        path = os.path.abspath(game_path)
        parts = path.split(os.sep)
        lowered = [p.lower() for p in parts]
        if "client" in lowered:
            idx = lowered.index("client")
            root = os.sep.join(parts[:idx])
            candidate = os.path.join(root, "NTELauncher", LAUNCHER_EXE)
            self._update_launcher_path(candidate)

    def _find_launcher_from_registry(self):
        try:
            import winreg
        except ImportError:
            return ""
        roots = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
        uninstall_keys = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]
        for root in roots:
            for key_path in uninstall_keys:
                result = self._scan_registry(root, key_path, winreg)
                if result:
                    return result
        return ""

    def _scan_registry(self, root, key_path, winreg):
        try:
            with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, index)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            result = self._check_registry_values(subkey, winreg)
                            if result:
                                return result
                    except OSError:
                        continue
        except OSError:
            pass
        return ""

    def _check_registry_values(self, subkey, winreg):
        values = {}
        for name in ("DisplayName", "InstallLocation", "DisplayIcon", "UninstallString"):
            try:
                values[name] = str(winreg.QueryValueEx(subkey, name)[0])
            except OSError:
                values[name] = ""
        combined = " ".join(values.values()).lower()
        if not any(tok in combined for tok in ("neverness", "ntegame", "ntelauncher")):
            return ""
        for val in values.values():
            match = re.search(r'"?([a-zA-Z]:\\[^"]*?NTEGame\.exe)"?', val)
            if match and os.path.exists(match.group(1)):
                return match.group(1)
            path = val.strip().strip('"')
            if os.path.basename(path).lower() == LAUNCHER_EXE.lower() and os.path.exists(path):
                return path
        return ""

    def _capture_game(self):
        self.log_info("capturing game window")

    def _capture_launcher(self):
        self.log_info("capturing launcher window")

    def _fmt_proc(self, proc_info):
        if not proc_info:
            return "not found"
        return f"name={proc_info.get('name', '?')}, exe={proc_info.get('exe', '?')}"
