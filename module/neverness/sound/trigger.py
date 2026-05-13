"""DodgeCounterTrigger – translates sound events into game input actions.

FAITHFUL port of ok-nte's DodgeCounterTrigger.  Executes dodge (double-Shift
tap) and counter (left click) actions with configurable rate limiting and
cooldown windows.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class DodgeCounterTrigger:
    """Converts detected sound events into keyboard / mouse actions.

    Parameters
    ----------
    task : Any
        The parent automation task object (must provide ``send_key`` and
        ``click`` methods).
    dodge_cooldown : float
        Minimum seconds between consecutive dodge actions.  Default 0.6.
    counter_cooldown : float
        Minimum seconds between consecutive counter actions.  Default 0.5.
    dodge_double_tap_interval : float
        Seconds between the two Shift presses that constitute a dodge.
        Default 0.08.
    """

    def __init__(
        self,
        task: Any = None,
        dodge_cooldown: float = 0.6,
        counter_cooldown: float = 0.5,
        dodge_double_tap_interval: float = 0.08,
    ) -> None:
        self.task = task
        self.dodge_cooldown = dodge_cooldown
        self.counter_cooldown = counter_cooldown
        self.dodge_double_tap_interval = dodge_double_tap_interval

        # Rate-limit timestamps
        self._last_dodge: float = 0.0
        self._last_counter: float = 0.0

        self._enabled: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_task(self, task: Any) -> None:
        """Bind (or re-bind) to a task instance."""
        self.task = task

    def enable(self) -> None:
        self._enabled = True
        logger.debug("DodgeCounterTrigger enabled")

    def disable(self) -> None:
        self._enabled = False
        logger.debug("DodgeCounterTrigger disabled")

    # ------------------------------------------------------------------
    # Dodge (double Shift tap)
    # ------------------------------------------------------------------
    def dodge(self) -> bool:
        """Execute a dodge action.  Returns True if executed, False if on cooldown."""
        if not self._enabled:
            return False
        if self.task is None:
            logger.warning("DodgeCounterTrigger has no task bound")
            return False

        now = time.time()
        if now - self._last_dodge < self.dodge_cooldown:
            return False

        self._last_dodge = now
        try:
            self.task.send_key("LSHIFT")
            time.sleep(self.dodge_double_tap_interval)
            self.task.send_key("LSHIFT")
            logger.debug("Dodge executed")
            return True
        except Exception:
            logger.exception("Dodge action failed")
            return False

    # ------------------------------------------------------------------
    # Counter (left click)
    # ------------------------------------------------------------------
    def counter(self) -> bool:
        """Execute a counter-attack (left click)."""
        if not self._enabled:
            return False
        if self.task is None:
            logger.warning("DodgeCounterTrigger has no task bound")
            return False

        now = time.time()
        if now - self._last_counter < self.counter_cooldown:
            return False

        self._last_counter = now
        try:
            self.task.click("left")
            logger.debug("Counter executed")
            return True
        except Exception:
            logger.exception("Counter action failed")
            return False

    # ------------------------------------------------------------------
    # Sound event callbacks (for SoundListener registration)
    # ------------------------------------------------------------------
    def on_dodge_sound(self) -> None:
        """Callback suitable for SoundListener.register_trigger('dodge', ...)."""
        self.dodge()

    def on_counter_sound(self) -> None:
        """Callback suitable for SoundListener.register_trigger('counter', ...)."""
        self.counter()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    @property
    def dodge_available(self) -> bool:
        return self._enabled and (time.time() - self._last_dodge >= self.dodge_cooldown)

    @property
    def counter_available(self) -> bool:
        return self._enabled and (time.time() - self._last_counter >= self.counter_cooldown)
