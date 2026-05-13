"""
BaseNTETask - Bridge between al-script TaskBase and Neverness-to-Everness game logic.

Provides game-specific detection, interaction, navigation, and UI panel helpers.
"""

import ctypes
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Callable, List, Optional, Tuple, Any, overload

import cv2
import numpy as np
import win32api
import win32con
import win32gui
import win32process

from module.task.base_task import TaskBase
from module.feature.box import Box, find_box_by_name, find_boxes_by_name, relative_box
from module.feature.feature_set import FeatureSet
from module.util.logger import logger as _framework_logger
from module.device.device_manager import TARGET_WIDTH, TARGET_HEIGHT

from module.neverness.Labels import Labels
from module.neverness.scene.NTEScene import NTEScene
from module.neverness.util import image as iu
from module.neverness.util import filter as gf
from module.neverness.globals import Globals

logger = _framework_logger

stamina_re = re.compile(r"(\d+)[\s/\\|!Il／-]+\d+")


class BaseNTETask(TaskBase):
    """Game-specific base task for Neverness-to-Everness automation.

    Extends al-script's TaskBase with:
    - Game window management (bring_to_front, is_foreground)
    - Feature detection (find_one, find_feature, box_of_screen)
    - Character UI (is_in_team, in_world, get_current_char_index, multi_stage_char_match)
    - Navigation (walk_until_interac, walk_to_treasure)
    - UI panels (openF1panel, openF2panel, openESCpanel)
    - Stamina, monthly card, claim handling
    - OpenVINO detection (async/sync)
    - Periodic task submission
    """

    DEFAULT_MOVE = False

    def __init__(self, config=None, device_manager=None, exit_event=None, handler=None):
        super().__init__(config, device_manager, exit_event, handler)
        self.scene: Optional[NTEScene] = None
        self.key_config = {}
        self.monthly_card_config = {}
        self.sound_config = {}
        self._logged_in = False
        self.arrow_contour = {"contours": None, "shape": None}
        self.char_ui_offset = False
        self.next_monthly_card_start = 0
        self._last_interval_action_time = {}
        self._action_interval_lock = threading.Lock()
        self._char_template_cache = {}
        self.monthly_card_pause_time = 0.0

    # ------------------------------------------------------------------
    # Resolution helpers (ratio-based Box creation)
    # ------------------------------------------------------------------

    @property
    def width(self) -> int:
        return TARGET_WIDTH

    @property
    def height(self) -> int:
        return TARGET_HEIGHT

    def width_of_screen(self, ratio: float) -> int:
        return int(self.width * ratio)

    def height_of_screen(self, ratio: float) -> int:
        return int(self.height * ratio)

    def box_of_screen(self, x: float, y: float, to_x: float, to_y: float, name: str = "") -> Box:
        """Create a Box from ratio-based coordinates (0.0-1.0)."""
        return relative_box(x, y, to_x, to_y, self.width, self.height, name=name)

    def box_of_screen_scaled(
        self,
        base_w: int,
        base_h: int,
        x: int,
        y: int,
        width_original: int = 0,
        height_original: int = 0,
        name: str = "",
    ) -> Box:
        """Create a Box scaled from a base resolution."""
        scale_x = self.width / base_w
        scale_y = self.height / base_h
        bx = int(x * scale_x)
        by = int(y * scale_y)
        bw = int(width_original * scale_x) if width_original else 0
        bh = int(height_original * scale_y) if height_original else 0
        return Box(x=bx, y=by, width=bw, height=bh, name=name)

    # ------------------------------------------------------------------
    # Feature / Box accessors
    # ------------------------------------------------------------------

    def get_box_by_name(self, name: str) -> Box:
        """Get a Box geometry from the feature set by name."""
        if self._feature_set is None:
            return Box(0, 0, 0, 0, name=name)
        box = self._feature_set.get_box(name)
        if box is None:
            return Box(0, 0, 0, 0, name=name)
        return box

    def get_feature_by_name(self, name: str):
        """Get a Feature (image mat) from the feature set by name."""
        if self._feature_set is None:
            return None
        return self._feature_set.get_feature(name)

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def find_one(
        self,
        feature_name,
        threshold: float = 0.85,
        box: Box = None,
        mask_function=None,
        frame_processor=None,
        horizontal_variance: float = 0,
        vertical_variance: float = 0,
        use_gray_scale: bool = False,
    ) -> Optional[Box]:
        """Find a single feature in the current screenshot with optional processing.

        Args:
            feature_name: Label name of the feature.
            threshold: Confidence threshold (0-1).
            box: Restrict search to this Box area.
            mask_function: Callable(image)->mask to pre-filter.
            frame_processor: Callable(image)->processed_image for template matching.
            horizontal_variance: Allowable horizontal variance ratio.
            vertical_variance: Allowable vertical variance ratio.
            use_gray_scale: Match on grayscale images.
        """
        if self._feature_set is None:
            return None
        if self._last_screenshot is None:
            return None

        result = self._feature_set.find_one(
            self._last_screenshot,
            feature_name,
            threshold=threshold,
            box=box,
            mask_function=mask_function,
            frame_processor=frame_processor,
            horizontal_variance=horizontal_variance,
            vertical_variance=vertical_variance,
            use_gray_scale=use_gray_scale,
        )
        return result

    def find_feature(
        self,
        feature_name,
        threshold: float = 0.85,
        box: Box = None,
        mask_function=None,
        frame_processor=None,
    ) -> List[Box]:
        """Find all instances of a feature."""
        if self._feature_set is None:
            return []
        if self._last_screenshot is None:
            return []
        return self._feature_set.find_feature(
            self._last_screenshot,
            feature_name,
            threshold=threshold,
            box=box,
            mask_function=mask_function,
            frame_processor=frame_processor,
        )

    # ------------------------------------------------------------------
    # Click (extended: accepts Box, tuple, or ratio floats)
    # ------------------------------------------------------------------

    @overload
    def click(self, x: int, y: int, **kwargs) -> Any:
        ...

    @overload
    def click(self, x_box_ratio: float, y_box_ratio: float, **kwargs) -> Any:
        ...

    def click(
        self,
        x=0,
        y=0,
        move_back=False,
        name=None,
        interval=0,
        move=False,
        down_time=0.02,
        after_sleep=0,
        key='left',
        hcenter=False,
        vcenter=False,
        action_name=None,
    ):
        """Click at a target.

        Accepts:
        - Box: click its center with random offset.
        - (float, float): ratio-based screen coordinates (0.0-1.0).
        - (int, int): absolute pixel coordinates.
        """
        if action_name is not None:
            if not self._check_action_interval(action_name, interval if interval > 0 else 0.1):
                return False

        target_x, target_y = self._resolve_click_target(
            x, y, hcenter=hcenter, vcenter=vcenter
        )

        if self._device_manager:
            if move:
                self._device_manager.move(int(target_x), int(target_y))
            self._device_manager.click(int(target_x), int(target_y), down_time=down_time)

        if after_sleep > 0:
            self.sleep(after_sleep)

        if name is not None:
            self._click_intervals[name] = time.time()

        return True

    def _resolve_click_target(self, x, y, hcenter=False, vcenter=False):
        """Normalize various click target formats to (px, py)."""
        from module.base.utils import random_rectangle_point

        if isinstance(x, Box):
            if hcenter:
                x_val = x.center[0]
            else:
                x_val, y_val = random_rectangle_point(x.area)
                return x_val, y_val
        if isinstance(x, (float,)) and isinstance(y, (float,)):
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                return int(self.width * x), int(self.height * y)
        if isinstance(x, (tuple, list)) and len(x) == 2:
            return x[0], x[1]
        return int(x), int(y)

    def operate_click(
        self,
        x=0,
        y=0,
        move_back=False,
        name=None,
        interval=0,
        down_time=0.02,
        key='left',
        hcenter=False,
        vcenter=False,
        action_name=None,
    ):
        """Click via operate (physical mouse move + click), blocking."""
        return self.operate(
            lambda: self.click(
                x=x, y=y, move_back=move_back, name=name,
                interval=interval, down_time=down_time, key=key,
                hcenter=hcenter, vcenter=vcenter, action_name=action_name,
                move=True, after_sleep=0,
            ),
            block=True,
        )

    def middle_click(self, after_sleep=0, interval=0):
        """Perform a middle mouse click."""
        if self._device_manager:
            self._device_manager.click(0, 0, button='middle')
        if after_sleep > 0:
            self.sleep(after_sleep)
        return True

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def send_key(self, key, down_time=0.02, interval=0, after_sleep=0, action_name=None):
        """Send a keyboard key press."""
        if action_name is not None:
            if not self._check_action_interval(action_name, interval if interval > 0 else 0.1):
                return False
        if self._device_manager:
            self._device_manager.send_key(key, down_time=down_time)
        if after_sleep > 0:
            self.sleep(after_sleep)
        return True

    def send_key_down(self, key):
        """Press and hold a key."""
        if self._device_manager:
            self._device_manager.send_key_down(key)

    def send_key_up(self, key):
        """Release a held key."""
        if self._device_manager:
            self._device_manager.send_key_up(key)

    def back(self, after_sleep=2):
        """Press the Escape key (back)."""
        self.send_key("esc", after_sleep=after_sleep)

    # ------------------------------------------------------------------
    # Wait / Timing
    # ------------------------------------------------------------------

    def wait_until(
        self,
        condition: Callable,
        time_out: float = 10,
        interval: float = 0.5,
        raise_if_not_found: bool = False,
        post_action: Callable = None,
        settle_time: float = 0,
        pre_action: Callable = None,
    ):
        """Wait until a condition is met.

        Args:
            condition: Callable returning True when met.
            time_out: Maximum wait time in seconds.
            interval: Polling interval in seconds.
            raise_if_not_found: Raise error on timeout.
            post_action: Action to run after each failed poll.
            settle_time: Extra settle wait after condition is met.
            pre_action: Action to run before each poll.
        """
        start = time.time()
        while time.time() - start < time_out:
            if self._exit_event and self._exit_event.is_set():
                return False
            if pre_action is not None:
                pre_action()
            result = condition()
            if result:
                if settle_time > 0:
                    self.sleep(settle_time)
                return result
            if post_action is not None:
                post_action()
            self.sleep(interval)
        if raise_if_not_found:
            from module.task.exceptions import WaitTimeoutError
            raise WaitTimeoutError(f"wait_until timed out after {time_out}s")
        return False

    def next_frame(self):
        """Capture the next screenshot frame."""
        self.screenshot()

    # ------------------------------------------------------------------
    # Action interval gating
    # ------------------------------------------------------------------

    def _check_action_interval(self, action_name: str, interval: float) -> bool:
        if interval <= 0:
            return True
        with self._action_interval_lock:
            now = time.time()
            last_time = self._last_interval_action_time.get(action_name, 0)
            if now - last_time < interval:
                return False
            self._last_interval_action_time[action_name] = now
            return True

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------

    def log_info(self, message: str, notify: bool = False):
        logger.info(message)

    def log_debug(self, message: str):
        logger.debug(message)

    def log_error(self, message: str, notify: bool = False):
        logger.error(message)

    def log_warning(self, message: str, notify: bool = False):
        logger.warning(message)

    def info_set(self, key: str, value):
        """Set an info display key-value."""
        pass

    def info_get(self, key: str):
        """Get an info display value."""
        return None

    # ------------------------------------------------------------------
    # Thread pool / periodic tasks
    # ------------------------------------------------------------------

    @property
    def thread_pool_executor(self) -> Optional[ThreadPoolExecutor]:
        return _get_globals().thread_pool_executor

    def submit_periodic_task(self, delay: float, task: Callable, *args, **kwargs):
        """Submit a periodic task to the global thread pool."""
        _get_globals().submit_periodic_task(delay, task, *args, **kwargs)

    # ------------------------------------------------------------------
    # OpenVINO detection
    # ------------------------------------------------------------------

    def _openvino_detect(self, frame, sync, box, threshold, force=False, mask_regions=None):
        g = _get_globals()
        if g is None:
            return []
        if box is None:
            box = self.box_of_screen(0.0840, 0.1326, 0.9176, 0.8694, name="openvino_box")
        if frame is None:
            frame = self._last_screenshot
        if sync:
            return g.openvino_detect_sync(
                image=frame, box=box, threshold=threshold, mask_regions=mask_regions
            )
        else:
            return g.openvino_detect_async(
                image=frame, box=box, threshold=threshold, force=force, mask_regions=mask_regions
            )

    def openvino_detect_async(
        self, frame=None, box: Box = None, threshold: float = 0.6, force: bool = False,
        mask_regions=None
    ) -> List[Box]:
        """Async OpenVINO detection (may return cached result)."""
        return self._openvino_detect(
            frame, False, box, threshold, force=force, mask_regions=mask_regions
        )

    def openvino_detect_sync(
        self, frame=None, box: Box = None, threshold: float = 0.5, mask_regions=None
    ) -> List[Box]:
        """Sync OpenVINO detection (blocks until result)."""
        return self._openvino_detect(frame, True, box, threshold, mask_regions=mask_regions)

    # ------------------------------------------------------------------
    # Character UI
    # ------------------------------------------------------------------

    @property
    def char_vertical_spacing(self) -> int:
        return int(self.height * 176 / 1440)

    def get_char_box(self, index: int) -> Box:
        """Get the Box for a character slot (0-indexed)."""
        box = self.get_box_by_name(f"box_char_{index + 1}")
        if self.char_ui_offset:
            box = self._shift_char_ui_box(box)
        return box

    def get_char_text_box(self, index: int) -> Box:
        """Get the text Box for a character slot."""
        return self.get_box_by_name(f"char_{index + 1}_text")

    def get_base_char_element_box(self) -> Box:
        """Get the base box for character element detection."""
        box = self.box_of_screen_scaled(
            2560, 1440, 2438, 335, width_original=29, height_original=29
        )
        box = self._shift_char_ui_box(box, expend=True)
        return box

    def get_box_by_char_spacing(self, box: Box, index: int) -> Box:
        """Offset a box vertically by character slot spacing."""
        return Box(
            x=box.x, y=box.y + index * self.char_vertical_spacing,
            width=box.width, height=box.height,
            name=f"{box.name}_{index}"
        )

    def _shift_char_ui_box(self, box: Box, expend: bool = False) -> Box:
        """Adjust a character UI box for UI offset."""
        offset = int(-9 * self.width / 2560)
        width_offset = -offset if expend else 0
        return Box(
            x=box.x + offset, y=box.y,
            width=box.width + width_offset, height=box.height,
            name=box.name
        )

    # ------------------------------------------------------------------
    # is_in_team / in_world
    # ------------------------------------------------------------------

    def is_in_team(self) -> bool:
        """Check if the player is in a team (health bar slash visible)."""
        box = self.find_one(
            Labels.health_bar_slash,
            mask_function=iu.mask_corners,
            horizontal_variance=0.01,
            vertical_variance=0.005,
        )
        return box is not None

    def in_world(self) -> bool:
        """Check if the player is in the open world (mini-map arrow shape matching)."""
        frame = self._last_screenshot
        if frame is None:
            return False

        if self.arrow_contour["shape"] != frame.shape[:2]:
            template_bgr = self.get_feature_by_name(Labels.mini_map_arrow)
            if template_bgr is None:
                return False
            t_bin = template_bgr.mat[:, :, 0] if template_bgr.mat.ndim == 3 else template_bgr.mat
            contours, _ = cv2.findContours(t_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return False
            self.arrow_contour["contours"] = max(contours, key=cv2.contourArea)
            self.arrow_contour["shape"] = frame.shape[:2]

        mat = self.box_of_screen(0.0691, 0.1083, 0.0949, 0.1493, name="in_world").crop_frame(frame)
        mat = iu.binarize_bgr_by_brightness(mat, threshold=200)
        res, _ = self._find_rotated_shape(mat)
        return len(res) == 1

    def _find_rotated_shape(self, scene_bgr, score_threshold: float = 0.1):
        """Find rotated arrow shape in the mini-map area."""
        s_bin = scene_bgr[:, :, 0] if scene_bgr.ndim == 3 else scene_bgr
        scene_contours, _ = cv2.findContours(s_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results = []
        for cnt in scene_contours:
            if cv2.contourArea(cnt) < 50:
                continue
            score = cv2.matchShapes(
                self.arrow_contour["contours"], cnt, cv2.CONTOURS_MATCH_I1, 0.0
            )
            if score < score_threshold:
                results.append({"score": score})
        return results, 0

    def in_team(self) -> Tuple[bool, int, int]:
        """Return (is_in_team, current_char_index, exist_count)."""
        if not self.is_in_team():
            return False, -1, 0

        if self.scene is not None:
            state, timestamp = self.scene.get_is_in_team_record()
            if state and (to_sleep := 0.5 - (time.time() - timestamp)) > 0:
                self.sleep(to_sleep)

        arr = self._update_char_ui_offset()
        current = self._get_current_char_index()
        exist_count = 0
        for i in range(len(arr)):
            if arr[i] is not None:
                exist_count += 1
            elif current == -1:
                current = i

        if current != -1 and arr[current] is None:
            exist_count += 1

        self._logged_in = True
        return True, current, exist_count

    def _update_char_ui_offset(self):
        arr = self.multi_stage_char_match()
        results = [
            c.x < self.get_char_text_box(idx).x
            for idx, c in enumerate(arr) if c is not None
        ]
        if results:
            self.char_ui_offset = sum(results) > (len(results) / 2)
        else:
            self.char_ui_offset = False
        return arr

    def in_team_and_world(self) -> bool:
        return self.is_in_team() and self.in_world()

    def wait_in_team(self, time_out: float = 30, raise_if_not_found: bool = True, esc: bool = False):
        success = self.wait_until(
            self.is_in_team,
            time_out=time_out,
            raise_if_not_found=raise_if_not_found,
            post_action=lambda: self.back(after_sleep=2) if esc else None,
        )
        if success:
            self.sleep(0.1)
        return success

    def wait_in_team_and_world(
        self, time_out: float = 30, raise_if_not_found: bool = True, esc: bool = False
    ):
        success = self.wait_until(
            self.in_team_and_world,
            time_out=time_out,
            raise_if_not_found=raise_if_not_found,
            post_action=lambda: self.back(after_sleep=2) if esc else None,
        )
        if success:
            self.sleep(0.1)
        return success

    # ------------------------------------------------------------------
    # Current character detection (template-based scoring)
    # ------------------------------------------------------------------

    def _get_char_template_data(self):
        """Lazily load and cache character template data."""
        cache = self._char_template_cache
        if (
            cache.get("width") != self.width
            or cache.get("height") != self.height
        ):
            feature = self.get_feature_by_name(Labels.is_current_char)
            mat = feature.mat if feature is not None else np.zeros((10, 10), dtype=np.uint8)
            white_pixels = cv2.countNonZero(mat)
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.dilate(mat, kernel, iterations=1)
            self._char_template_cache = {
                "width": self.width,
                "height": self.height,
                "mat": mat,
                "mask": mask,
                "white_pixels": white_pixels,
            }
        c = self._char_template_cache
        return c["mat"], c["mask"], c["white_pixels"]

    def get_char_match_score(self, index: int, frame=None) -> float:
        """Get match score for character at slot index (lower is better)."""
        template_mat, _, template_white_count = self._get_char_template_data()
        if template_white_count == 0:
            return 1.0
        if frame is None:
            frame = self._last_screenshot

        base_box = self.get_box_by_name(Labels.is_current_char)
        base_box = self._shift_char_ui_box(base_box, expend=True)
        box = self.get_box_by_char_spacing(base_box, index)

        from module.base.utils import crop
        cropped = crop(frame, box.area)
        if cropped is None:
            return 1.0
        current_mat = gf.current_char_filter(cropped)

        total_pixels = current_mat.shape[0] * current_mat.shape[1]
        if total_pixels > 0 and cv2.countNonZero(current_mat) / total_pixels > 0.5:
            return 1.0

        th, tw = template_mat.shape[:2]
        ch, cw = current_mat.shape[:2]
        if ch >= th and cw >= tw:
            result = cv2.matchTemplate(current_mat, template_mat, cv2.TM_CCORR)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            coverage = max_val / (template_white_count * 255 * 255)
            return 1.0 - coverage
        return 1.0

    def is_char_at_index(self, index: int, threshold: float = 0.5, frame=None) -> bool:
        score = self.get_char_match_score(index, frame=frame)
        return score < threshold

    def _get_current_char_index(self) -> int:
        """Scan all 4 slots and return the best matching index."""
        best_score = 999
        best_idx = -1
        for i in range(4):
            score = self.get_char_match_score(i)
            if score < best_score:
                best_score = score
                best_idx = i
        return best_idx

    def multi_stage_char_match(self) -> List[Optional[Box]]:
        """Match all 4 character text labels with progressive contrast steps."""
        results = [None, None, None, None]
        contrast_steps = [0, 30, 60, 90]

        for c_val in contrast_steps:
            if all(res is not None for res in results):
                break
            for i in range(4):
                if results[i] is None:
                    def _make_processor(cur_c):
                        return lambda img: iu.adjust_lightness_contrast_lab(
                            img, brightness=0, contrast=cur_c
                        )
                    res = self.find_one(
                        f"char_{i + 1}_text",
                        threshold=0.7,
                        frame_processor=_make_processor(c_val),
                        mask_function=iu.mask_outside_white_rect,
                        horizontal_variance=0.005,
                    )
                    if res:
                        results[i] = res
        return results

    # ------------------------------------------------------------------
    # Interaction / Walk
    # ------------------------------------------------------------------

    @property
    def interact_box(self) -> Box:
        box = self.get_box_by_name(Labels.interactable)
        return Box(
            x=int(box.x - box.width * 0.3),
            y=int(box.y - box.height * 2.5),
            width=int(box.width * 1.6),
            height=int(box.height * 6),
            name="search_interac",
        )

    def find_interac(self) -> Optional[Box]:
        """Find an interactable object near the player."""
        return self.find_one(
            Labels.interactable,
            box=self.interact_box,
            threshold=0.7,
            mask_function=_interac_mask,
        )

    def walk_until_interac(
        self, direction: str = "w", time_out: float = 10, raise_if_not_found: bool = False
    ) -> bool:
        """Walk forward until an interactable is found."""
        ret = False
        try:
            self.middle_click(after_sleep=0.2)
            self.send_key_down(direction)
            ret = bool(
                self.wait_until(
                    self.find_interac,
                    time_out=time_out,
                    raise_if_not_found=raise_if_not_found,
                )
            )
        finally:
            self.send_key_up(direction)
        return ret

    def find_treasure(self) -> Optional[Box]:
        """Find treasure in the main viewport."""
        def mask(img):
            return iu.mask_corners(img, 0.5, 0.5, "all", to_bgr=False)
        return self.find_one(
            Labels.treasure,
            box=self.main_viewport,
            threshold=0.7,
            mask_function=mask,
            use_gray_scale=True,
        )

    def walk_to_treasure(self) -> bool:
        """Walk toward visible treasure."""
        if self.find_treasure():
            self._walk_to_box(self.find_treasure, end_condition=self.find_interac, y_offset=0.1)
            return True
        return False

    def _walk_to_box(
        self, find_function, time_out: float = 30,
        end_condition=None, y_offset: float = 0.05, x_threshold: float = 0.07
    ):
        """Walk toward a target box using directional key presses."""
        start = time.time()
        while time.time() - start < time_out:
            if self._do_walk_to_box(
                find_function,
                time_out=time_out - (time.time() - start),
                end_condition=end_condition,
                y_offset=y_offset,
                x_threshold=x_threshold,
            ):
                return True

    def _do_walk_to_box(
        self, find_function, time_out: float = 30,
        end_condition=None, y_offset: float = 0.05, x_threshold: float = 0.07
    ):
        if find_function:
            self.wait_until(
                lambda: (not end_condition or end_condition()) or find_function(),
                raise_if_not_found=True,
                time_out=time_out,
            )
        last_direction = None
        try:
            start = time.time()
            last_target = None
            centered = False
            while time.time() - start < time_out:
                self.next_frame()
                if end_condition and end_condition():
                    return True
                result = find_function()
                if isinstance(result, list):
                    target = result[0] if result else None
                else:
                    target = result
                if target:
                    last_target = target
                direction, centered = self._calc_walk_direction(
                    last_target, last_direction, y_offset, x_threshold, centered
                )
                if direction != last_direction:
                    if last_direction:
                        self.send_key_up(last_direction)
                        self.sleep(0.001)
                    last_direction = direction
                    if direction:
                        self.send_key_down(direction)
        finally:
            if last_direction:
                self.send_key_up(last_direction)

    def _calc_walk_direction(self, last_target, last_direction, y_offset, x_threshold, centered):
        if last_target is None:
            return self._opposite_direction(last_direction), centered
        x, y = last_target.center
        y = max(0, y - self.height_of_screen(y_offset))
        x_abs = abs(x - self.width_of_screen(0.5))
        threshold = 0.04 if not last_direction else x_threshold
        centered = centered or x_abs <= self.width_of_screen(threshold)
        if not centered:
            direction = "d" if x > self.width_of_screen(0.5) else "a"
        else:
            if last_direction == "s":
                v_center = 0.45
            elif last_direction == "w":
                v_center = 0.6
            else:
                v_center = 0.5
            direction = "s" if y > self.height_of_screen(v_center) else "w"
        return direction, centered

    def _opposite_direction(self, direction):
        opposites = {"w": "s", "s": "w", "a": "d", "d": "a"}
        return opposites.get(direction, "w")

    # ------------------------------------------------------------------
    # Transport / Teleport
    # ------------------------------------------------------------------

    def find_traval_button(self) -> Optional[Box]:
        """Find the teleport/travel button."""
        box = self.get_box_by_name(Labels.teleport)
        w = box.width - (box.x - self.width_of_screen(0.99))
        y = -box.width * 0.2
        search_box = Box(
            x=box.x, y=box.y + int(y),
            width=box.width + int(w), height=box.height + int(-y),
            name="search_teleport"
        )
        return self.find_one(Labels.teleport, box=search_box)

    def click_traval_button(self, travel_btn: Box = None):
        """Click the teleport/travel button."""
        if not isinstance(travel_btn, Box):
            travel_btn = self.wait_until(
                self.find_traval_button, time_out=10, raise_if_not_found=True
            )
        self.sleep(0.1)
        self.operate_click(travel_btn)
        self.sleep(1)

    # ------------------------------------------------------------------
    # UI Panels
    # ------------------------------------------------------------------

    def openF1panel(self) -> bool:
        """Open the F1 panel (main menu)."""
        if self.in_team_and_world():
            self.send_key("f1", after_sleep=1)
            self.log_info("send f1 key to open the panel")
        result = self._wait_panel(Labels.f1_panel)
        if not result:
            self.log_error("can't find F1 panel, make sure f1 is the hotkey for panel", notify=True)
            from module.task.exceptions import FeatureNotFoundError
            raise FeatureNotFoundError("can't find F1 panel")
        self.sleep(0.5)
        return result

    def openF2panel(self) -> bool:
        """Open the F2 panel (battle pass)."""
        if self.in_team_and_world():
            self.send_key("f2", after_sleep=1)
            self.log_info("send f2 key to open the panel")
        result = self._wait_panel(Labels.f2_panel)
        if not result:
            self.log_error("can't find F2 panel, make sure f2 is the hotkey for panel", notify=True)
            from module.task.exceptions import FeatureNotFoundError
            raise FeatureNotFoundError("can't find F2 panel")
        self.sleep(0.5)
        return result

    def openESCpanel(self) -> bool:
        """Open the ESC panel (system menu)."""
        if self.in_team_and_world():
            self.send_key("esc", after_sleep=1)
            self.log_info("send esc key to open the panel")
        result = self._wait_panel(Labels.esc_option, box=self.get_box_by_name(Labels.box_all_esc_options), threshold=0.3)
        if not result:
            self.log_error("can't find ESC panel, make sure esc is the hotkey for panel", notify=True)
            from module.task.exceptions import FeatureNotFoundError
            raise FeatureNotFoundError("can't find ESC panel")
        self.sleep(0.5)
        return result

    def _wait_panel(
        self, feature, box: Box = None, threshold: float = 0.8, time_out: float = 4.5
    ) -> Optional[Box]:
        result = self.wait_until(
            lambda: self.find_one(feature, box=box, threshold=threshold),
            time_out=time_out,
            settle_time=0.5,
        )
        return result

    # ------------------------------------------------------------------
    # Ensure main (login / in-world)
    # ------------------------------------------------------------------

    def ensure_main(self, esc: bool = True, time_out: float = 30):
        """Ensure the game is in the main world state (logged in, in team)."""
        self.info_set("current task", f"wait main esc={esc}")
        if not self._logged_in:
            time_out = 600
        if not self.wait_until(
            lambda: self._is_main(esc=esc), time_out=time_out, raise_if_not_found=False
        ):
            raise Exception("Please start in game world and in team!")
        self.sleep(0.5)
        self.info_set("current task", None)

    def _is_main(self, esc: bool = True) -> bool:
        if self.in_team_and_world():
            self._logged_in = True
            return True
        if self.handle_monthly_card():
            return True
        if self._wait_login():
            return True
        if esc:
            self.back(after_sleep=2)
        return False

    # ------------------------------------------------------------------
    # Login waiter
    # ------------------------------------------------------------------

    def _wait_login(self) -> bool:
        if not self._logged_in:
            if self.in_team_and_world():
                return True
            self.handle_monthly_card()
            texts = self.ocr_box(self.box_of_screen(0.3, 0.3, 0.7, 0.7))
            if texts:
                if find_match(texts, re.compile(r"pp:[\d\.-]+", re.IGNORECASE)):
                    self.log_info("Login screen detected, clicking start")
                    self.click(0.499, 0.865, after_sleep=3)
                    return False
        return False

    def ocr_box(self, area: Box):
        """Perform OCR on a Box area. Returns list of text strings."""
        if self._last_screenshot is None:
            return []
        from module.ocr.ocr import Ocr
        ocr_obj = Ocr(buttons=[area.area], letter=(255, 255, 255), threshold=128)
        results = ocr_obj.ocr(self._last_screenshot)
        return results

    # ------------------------------------------------------------------
    # Monthly card
    # ------------------------------------------------------------------

    def find_monthly_card(self) -> Optional[Box]:
        """Find the monthly card popup."""
        return self.find_one(Labels.monthly_card)

    def should_check_monthly_card(self) -> bool:
        if self.next_monthly_card_start > 0:
            if 0 < time.time() - self.next_monthly_card_start < 120:
                return True
        return False

    def handle_monthly_card(self) -> bool:
        """Handle the monthly card popup if visible."""
        monthly_card = self.find_monthly_card()
        if monthly_card is not None:
            self.log_info("monthly_card found, closing")
            self.click(0.50, 0.89)
            self.sleep(2)
            self.click(0.50, 0.89)
            self.sleep(2)
            self.wait_until(
                self.in_team_and_world,
                time_out=10,
                post_action=lambda: self.click(0.50, 0.89, after_sleep=1),
            )
            self._set_check_monthly_card(next_day=True)
        return monthly_card is not None

    def _set_check_monthly_card(self, next_day: bool = False):
        now = datetime.now()
        hour = self.monthly_card_config.get("Monthly Card Time", 4)
        next_four_am = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if now >= next_four_am or next_day:
            next_four_am += timedelta(days=1)
        next_check = next_four_am - timedelta(seconds=30)
        self.next_monthly_card_start = next_check.timestamp()
        logger.info(f"set next monthly card start time to {next_check}")

    # ------------------------------------------------------------------
    # Claim / Reward
    # ------------------------------------------------------------------

    def send_interac(self, handle_claim: bool = True) -> bool:
        """Interact with nearby object and optionally handle claim popups."""
        if self.find_interac():
            self.send_key("f", after_sleep=0.8)
            if not handle_claim:
                return True
            return self._handle_claim_button()
        return False

    def _handle_claim_button(self) -> bool:
        while self.wait_until(self._has_claim, raise_if_not_found=False, time_out=1.5):
            self.sleep(0.5)
            self.send_key("esc")
            self.sleep(0.5)
            logger.info("handle_claim_button found a claim reward")
        return True

    def _has_claim(self) -> bool:
        return not self.is_in_team() and bool(self.find_all_claim())

    def find_all_claim(self) -> List[Box]:
        """Find all claim/reward icons on screen."""
        box = self.box_of_screen(0.2645, 0.6167, 0.7352, 0.6785, name="reward_area")
        return self.find_feature(Labels.claim_icon, box=box)

    # ------------------------------------------------------------------
    # Stamina
    # ------------------------------------------------------------------

    def get_stamina(self) -> int:
        """Read current stamina from the stamina display."""
        boxes = self._wait_ocr(0.814, 0.029, 0.898, 0.083, match=stamina_re)
        if not boxes:
            self.screenshot()
            return -1
        current = 0
        for box in boxes:
            if match := stamina_re.search(box.name):
                current = int(match.group(1))
        self.info_set("current stamina", current)
        return current

    def _wait_ocr(self, x1, y1, x2, y2, match=None, raise_if_not_found=False, time_out=5):
        box = self.box_of_screen(x1, y1, x2, y2, name="ocr_area")
        start = time.time()
        while time.time() - start < time_out:
            self.next_frame()
            from module.ocr.ocr import Ocr
            ocr_obj = Ocr(buttons=[box.area], letter=(255, 255, 255), threshold=128)
            results = ocr_obj.ocr(self._last_screenshot)
            if match is not None:
                import re as _re
                matched = []
                for r in results:
                    if isinstance(match, _re.Pattern):
                        if match.search(r):
                            matched.append(r)
                    elif isinstance(match, str):
                        if match in r:
                            matched.append(r)
                if matched:
                    return matched
            else:
                return results
            self.sleep(0.5)
        return []

    # ------------------------------------------------------------------
    # Color percentage
    # ------------------------------------------------------------------

    def calculate_color_percentage(self, color_range, box: Box) -> float:
        """Calculate the percentage of pixels matching a color range within a box."""
        from module.base.utils import crop, get_color
        frame = self._last_screenshot
        if frame is None:
            return 0.0
        roi = crop(frame, box.area)
        if roi is None or roi.size == 0:
            return 0.0
        mask = iu.create_color_mask(roi, color_range, to_bgr=False)
        total = mask.shape[0] * mask.shape[1]
        matching = cv2.countNonZero(mask)
        return matching / total if total > 0 else 0.0

    # ------------------------------------------------------------------
    # has_cd / available / is_cycle_full (combat support stubs)
    # ------------------------------------------------------------------

    def has_cd(self, name: str) -> bool:
        """Check if a skill is on cooldown. Stub for combat tasks."""
        return False

    def available(self, name: str, check_color: bool = True, check_cd: bool = True) -> bool:
        """Check if a skill is available. Stub for combat tasks."""
        return not self.has_cd(name)

    def is_cycle_full(self) -> bool:
        """Check if the cycle gauge is full. Stub for combat tasks."""
        return False

    # ------------------------------------------------------------------
    # operate (physical mouse control)
    # ------------------------------------------------------------------

    def operate(self, func: Callable, block: bool = False):
        """Execute a function via physical mouse interaction layer."""
        return func()

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    def is_foreground(self) -> bool:
        """Check if the game window is in the foreground."""
        if self._device_manager is None:
            return False
        return self._device_manager.is_foreground()

    def bring_to_front(self) -> bool:
        """Force the game window to the foreground."""
        if self._device_manager is None:
            return False
        hwnd = self._device_manager.hwnd
        if hwnd is None:
            return False
        if self.is_foreground():
            return True

        try:
            current_thread_id = win32api.GetCurrentThreadId()
            target_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
            foreground_hwnd = win32gui.GetForegroundWindow()
            foreground_thread_id = 0
            if foreground_hwnd:
                foreground_thread_id, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)

            attached_target = False
            attached_foreground = False

            if target_thread_id and target_thread_id != current_thread_id:
                attached_target = bool(
                    ctypes.windll.user32.AttachThreadInput(
                        current_thread_id, target_thread_id, True
                    )
                )
            if (
                foreground_thread_id
                and foreground_thread_id != current_thread_id
                and foreground_thread_id != target_thread_id
            ):
                attached_foreground = bool(
                    ctypes.windll.user32.AttachThreadInput(
                        current_thread_id, foreground_thread_id, True
                    )
                )

            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
            self.sleep(0.1)
            return self.is_foreground()
        except Exception:
            return False
        finally:
            if attached_foreground:
                ctypes.windll.user32.AttachThreadInput(
                    current_thread_id, foreground_thread_id, False
                )
            if attached_target:
                ctypes.windll.user32.AttachThreadInput(current_thread_id, target_thread_id, False)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def main_viewport(self) -> Box:
        """Main gameplay viewport (excludes UI edges)."""
        return self.box_of_screen(0.0984, 0.1042, 0.8961, 0.8944, name="main_viewport")

    # ------------------------------------------------------------------
    # Scene
    # ------------------------------------------------------------------

    @property
    def scene(self) -> Optional[NTEScene]:
        return getattr(self, '_scene', None)

    @scene.setter
    def scene(self, value):
        self._scene = value


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

_globals_instance = None
_globals_lock = threading.Lock()


def _get_globals():
    """Get or create the global Globals instance."""
    global _globals_instance
    if _globals_instance is None:
        with _globals_lock:
            if _globals_instance is None:
                from threading import Event
                _globals_instance = Globals(Event())
    return _globals_instance


def find_match(texts, pattern):
    """Find text matching a regex pattern in OCR results."""
    for t in texts:
        if pattern.search(str(t)):
            return True
    return False


def interac_pink_color():
    return {
        "r": (197, 221),
        "g": (71, 78),
        "b": (119, 133),
    }


def _interac_mask(image):
    mask = iu.create_color_mask(image, interac_pink_color(), to_bgr=False)
    dilated_mask = iu.morphology_mask(mask, to_bgr=False)
    return dilated_mask
