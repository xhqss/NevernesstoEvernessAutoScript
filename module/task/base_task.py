"""
Task base classes - dual mode: ScriptTask + StateTask.
Enhanced with FindFeature, OCR, and device integration.
"""

import time

import numpy as np

from module.base.utils import (
    crop, get_color, color_similar, random_rectangle_point,
    random_normal_distribution_int, random_rectangle_vector,
    ensure_time, image_size
)
from module.device.device_manager import TARGET_WIDTH, TARGET_HEIGHT
from module.feature.box import Box, find_box_by_name, find_boxes_by_name, find_highest_confidence_box
from module.util.logger import logger
from module.task.exceptions import (
    TaskError, WaitTimeoutError, FeatureNotFoundError, FinishedError, TaskDisabledError
)


class TaskBase:
    """Base class for all automation tasks."""

    def __init__(self, config=None, device_manager=None, exit_event=None, handler=None):
        self.config = config or {}
        self._device_manager = device_manager
        self._handler = handler
        self._exit_event = exit_event
        self._last_screenshot = None
        self._last_screenshot_time = 0
        self._click_intervals = {}
        self._task_name = self.__class__.__name__
        self._loop_count = 0
        self._skip_first_screenshot = True
        self._feature_set = None

    @property
    def device_manager(self):
        return self._device_manager

    @device_manager.setter
    def device_manager(self, value):
        self._device_manager = value

    @property
    def feature_set(self):
        return self._feature_set

    @feature_set.setter
    def feature_set(self, value):
        self._feature_set = value

    def screenshot(self):
        """Take a screenshot using the device manager."""
        if self._device_manager:
            self._last_screenshot = self._device_manager.screenshot()
            self._last_screenshot_time = time.time()
        return self._last_screenshot

    def get_resolution(self):
        """Get target resolution (always 1280x720)."""
        return TARGET_WIDTH, TARGET_HEIGHT

    # ========== Button Detection ==========

    def appear(self, button, offset=0, interval=0):
        """Check if a Button appears on the current screenshot."""
        if self._last_screenshot is None:
            return False
        from module.base.button import Button
        if isinstance(button, Button):
            if interval:
                last = self._click_intervals.get(button.name, 0)
                if time.time() - last < interval:
                    return False
            if offset is not None and offset > 0:
                matched = button.match(self._last_screenshot, offset=offset)
                return matched is not None
            return button.appear_on(self._last_screenshot)
        # Treat as area tuple
        color = get_color(self._last_screenshot, button)
        return not color_similar(color, (0, 0, 0))

    def appear_then_click(self, button, offset=0, interval=0):
        """If button appears, click it and return True."""
        from module.base.button import Button
        if not isinstance(button, Button):
            return False
        if self.appear(button, offset=offset, interval=interval):
            self.click(button)
            self._click_intervals[button.name] = time.time()
            return True
        return False

    def click(self, target):
        """Click a Button, Box, or coordinate tuple."""
        from module.base.button import Button
        from module.feature.box import Box as BoxCls
        if isinstance(target, Button):
            x, y = target.button
            x, y = random_rectangle_point((x, y, x, y))
        elif isinstance(target, BoxCls):
            x, y = target.center
        elif isinstance(target, (tuple, list)):
            x, y = target
        else:
            raise TypeError(f"Unknown click target type: {type(target)}")
        if self._device_manager:
            self._device_manager.click(int(x), int(y))

    def swipe(self, x1, y1, x2, y2, duration=0.5):
        """Swipe from one point to another."""
        if self._device_manager:
            start, end = random_rectangle_vector(
                (x2 - x1, y2 - y1), (x1, y1, x2, y2)
            )
            self._device_manager.swipe(start[0], start[1], end[0], end[1], duration)

    def click_box(self, box, offset_x=0, offset_y=0):
        """Click the center of a Box."""
        if box:
            x, y = box.center
            self.click((x + offset_x, y + offset_y))

    # ========== Feature Finding ==========

    def find_one(self, feature_name, threshold=0.85):
        """Find a single feature in the current screenshot."""
        if self._feature_set is None:
            return None
        if self._last_screenshot is None:
            return None
        return self._feature_set.find_one(self._last_screenshot, feature_name, threshold)

    def find_all(self, feature_name, threshold=0.85):
        """Find all instances of a feature."""
        if self._feature_set is None:
            return []
        if self._last_screenshot is None:
            return []
        return self._feature_set.find_feature(self._last_screenshot, feature_name, threshold)

    def find_one_and_click(self, feature_name, threshold=0.85):
        """Find a feature and click it if found."""
        box = self.find_one(feature_name, threshold)
        if box:
            self.click_box(box)
            return True
        return False

    def wait_feature(self, feature_name, timeout=10, interval=0.5, threshold=0.85):
        """Wait for a feature to appear."""
        start = time.time()
        while time.time() - start < timeout:
            self.screenshot()
            box = self.find_one(feature_name, threshold)
            if box:
                return box
            time.sleep(interval)
        return None

    def wait_and_click_feature(self, feature_name, timeout=10, threshold=0.85):
        """Wait for a feature and click it."""
        box = self.wait_feature(feature_name, timeout, threshold=threshold)
        if box:
            self.click_box(box)
            return True
        return False

    # ========== OCR ==========

    def ocr(self, area, letter=(255, 255, 255), threshold=128, alphabet=None):
        """Perform OCR on an area of the screenshot."""
        if self._last_screenshot is None:
            return ''
        from module.ocr.ocr import Ocr
        ocr_obj = Ocr(
            buttons=[area], letter=letter, threshold=threshold,
            alphabet=alphabet
        )
        results = ocr_obj.ocr(self._last_screenshot)
        return results[0] if results else ''

    def ocr_digit(self, area):
        """Perform OCR on a digit area."""
        if self._last_screenshot is None:
            return 0
        from module.ocr.ocr import Digit
        return Digit(buttons=[area]).ocr(self._last_screenshot)

    def ocr_counter(self, area):
        """Perform counter OCR (e.g., '14/15')."""
        if self._last_screenshot is None:
            return 0, 0, 0
        from module.ocr.ocr import DigitCounter
        return DigitCounter(buttons=[area]).ocr(self._last_screenshot)

    # ========== Timing ==========

    def sleep(self, seconds):
        """Sleep that can be interrupted by exit event."""
        s = ensure_time(seconds, n=3)
        if s > 0:
            if self._exit_event:
                self._exit_event.sleep(s)
            else:
                time.sleep(s)

    def wait_until(self, condition, timeout=10, interval=0.5):
        """Wait until condition is true."""
        start = time.time()
        while time.time() - start < timeout:
            if self._exit_event and self._exit_event.is_set():
                return False
            if condition():
                return True
            time.sleep(interval)
        return False

    # ========== Utility ==========

    def crop_screenshot(self, area):
        """Crop the current screenshot to an area."""
        if self._last_screenshot is None:
            return None
        return crop(self._last_screenshot, area)

    def get_color(self, area):
        """Get average color of an area in the current screenshot."""
        if self._last_screenshot is None:
            return 0, 0, 0
        return tuple(get_color(self._last_screenshot, area))

    @property
    def frame(self):
        """Get the current screenshot frame."""
        return self._last_screenshot

    def is_running(self):
        """Check if the task should continue running."""
        if self._exit_event:
            return not self._exit_event.is_set()
        return True

    def run(self):
        raise NotImplementedError


class ScriptTask(TaskBase):
    """Traditional linear script-style task."""

    def before_run(self):
        """Called before run(). Override in subclass."""
        pass

    def after_run(self):
        """Called after run(). Override in subclass."""
        pass

    def execute(self):
        """Execute the full task lifecycle."""
        try:
            self.before_run()
            if self._skip_first_screenshot:
                self.screenshot()
                self._skip_first_screenshot = False
            self.run()
            self.after_run()
        except FinishedError:
            logger.info(f'Task finished: {self._task_name}')
        except Exception as e:
            logger.error(f'Task error: {e}')
            raise


class StateTask(TaskBase):
    """State loop task (Alas-style state machine pattern).

    Override handle_states() and handle_exit().
    """

    def execute(self):
        """Execute the state loop."""
        if self._skip_first_screenshot:
            self.screenshot()
            self._skip_first_screenshot = False

        while self.is_running():
            self.screenshot()
            self._loop_count += 1
            try:
                if self.handle_exit():
                    break
                self.handle_states()
            except FinishedError:
                break

    def handle_exit(self):
        """Check exit conditions. Return True to exit loop."""
        return False

    def handle_states(self):
        """Handle states. Override in subclass."""
        raise NotImplementedError
