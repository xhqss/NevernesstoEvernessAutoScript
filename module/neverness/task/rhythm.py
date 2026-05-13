"""
RhythmTask - Automatic rhythm game (鼓组音游) for Neverness-to-Everness.

FAITHFUL port from ok-nte RhythmTask.py.

Features:
- 4-column note detection via brightness threshold at fixed detection points
- Async producer-consumer key dispatch with threading.Condition
- RETRIGGER_INTERVAL for sustained notes (0.085s)
- Finish detection via color percentage on result screen
- Multi-song loop support
"""

import threading
import time
from collections import deque

import numpy as np

from module.task.exceptions import TaskDisabledError
from module.util.logger import logger

from module.neverness.task.onetime import NTEOneTimeTask
from module.neverness.task.base import BaseNTETask


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Detection points (ratio-based) for each of the 4 columns
DETECT_POINTS = {
    "d": (0.2301, 0.7715),
    "f": (0.4055, 0.7715),
    "j": (0.5941, 0.7715),
    "k": (0.7699, 0.7715),
}

# Brightness threshold: values below this mean a note is passing
# (background ~245, note ~28)
BRIGHTNESS_THRESHOLD = 100

# Finish (result) screen close button position
FINISH_CLOSE_POS = (0.5402, 0.0437)

# Song start button position
SONG_START_POS = (0.8313, 0.9313)

# Detection window radius in pixels
DETECT_RADIUS_X = 5
DETECT_RADIUS_Y = 10

# Ratio of dark pixels within the detection window to trigger a note press
DARK_RATIO_THRESHOLD = 0.06

# Minimum interval between repeated presses on the same key (sustained notes)
RETRIGGER_INTERVAL = 0.085

# Key press duration
KEY_DOWN_TIME = 0.005

# Finish check interval (seconds) - avoid running color detection every frame
FINISH_CHECK_INTERVAL = 2.0


# ---------------------------------------------------------------------------
# Color definitions for scene detection
# ---------------------------------------------------------------------------

finish_yellow_color = {
    "r": (220, 230),
    "g": (170, 180),
    "b": (85, 90),
}

finish_red_color = {
    "r": (220, 230),
    "g": (90, 100),
    "b": (85, 90),
}

song_select_pink_color = {
    "r": (180, 220),
    "g": (35, 50),
    "b": (100, 120),
}


# ---------------------------------------------------------------------------
# RhythmTask
# ---------------------------------------------------------------------------


class RhythmTask(NTEOneTimeTask, BaseNTETask):
    """Automatic rhythm game player for Neverness-to-Everness drum game."""

    CONF_TIMEOUT_SECONDS = "timeout_seconds"
    CONF_DEBUG_LOG = "debug_log"
    CONF_LOOP_COUNT = "loop_count"
    CONF_TRACK_KEYS = "track_keys"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "rhythm_game"
        self._setup_defaults()

        # Runtime state
        self._prev_state = dict.fromkeys(DETECT_POINTS, False)
        self._last_press_time = dict.fromkeys(DETECT_POINTS, 0.0)
        self._last_finish_check = 0.0
        self._key_queue = deque()
        self._key_queue_cv = threading.Condition()
        self._key_worker = None
        self._key_worker_stop = False
        self._px_cache = None
        self._cache_shape = None

    def _setup_defaults(self):
        self.config.setdefault(self.CONF_TIMEOUT_SECONDS, 180)
        self.config.setdefault(self.CONF_DEBUG_LOG, False)
        self.config.setdefault(self.CONF_LOOP_COUNT, 0)
        self.config.setdefault(self.CONF_TRACK_KEYS, "d, f, j, k")

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
            self.log_error("RhythmTask error", e)
            raise

    def _do_run(self):
        total = int(self.config.get(self.CONF_LOOP_COUNT, 1))
        endless = total == 0
        count = 0

        while endless or count < total:
            count += 1
            label = f"song {count}" + ("" if endless else f"/{total}")

            # Click start button
            self.log_info(f"{label}: clicking start")
            self.operate_click(SONG_START_POS[0], SONG_START_POS[1])

            # Wait to leave song select screen (max 15s)
            self.log_info("waiting to enter rhythm screen")
            deadline_load = time.time() + 15
            while time.time() < deadline_load:
                self.sleep(0.3)
                if not self._is_song_select():
                    break
            else:
                self.log_error("did not enter rhythm screen within 15s")
                raise TaskDisabledError("timeout waiting for rhythm screen")

            self.sleep(1.0)  # Let UI stabilize

            # Reset per-song state
            self._prev_state = dict.fromkeys(DETECT_POINTS, False)
            self._last_press_time = dict.fromkeys(DETECT_POINTS, 0.0)
            self._last_finish_check = 0.0
            self._start_key_worker()

            # Main song loop
            self._run_single()

            # Handle finish screen
            self._handle_finish()

            # Wait for song select screen if looping
            if endless or count < total:
                self.log_info("waiting for song select screen")
                self.sleep(1.0)
                deadline = time.time() + 10
                while time.time() < deadline:
                    if self._is_song_select():
                        break
                    self.sleep(0.5)
                else:
                    self.log_error("did not return to song select screen within 10s")
                    raise TaskDisabledError("timeout waiting for song select after finish")

        self.log_info(f"rhythm task done: {count} songs completed", notify=True)

    # ------------------------------------------------------------------
    # Single song
    # ------------------------------------------------------------------

    def _run_single(self):
        """Main detection + dispatch loop for one song."""
        timeout = float(self.config.get(self.CONF_TIMEOUT_SECONDS, 180))
        deadline = time.time() + timeout
        self.log_info("rhythm started, keys: D/F/J/K")

        try:
            while time.time() < deadline:
                now = time.time()
                # Periodic finish check
                if now - self._last_finish_check >= FINISH_CHECK_INTERVAL:
                    self._last_finish_check = now
                    if self._is_finished():
                        self.log_info("result screen detected")
                        return
                self._tick()
                self.next_frame()
            self.log_error(f"song timeout after {timeout}s")
            raise TaskDisabledError("song timeout")
        finally:
            self._stop_key_worker()

    # ------------------------------------------------------------------
    # Per-frame tick
    # ------------------------------------------------------------------

    def _tick(self):
        """Detect notes and dispatch key presses for the current frame."""
        state = self._detect_notes()
        key_map = self._get_key_map()
        col_name = {"d": "col1", "f": "col2", "j": "col3", "k": "col4"}

        now = time.time()
        for track, has_note in state.items():
            prev = self._prev_state[track]
            can_retrigger = (
                has_note
                and prev
                and now - self._last_press_time[track] >= RETRIGGER_INTERVAL
            )
            if has_note and (not prev or can_retrigger):
                actual_key = key_map[track]
                self._queue_press(actual_key, col_name[track])
                self._last_press_time[track] = now
            self._prev_state[track] = has_note

    def _get_key_map(self) -> dict:
        """Parse track key configuration into a dict mapping track -> key."""
        raw_keys = str(self.config.get(self.CONF_TRACK_KEYS, "d, f, j, k"))
        keys = [k.strip() for k in raw_keys.split(",")]
        defaults = ["d", "f", "j", "k"]
        keys = [(keys[i] if i < len(keys) and keys[i] else defaults[i]) for i in range(4)]
        return dict(zip(DETECT_POINTS, keys))

    # ------------------------------------------------------------------
    # Async key dispatch (producer-consumer)
    # ------------------------------------------------------------------

    def _start_key_worker(self):
        """Start the background key dispatch worker thread."""
        if self._key_worker and self._key_worker.is_alive():
            return
        with self._key_queue_cv:
            self._key_queue.clear()
            self._key_worker_stop = False
        self._key_worker = threading.Thread(target=self._key_worker_loop, daemon=True)
        self._key_worker.start()

    def _stop_key_worker(self, timeout: float = 1.0):
        """Stop the key dispatch worker thread."""
        with self._key_queue_cv:
            self._key_worker_stop = True
            self._key_queue.clear()
            self._key_queue_cv.notify_all()
        if self._key_worker:
            self._key_worker.join(timeout=timeout)
            if not self._key_worker.is_alive():
                self._key_worker = None

    def _queue_press(self, key: str, col: str = ""):
        """Enqueue a key press for the worker thread."""
        with self._key_queue_cv:
            self._key_queue.append((key, col))
            self._key_queue_cv.notify()

    def _key_worker_loop(self):
        """Background worker that consumes the key queue and sends presses."""
        while True:
            with self._key_queue_cv:
                while not self._key_queue and not self._key_worker_stop:
                    self._key_queue_cv.wait(timeout=0.05)
                if self._key_worker_stop and not self._key_queue:
                    return
                key, col = self._key_queue.popleft()

            self.send_key(key, interval=0, down_time=KEY_DOWN_TIME)
            self.log_info(f"key {key.upper()} ({col})")

    # ------------------------------------------------------------------
    # Note detection via brightness threshold
    # ------------------------------------------------------------------

    def _detect_notes(self) -> dict:
        """Detect notes at the 4 hit-line detection points using brightness.

        For each detection point, a small ROI is examined. If the ratio of
        dark pixels (brightness < BRIGHTNESS_THRESHOLD) exceeds
        DARK_RATIO_THRESHOLD, a note is considered present.
        """
        frame = self._last_screenshot
        if frame is None:
            return dict.fromkeys(DETECT_POINTS, False)

        fh, fw = frame.shape[:2]

        # Cache pixel coordinates (recalculate on resolution change)
        if self._cache_shape != (fh, fw):
            self._px_cache = {
                k: (int(x * fw), int(y * fh)) for k, (x, y) in DETECT_POINTS.items()
            }
            self._cache_shape = (fh, fw)

        debug = bool(self.config.get(self.CONF_DEBUG_LOG, False))
        result = {}
        debug_parts = [] if debug else None

        for key, (px, py) in self._px_cache.items():
            x1 = max(0, px - DETECT_RADIUS_X)
            x2 = min(fw, px + DETECT_RADIUS_X + 1)
            y1 = max(0, py - DETECT_RADIUS_Y)
            y2 = min(fh, py + DETECT_RADIUS_Y + 1)
            roi = frame[y1:y2, x1:x2]

            # Compute per-pixel brightness (mean of BGR channels)
            pixel_brightness = roi.mean(axis=2) if roi.ndim == 3 else roi
            dark_ratio = float((pixel_brightness < BRIGHTNESS_THRESHOLD).mean())
            brightness = int(pixel_brightness.mean())
            has_note = dark_ratio >= DARK_RATIO_THRESHOLD
            result[key] = has_note

            if debug:
                debug_parts.append(
                    f"{key.upper()}:{brightness}/{dark_ratio:.2f}"
                    f"{' hit' if has_note else ' miss'}"
                )

        if debug:
            self.log_info("detect | " + " | ".join(debug_parts))

        return result

    # ------------------------------------------------------------------
    # Scene detection
    # ------------------------------------------------------------------

    def _is_finished(self) -> bool:
        """Detect if the result/finish screen is showing via color percentage."""
        yellow_box = self.box_of_screen(0.2211, 0.6625, 0.3156, 0.6965, name="finish_yellow")
        red_box = self.box_of_screen(0.4555, 0.6625, 0.5445, 0.6965, name="finish_red")
        yellow_pct = self.calculate_color_percentage(finish_yellow_color, yellow_box)
        red_pct = self.calculate_color_percentage(finish_red_color, red_box)
        return red_pct > 0.5 or yellow_pct > 0.5

    def _handle_finish(self):
        """Close the finish/result screen."""
        self.log_info("closing result screen")
        self.sleep(1.5)
        self.click(FINISH_CLOSE_POS[0], FINISH_CLOSE_POS[1])
        self.sleep(1.0)

    def _is_song_select(self) -> bool:
        """Detect if the song select screen is showing."""
        pink_box = self.box_of_screen(0.7441, 0.8306, 0.9336, 0.8632, name="song_select_pink")
        pink_pct = self.calculate_color_percentage(song_select_pink_color, pink_box)
        return pink_pct > 0.9
