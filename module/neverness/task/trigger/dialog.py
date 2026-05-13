"""
SkipDialogTask - Auto skip dialog/cutscene via template matching.

Background trigger that detects dialog elements and clicks/keys to advance.
"""

import time

from module.util.logger import logger

from module.neverness.Labels import Labels
from module.neverness.task.base import BaseNTETask


class SkipDialogTask(BaseNTETask):
    """Background trigger for auto-skipping dialog and cutscenes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "skip_dialog"
        self.trigger_interval = 0.5
        self.default_config = {"_enabled": False}
        self.config.setdefault("skip_story", True)
        self.config.setdefault("auto_message", True)

        self._confirm_dialog_checked = False
        self._has_eye_time = 0
        self._check_confirm_timer = 0.0
        self._skip_message_hold = False

    # ------------------------------------------------------------------
    # Trigger entry point
    # ------------------------------------------------------------------

    def run(self):
        """Check for dialog elements and skip/advance them."""
        # Only run when NOT in team (i.e., in a UI/dialog)
        if self.is_in_team():
            return

        if self.config.get("skip_story") and self._in_story():
            if self._check_skip():
                return
            if self._check_options():
                return
            self._check_dialog_click()

        if self.config.get("auto_message") and self._skip_message():
            return

    # ------------------------------------------------------------------
    # Story/dialog detection
    # ------------------------------------------------------------------

    def _in_story(self) -> bool:
        """Check if currently in a story cutscene or dialog."""
        return bool(
            self.find_one(Labels.auto_play)
            or self._find_skip()
            or self._find_dialog_history()
        )

    def _find_skip(self):
        """Find the skip dialog button."""
        return self.find_one(
            Labels.skip_dialog,
            horizontal_variance=0.02,
            threshold=0.75,
            frame_processor=lambda img: isolate_dialog_to_white(img),
        )

    def _find_dialog_history(self):
        """Find the dialog history icon."""
        return self.find_one(
            Labels.dialog_history,
            threshold=0.8,
            box=self.box_of_screen(0.6887, 0.5160, 0.7121, 0.7764),
        )

    # ------------------------------------------------------------------
    # Skip actions
    # ------------------------------------------------------------------

    def _check_skip(self) -> bool:
        """Try clicking the skip button and handle the confirmation."""
        if self._try_click_skip():
            self._check_confirm_timer = time.time() + 3

        if self._check_confirm_timer > time.time():
            return self._do_skip_confirm()
        else:
            self._check_confirm_timer = 0
        return False

    def _try_click_skip(self) -> bool:
        """Repeatedly click the skip button while visible."""
        skipped = False
        while skip_btn := self._find_skip():
            logger.info("click skip dialog")
            self.operate_click(skip_btn)
            self.sleep(0.4)
            skipped = True
        return skipped

    def _do_skip_confirm(self) -> bool:
        """Handle the skip confirmation popup."""
        if skip_button := self.find_one(Labels.skip_quest_confirm, threshold=0.8):
            # Wait for confirm button to fully appear
            now = time.time()
            self.wait_until(
                lambda: self.calculate_color_percentage(_skip_confirm_color, skip_button) > 0.4,
                time_out=6,
            )
            if time.time() - now < 2.5:
                self.sleep(0.2)
                self.operate_click(0.4508, 0.5194)
                self.sleep(0.4)
            self.operate_click(skip_button)
            self.sleep(0.5)
            if not self.find_one(Labels.skip_quest_confirm, threshold=0.8):
                return True
        if self.is_in_team():
            return True
        return False

    def _check_options(self) -> bool:
        """Check and click dialog choice options."""
        boxes = self.find_feature(
            Labels.dialog_history,
            box=self.box_of_screen(0.6887, 0.5160, 0.7121, 0.7764),
            threshold=0.6,
        )
        if boxes:
            boxes.sort(key=lambda b: b.y)
            top_box = boxes[0]
            bottom_box = boxes[-1]
            if self.calculate_color_percentage(_option_pink_color, top_box) > 0.3:
                self.operate_click(bottom_box)
                self.sleep(0.1)
            return True
        return False

    def _check_dialog_click(self) -> bool:
        """Check for dialog click indicator and press space."""
        if self._find_dialog_history():
            if self.find_one(Labels.dialog_click, threshold=0.8, vertical_variance=0.02):
                self.send_key("space", after_sleep=0.1)
                return True
        return False

    # ------------------------------------------------------------------
    # Message skip
    # ------------------------------------------------------------------

    def _skip_message(self) -> bool:
        """Skip message/notification popups."""
        if self.find_one(Labels.message) and self._find_message_dialog():
            self.sleep(0.1)
            msg_dialog = self._find_message_dialog()
            if msg_dialog:
                self.operate_click(msg_dialog)
                self.sleep(1)
                self.log_info(f"clicked message {msg_dialog}")
                return True
        return False

    def _find_message_dialog(self):
        return self.find_one(
            Labels.message_dialog,
            vertical_variance=0.2,
            horizontal_variance=0.01,
        )


# ---------------------------------------------------------------------------
# Color definitions
# ---------------------------------------------------------------------------

_skip_confirm_color = {
    "r": (208, 217),
    "g": (208, 217),
    "b": (208, 217),
}

_option_pink_color = {
    "r": (235, 250),
    "g": (75, 85),
    "b": (140, 145),
}

_dialog_white_color = {
    "r": (220, 240),
    "g": (220, 240),
    "b": (220, 240),
}


def isolate_dialog_to_white(cv_image):
    """Create a white mask from dialog elements."""
    from module.neverness.util import image as iu
    return iu.create_color_mask(cv_image, _dialog_white_color, invert=False)
