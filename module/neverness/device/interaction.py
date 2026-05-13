import ctypes
import logging
import time

import win32api
import win32con
from module.device.control import PostMessageInteraction
from win32api import GetCursorPos, SetCursorPos

logger = logging.getLogger(__name__)


class NTEInteraction(PostMessageInteraction):
    """PC interaction for Neverness to Everness — PostMessage + cursor management + BlockInput."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cursor_position = None
        self._operating = False
        self.user32 = ctypes.windll.user32

    def click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.001, move=False, key="left"):
        self.try_activate()
        if x < 0:
            x, y = round(self.capture.width * 0.5), round(self.capture.height * 0.5)
        should_restore = False
        if move:
            if not self._operating:
                self.cursor_position = GetCursorPos()
                should_restore = True
            abs_x, abs_y = self.capture.get_abs_cords(x, y)
            SetCursorPos((abs_x, abs_y))
            time.sleep(0.025)
        click_pos = win32api.MAKELONG(x, y)
        btn_down = {"left": win32con.WM_LBUTTONDOWN, "middle": win32con.WM_MBUTTONDOWN,
                     "right": win32con.WM_RBUTTONDOWN}.get(key, win32con.WM_LBUTTONDOWN)
        btn_mk = {"left": win32con.MK_LBUTTON, "middle": win32con.MK_MBUTTON,
                   "right": win32con.MK_RBUTTON}.get(key, win32con.MK_LBUTTON)
        btn_up = {"left": win32con.WM_LBUTTONUP, "middle": win32con.WM_MBUTTONUP,
                   "right": win32con.WM_RBUTTONUP}.get(key, win32con.WM_LBUTTONUP)
        self.post(btn_down, btn_mk, click_pos)
        time.sleep(down_time)
        self.post(btn_up, 0, click_pos)
        if should_restore:
            time.sleep(0.025)
            SetCursorPos(self.cursor_position)

    def operate(self, fun, block=False):
        result = None
        is_outer_operate = False
        if not self._operating:
            self.cursor_position = GetCursorPos()
            self._operating = True
            is_outer_operate = True
        if block:
            self.block_input()
        try:
            result = fun()
        except Exception as e:
            logger.error("operate exception: %s", e)
        finally:
            if is_outer_operate:
                self._operating = False
                time.sleep(0.025)
                SetCursorPos(self.cursor_position)
            if block:
                self.unblock_input()
        return result

    def block_input(self):
        self.user32.BlockInput(True)

    def unblock_input(self):
        self.user32.BlockInput(False)
