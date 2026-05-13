"""
FishingTask - Automatic fishing for Neverness-to-Everness.

FAITHFUL port from ok-nte FishingTask.py.

Features:
- HSV-based fishing bar detection (green zone + yellow pointer)
- Long-press (smooth) and tap (safe) control modes
- Smoothstep curve for tap mode force calculation
- Blue HSV bite detection (>7% pixel ratio in ring zone)
- Auto bait/sell/buy flow
- Monthly card handling during control loop
"""

import time

import cv2
import numpy as np

from module.task.exceptions import TaskDisabledError
from module.feature.box import Box
from module.util.logger import logger

from module.neverness.Labels import Labels
from module.neverness.task.onetime import NTEOneTimeTask
from module.neverness.task.base import BaseNTETask
from module.neverness.util import image as iu


# ---------------------------------------------------------------------------
# Color definitions
# ---------------------------------------------------------------------------

fishing_bite_blue_color = {
    "r": (30, 35),
    "g": (120, 130),
    "b": (250, 255),
}

text_black_color = {
    "r": (0, 10),
    "g": (0, 10),
    "b": (0, 10),
}

default_bait_color = {
    "r": (140, 255),
    "g": (40, 140),
    "b": (100, 190),
}

text_white_color = {
    "r": (210, 255),
    "g": (210, 255),
    "b": (210, 255),
}

# ---------------------------------------------------------------------------
# FishingTask
# ---------------------------------------------------------------------------


class FishingTask(NTEOneTimeTask, BaseNTETask):
    """Automatic fishing task with HSV bar control and bite detection."""

    # Configuration keys
    CONF_ROUNDS = "rounds"
    CONF_CONTROL_MODE = "control_mode"
    CONF_TAP_MULTIPLIER = "tap_multiplier"
    CONF_USE_ESC = "use_esc"
    CONF_AUTO_BUY_BAIT = "auto_buy_bait"

    # Control mode options
    MODE_HOLD = "hold"
    MODE_TAP = "tap"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "fishing"
        self._setup_defaults()

        # Runtime state
        self._last_bar_log_time = 0.0
        self._morph_kernel = np.ones((3, 3), dtype=np.uint8)
        self._bar_active_key = None
        self._last_direction = None
        self._monthly_card_pause_time = 0.0

    def _setup_defaults(self):
        self.config.setdefault(self.CONF_ROUNDS, 1)
        self.config.setdefault(self.CONF_CONTROL_MODE, self.MODE_HOLD)
        self.config.setdefault(self.CONF_TAP_MULTIPLIER, 1.0)
        self.config.setdefault(self.CONF_USE_ESC, False)
        self.config.setdefault(self.CONF_AUTO_BUY_BAIT, True)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self):
        super().run()
        try:
            return self._do_run()
        except TaskDisabledError:
            pass
        except Exception as e:
            self.log_error("FishingTask error", e)
            raise

    def _do_run(self):
        self._reset_runtime_state()
        if not self._enter_fishing_scene():
            raise TaskDisabledError("failed to enter fishing scene")

        rounds = max(1, int(self.config.get(self.CONF_ROUNDS, 1)))
        self.log_info(f"fishing: {rounds} round(s)")

        success_count = 0
        for i in range(rounds):
            self.log_info(f"round {i + 1}/{rounds}")
            self.info_set("round", f"{i + 1}/{rounds}")
            if self._run_once(i + 1):
                success_count += 1
            else:
                self.log_error(f"round {i + 1} failed")
                self._reset_runtime_state()

        self.info_set("success count", success_count)
        self.log_info(f"fishing done: {success_count}/{rounds}", notify=True)

    # ------------------------------------------------------------------
    # Single round
    # ------------------------------------------------------------------

    def _run_once(self, round_index: int) -> bool:
        """Execute one complete fishing round: close overlay, cast, wait bite, control."""
        if not self._close_success_overlay():
            self.screenshot()
            raise TaskDisabledError("failed to close success overlay")

        if not self._cast_rod():
            raise TaskDisabledError("cast rod failed")

        if not self._wait_bite():
            self.screenshot()
            return False

        return self._control_until_finish()

    # ------------------------------------------------------------------
    # Scene entry
    # ------------------------------------------------------------------

    def _enter_fishing_scene(self) -> bool:
        """Detect and enter the fishing preparation scene."""
        ENTER_SCENE_TIMEOUT = 5

        if self._is_fish_start_exist() or self._is_success_overlay():
            self.log_info("already in fishing scene")
            return True

        if self._wait_until_pause_aware(
            self.find_interac,
            time_out=ENTER_SCENE_TIMEOUT,
        ):
            box = self.box_of_screen(0.9094, 0.8278, 0.9746, 0.9104)

            if not self._wait_until_pause_aware(
                lambda: self.find_one(Labels.skip_quest_confirm, box=box) is not None,
                pre_action=lambda: self.send_key("f", interval=1.5, action_name="enter_panel_f"),
                time_out=ENTER_SCENE_TIMEOUT,
            ):
                self.log_error("fishing panel entry not detected")
                return False

            self.operate_click(box)
            self.sleep(1.5)

        if not self._wait_until_pause_aware(
            self._is_fish_start_exist,
            time_out=ENTER_SCENE_TIMEOUT,
        ):
            self.log_error("cast-ready state not detected after entering")
            return False

        self.log_info("entered fishing scene")
        return True

    # ------------------------------------------------------------------
    # Cast rod
    # ------------------------------------------------------------------

    def _cast_rod(self) -> bool:
        """Cast the fishing rod and wait for cast-complete state."""
        self.log_info("casting rod")

        if self._wait_cast_rod(7.5):
            return True

        if not self.config.get(self.CONF_AUTO_BUY_BAIT, True):
            self.log_warning("cast timeout, auto-bait disabled, aborting")
            return self._cast_rod_failed()

        self.log_warning("cast timeout, switching to default bait")
        if not self._change_to_default_bait():
            return self._cast_rod_failed()

        self._sell_fish()
        if self._wait_cast_rod(10):
            return True

        return self._cast_rod_failed()

    def _cast_rod_failed(self) -> bool:
        self.send_key("f")
        frame = self._last_screenshot
        self.screenshot()
        self.log_error("cast rod timeout", notify=True)
        return False

    def _wait_cast_rod(self, time_out: float) -> bool:
        return bool(
            self._wait_until_pause_aware(
                self._is_cast_rod_done,
                pre_action=lambda: self.send_key("f", interval=1.5, action_name="cast_rod_f"),
                post_action=lambda: self._close_success_overlay_once("closing overlay during cast"),
                time_out=time_out,
            )
        )

    def _is_cast_rod_done(self) -> bool:
        return (
            not self._is_success_overlay()
            and not self._is_fish_bait_exist()
            and self._is_fish_start_exist()
        )

    # ------------------------------------------------------------------
    # Wait bite
    # ------------------------------------------------------------------

    def _wait_bite(self) -> bool:
        """Wait for fish to bite the bait."""
        self.log_info("waiting for bite")

        if self._wait_until_pause_aware(
            self._is_fishing_bite,
            post_action=lambda: self._close_success_overlay_once("overlay during bite wait"),
            time_out=20,
        ):
            self.log_info("fish bite detected")

            if not self._wait_until_pause_aware(
                lambda: not self._is_fish_start_exist(),
                pre_action=lambda: self.send_key("f", interval=2, action_name="bite_f"),
                time_out=10,
            ):
                self.log_error("did not enter reeling state")
                return False

            self.log_info("entered reeling state")
            return True
        else:
            self.log_error("bite wait timeout")
            return False

    # ------------------------------------------------------------------
    # Control loop
    # ------------------------------------------------------------------

    def _control_until_finish(self) -> bool:
        """Real-time fishing bar control loop until success or failure."""
        start_check_time = time.time() + 1.0
        deadline = time.time() + 30.0
        failed_time = 0

        try:
            while time.time() < deadline:
                state = self._detect_fishing_bar_state()
                if self._is_valid_bar_state(state):
                    self._apply_bar_control(state)
                else:
                    self._clear_bar_key_if_hold_mode()

                if time.time() > start_check_time:
                    if self._is_fish_bait_exist():
                        if failed_time == 0:
                            failed_time = time.time()
                    else:
                        failed_time = 0

                    if failed_time != 0 and time.time() - failed_time > 5:
                        self.log_error("fish may have escaped")
                        return False

                    if self._is_success_overlay():
                        return True

                self.sleep(0.01)
                pause_time = self._consume_monthly_card_pause_time()
                if pause_time > 0:
                    deadline += pause_time
                    start_check_time += pause_time
                    if failed_time != 0:
                        failed_time += pause_time

            self.log_error("control phase timeout")
            return False
        finally:
            self._clear_bar_key_if_hold_mode()

    # ------------------------------------------------------------------
    # Bar control: hold mode (smooth)
    # ------------------------------------------------------------------

    def _apply_bar_control(self, state: dict):
        """Dispatch to the correct control mode."""
        mode = self.config.get(self.CONF_CONTROL_MODE, self.MODE_HOLD)
        if mode == self.MODE_TAP:
            self._apply_bar_control_discrete(state)
        else:
            self._apply_bar_control_hold(state)

    def _apply_bar_control_hold(self, state: dict):
        """Long-press control mode: smooth continuous adjustment."""
        now = time.time()
        pointer, zone_center, zone_width = self._bar_metrics(state)
        error = pointer - zone_center
        abs_error = abs(error)

        deadzone = max(2, int(zone_width * 0.08))

        if abs_error <= deadzone:
            self._set_bar_key(None)
            if now - self._last_bar_log_time > 1:
                self.log_debug(f"pointer locked: pointer={pointer}, target={zone_center}")
                self._last_bar_log_time = now
            return

        key = "d" if error < 0 else "a"
        self._set_bar_key(key)

    # ------------------------------------------------------------------
    # Bar control: tap mode (safe, discrete)
    # ------------------------------------------------------------------

    def _apply_bar_control_discrete(self, state: dict):
        """Tap control mode: discrete key presses with smoothstep curve.

        Uses a smoothstep (ratio^2 * (3 - 2*ratio)) to calculate hold duration,
        producing gentler adjustments near center and stronger near edges.
        """
        now = time.time()
        pointer, zone_center, zone_width = self._bar_metrics(state)
        dist_from_center = pointer - zone_center
        abs_dist = abs(dist_from_center)

        if abs_dist <= max(2, int(zone_width * 0.08)):
            if now - self._last_bar_log_time > 0.5:
                self.log_debug(f"pointer locked: pointer={pointer}, target={zone_center}")
                self._last_bar_log_time = now
            return

        key = "d" if dist_from_center < 0 else "a"
        ratio = min(1.0, abs_dist / (zone_width / 2))
        # Smoothstep curve: smooth acceleration from center to edges
        curve = ratio * ratio * (3 - 2 * ratio)
        hold = 0.01 + curve * 0.18

        # Reduce force on direction change to avoid overshoot
        if key != self._last_direction:
            hold *= 0.6

        self._last_direction = key

        # Apply user multiplier
        multiplier = float(self.config.get(self.CONF_TAP_MULTIPLIER, 1.0))
        hold *= multiplier

        # Clamp
        hold = min(0.2, max(0.01, hold))

        self.send_key(key, down_time=hold)

    # ------------------------------------------------------------------
    # Key state management
    # ------------------------------------------------------------------

    def _set_bar_key(self, key):
        """Set the active bar control key, releasing previous if different."""
        if key == self._bar_active_key:
            return

        if self._bar_active_key is not None:
            self.send_key_up(self._bar_active_key)
            self._bar_active_key = None

        if key is not None:
            self.send_key_down(key)
            self._bar_active_key = key

    def _clear_bar_key_if_hold_mode(self):
        """Release key if in hold mode (avoid stuck keys)."""
        if self.config.get(self.CONF_CONTROL_MODE, self.MODE_HOLD) == self.MODE_HOLD:
            self._set_bar_key(None)

    def _bar_metrics(self, state: dict):
        """Extract pointer, zone center, and zone width from state dict."""
        return (
            int(state["pointer_center"]),
            int(state["zone_center"]),
            max(1, int(state["zone_width"])),
        )

    def _is_valid_bar_state(self, state) -> bool:
        """Validate bar detection state for reasonableness."""
        if state is None:
            return False
        zone_left = int(state.get("zone_left", 0))
        zone_right = int(state.get("zone_right", 0))
        pointer_center = int(state.get("pointer_center", -1))
        image_width = max(1, int(state.get("image_width", 1)))
        zone_width = max(0, int(state.get("zone_width", zone_right - zone_left)))
        ratio = zone_width / image_width

        # Zone must be between 5% and 55% of image width
        if not (0.05 <= ratio <= 0.55):
            return False
        if not (0 <= pointer_center < image_width):
            return False

        # Filter edge-zone false positives where pointer is far from zone
        edge_zone = zone_left <= 1 or zone_right >= image_width - 2
        if edge_zone and abs(pointer_center - int((zone_left + zone_right) / 2)) > int(
            image_width * 0.38
        ):
            return False
        return True

    # ------------------------------------------------------------------
    # Success overlay handling
    # ------------------------------------------------------------------

    def _is_success_overlay(self) -> bool:
        return self.find_one(Labels.fising_sucess) is not None

    def _close_success_overlay(self) -> bool:
        if self._is_success_overlay():
            self.log_info("success overlay detected, closing")
        elif self._is_fish_start_exist():
            self.log_info("already in cast-ready state")
            return True

        if self._wait_until_pause_aware(
            lambda: not self._is_success_overlay(),
            pre_action=self._close_success_overlay_once,
            time_out=20,
        ):
            self.log_info("success overlay closed")
        else:
            self.log_error("failed to close success overlay")
            return False

        if self._wait_until_pause_aware(self._is_fish_start_exist, time_out=5):
            self.log_info("returned to cast-ready state")
            self.sleep(0.5)
        else:
            self.log_error("did not return to cast-ready state")
            return False
        return True

    def _close_success_overlay_once(self, log_message=None):
        if not self._is_success_overlay():
            return False
        closed = self._do_close_success_overlay()
        if not closed:
            return False
        if log_message:
            self.log_info(log_message)
        return True

    def _do_close_success_overlay(self):
        if self.config.get(self.CONF_USE_ESC):
            return self.send_key("esc", interval=2, action_name="close_success_overlay")
        return self.operate_click(0.12, 0.88, interval=2, action_name="close_success_overlay")

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _is_fish_start_exist(self) -> bool:
        """Detect if the 'start fishing' button is visible."""
        def _frame_process(img):
            return iu.create_color_mask(img, text_white_color)
        return self.find_one(Labels.fish_start, frame_processor=_frame_process) is not None

    def _is_fish_bait_exist(self) -> bool:
        """Detect if the bait icon is visible."""
        return self.find_one(Labels.fish_bait) is not None

    def _is_fishing_bite(self) -> bool:
        """Detect bite via blue HSV pixel ratio in the indicator ring zone.

        The indicator is a circle; blue pixels inside the ring (>7% ratio)
        indicate a bite.
        """
        box = self.box_of_screen(0.9023, 0.8562, 0.9488, 0.9403, name="fishing_bite_indicator")
        image = box.crop_frame(self._last_screenshot)

        if image is None or image.size == 0:
            return False

        blue_mask = iu.create_color_mask(image, fishing_bite_blue_color, to_bgr=False)

        h, w = blue_mask.shape[:2]
        center = (w // 2, h // 2)
        max_radius = min(h, w) // 2
        target_radius = int(max_radius * 0.7)

        # Create a ring mask excluding the center
        circle_mask = np.ones((h, w), dtype="uint8")
        cv2.circle(circle_mask, center, target_radius, 0, -1)

        masked_blue = cv2.bitwise_and(blue_mask, circle_mask)
        blue_pixels = int(cv2.countNonZero(masked_blue))
        total_circle_pixels = int(cv2.countNonZero(circle_mask))

        if total_circle_pixels == 0:
            return False

        blue_pixels_ratio = blue_pixels / total_circle_pixels
        return blue_pixels_ratio > 0.07

    def _detect_fishing_bar_state(self):
        """HSV-based fishing bar detection.

        Green zone: HSV (50-160, 150-220, 160-255)
        Yellow pointer: HSV (20-55, 60-200, 195-255)

        Returns dict with zone_left, zone_right, zone_center, zone_width,
        pointer_center, and image_width, or None if detection fails.
        """
        box = self.box_of_screen(0.3164, 0.0646, 0.6875, 0.0743, name="fishing_bar")
        image = box.crop_frame(self._last_screenshot)
        if image is None or image.size == 0:
            return None

        # Green zone mask
        green_mask = iu.filter_by_hsv(
            image, iu.HSVRange((50, 150, 160), (160, 220, 255)), return_mask=True
        )
        # Yellow pointer mask
        yellow_mask = iu.filter_by_hsv(
            image, iu.HSVRange((20, 60, 195), (55, 200, 255)), return_mask=True
        )

        # Morphological cleanup
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, self._morph_kernel)
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, self._morph_kernel)
        yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_OPEN, self._morph_kernel)
        yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_CLOSE, self._morph_kernel)

        # Find yellow pointer
        yellow_contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if yellow_contours:
            yellow_max = max(yellow_contours, key=cv2.contourArea)
            px, _, pw, _ = cv2.boundingRect(yellow_max)
            pointer_center = px + pw // 2
        else:
            pointer_center = -1

        # Find green zone candidates
        green_contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        green_candidates = []
        for contour in green_contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w >= 5 and h >= 5:
                area = w * h
                green_candidates.append((x, y, w, h, area))

        if not green_candidates:
            return None

        # Sort by area descending, take top 2
        green_candidates.sort(key=lambda item: item[4], reverse=True)
        top_2 = green_candidates[:2]
        top_2.sort(key=lambda item: item[0])  # Sort by x ascending

        if len(top_2) == 1:
            zone_left = top_2[0][0]
            zone_right = top_2[0][0] + top_2[0][2]
        else:
            zone_left = top_2[0][0]
            zone_right = max(
                top_2[0][0] + top_2[0][2],
                top_2[1][0] + top_2[1][2],
            )

        zone_w = zone_right - zone_left

        return {
            "zone_left": zone_left,
            "zone_right": zone_right,
            "zone_center": zone_left + zone_w // 2,
            "zone_width": zone_w,
            "image_width": int(image.shape[1]),
            "pointer_center": pointer_center,
            "in_zone": zone_left <= pointer_center <= zone_right,
        }

    # ------------------------------------------------------------------
    # Bait / Sell / Buy helpers
    # ------------------------------------------------------------------

    def _find_default_bait(self):
        """Find the default bait slot in the bait selection UI."""
        box1 = self.box_of_screen(0.0602, 0.2306, 0.313, 0.2597)
        box2 = self.box_of_screen(0.0602, 0.4516, 0.313, 0.4807)

        candidates = []
        for box in (box1, box2):
            image = box.crop_frame(self._last_screenshot)
            if image is None:
                continue
            mask = iu.create_color_mask(image, default_bait_color, to_bgr=False)
            mask = iu.morphology_mask(mask, closing=True, to_bgr=False)

            num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
            for i in range(1, num_labels):
                candidates.append({
                    "area": stats[i, cv2.CC_STAT_AREA],
                    "x": box.x + stats[i, cv2.CC_STAT_LEFT],
                    "y": box.y + stats[i, cv2.CC_STAT_TOP],
                    "w": stats[i, cv2.CC_STAT_WIDTH],
                    "h": stats[i, cv2.CC_STAT_HEIGHT],
                })

        if not candidates:
            return None

        max_area = max(c["area"] for c in candidates)
        similar = [c for c in candidates if c["area"] >= max_area * 0.9]
        best = min(similar, key=lambda c: (c["x"], c["y"]))
        return Box(best["x"], best["y"], best["w"], best["h"], name="default_bait")

    def _click_default_bait(self):
        box = self._find_default_bait()
        if box:
            self.operate_click(box)
        else:
            self.operate_click(0.185, 0.243)

    def _sell_fish(self):
        """Sell all fish in inventory."""
        self.send_key("q")
        self.sleep(1)
        self.operate_click(0.076, 0.386)
        self.sleep(1)
        self.operate_click(0.556, 0.898)
        self.sleep(1)
        self.operate_click(0.609, 0.656)
        self.sleep(2)
        self._back_to_fishing_scene()
        self.sleep(1)

    def _buy_bait(self):
        """Buy default bait."""
        self._click_default_bait()
        self.sleep(0.25)
        self.operate_click(0.9520, 0.8812)
        self.sleep(0.25)
        self.operate_click(0.8715, 0.9542)
        self.sleep(1)
        self.operate_click(0.609, 0.661)
        self.sleep(2)
        self._back_to_fishing_scene()
        self.sleep(1)

    def _back_to_fishing_scene(self):
        """Return to the fishing cast-ready scene."""
        self._wait_until_pause_aware(
            self._is_fish_start_exist,
            post_action=lambda: self.send_key("esc", action_name="back_to_fishing_scene", interval=2),
            time_out=10,
        )

    def _change_to_default_bait(self) -> bool:
        """Switch to default bait and verify."""
        def _choose_bait():
            self.send_key("e")
            self.sleep(2)
            self.operate_click(0.613, 0.655)
            self.sleep(1)
            self.operate_click(0.613, 0.655)

        _choose_bait()
        if self._wait_until_pause_aware(self._is_fish_start_exist, time_out=2):
            return True

        self._buy_bait()
        _choose_bait()
        return bool(self._wait_until_pause_aware(self._is_fish_start_exist, time_out=2))

    # ------------------------------------------------------------------
    # Pause-aware wait loop (monthly card)
    # ------------------------------------------------------------------

    def _wait_until_pause_aware(
        self,
        condition,
        time_out: float = 5,
        pre_action=None,
        post_action=None,
    ):
        """Wait for condition, accounting for monthly card pause time."""
        deadline = time.time() + time_out
        while True:
            if pre_action is not None:
                pre_action()
            result = condition()
            if result:
                return result
            if post_action is not None:
                post_action()
            self._sleep_briefly()
            deadline += self._consume_monthly_card_pause_time()
            if time.time() > deadline:
                return None

    def _sleep_briefly(self):
        self.sleep(0.1)

    def _consume_monthly_card_pause_time(self) -> float:
        """Consume and return accumulated monthly card pause time."""
        pause_time = self._monthly_card_pause_time
        self._monthly_card_pause_time = 0.0
        return pause_time

    def _reset_runtime_state(self):
        """Reset all runtime tracking state."""
        self._set_bar_key(None)
        self._last_bar_log_time = 0.0
        self._last_direction = None
        self._bar_active_key = None
        self._monthly_card_pause_time = 0.0

    # ------------------------------------------------------------------
    # Monthly card handling (overridden for fishing safety)
    # ------------------------------------------------------------------

    def handle_monthly_card(self) -> bool:
        """Handle monthly card popup during fishing (clears bar key first)."""
        monthly_card = self.find_monthly_card()
        if monthly_card is not None:
            self._clear_bar_key_if_hold_mode()
            self.log_info("monthly card found, closing")
            self.click(0.50, 0.89)
            self.sleep(2)
            self.click(0.50, 0.89)
            self.sleep(2)
            if self.find_monthly_card() is None:
                self._set_check_monthly_card(next_day=True)
            else:
                self.log_warning("monthly card close failed")
        return monthly_card is not None

    def _sleep_check(self):
        """Called during sleep; check for monthly card."""
        if self.should_check_monthly_card():
            start = time.time()
            if self.handle_monthly_card():
                self._monthly_card_pause_time += time.time() - start
