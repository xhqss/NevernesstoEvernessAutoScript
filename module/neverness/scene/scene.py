"""NTEScene – simple state tracker for the game world."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Any

logger = logging.getLogger(__name__)


class NTEScene:
    """Tracks discrete state flags about the current game scene.

    Attributes:
        _is_in_team: Whether the player is currently in a team (co-op).
        _in_combat: Whether combat is active.
        cd_refreshed: Timestamp of last cooldown refresh.
        _scene_frame: Frame counter for the current scene.
    """

    def __init__(self) -> None:
        self._is_in_team: bool = False
        self._in_combat: bool = False
        self.cd_refreshed: float = 0.0
        self._scene_frame: int = 0
        self._lock = threading.Lock()
        self._combat_observers: list[Callable[[bool], None]] = []

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Reset all state to defaults."""
        with self._lock:
            self._is_in_team = False
            self._in_combat = False
            self.cd_refreshed = 0.0
            self._scene_frame = 0

    # ------------------------------------------------------------------
    # Combat state
    # ------------------------------------------------------------------
    def in_combat(self) -> bool:
        return self._in_combat

    def set_in_combat(self) -> None:
        changed = False
        with self._lock:
            if not self._in_combat:
                self._in_combat = True
                changed = True
        if changed:
            for cb in self._combat_observers:
                try:
                    cb(True)
                except Exception:
                    logger.exception("Combat observer failed")

    def set_not_in_combat(self) -> None:
        changed = False
        with self._lock:
            if self._in_combat:
                self._in_combat = False
                changed = True
        if changed:
            for cb in self._combat_observers:
                try:
                    cb(False)
                except Exception:
                    logger.exception("Combat observer failed")

    def add_combat_observer(self, callback: Callable[[bool], None]) -> None:
        """Register a callback invoked when combat state changes."""
        self._combat_observers.append(callback)

    # ------------------------------------------------------------------
    # Team state
    # ------------------------------------------------------------------
    def is_in_team(self, fun: Callable[[], bool]) -> bool:
        """Run a detection function to determine if we are in a team."""
        with self._lock:
            self._is_in_team = fun()
        return self._is_in_team

    def get_is_in_team_record(self) -> bool:
        return self._is_in_team

    # ------------------------------------------------------------------
    # Frame / scene tracking
    # ------------------------------------------------------------------
    def scene_frame(self, frame: int) -> None:
        """Update the current scene frame index."""
        self._scene_frame = frame

    @property
    def current_frame(self) -> int:
        return self._scene_frame

    # ------------------------------------------------------------------
    # OCR warm-up
    # ------------------------------------------------------------------
    def ocr_warm_up(self, task: Any) -> None:
        """Prime any OCR caches by reading a dummy region.

        Args:
            task: The automation task instance (provides screenshot access).
        """
        try:
            _ = task.screenshot()
            logger.info("NTEScene OCR warm-up triggered")
        except Exception:
            logger.debug("OCR warm-up skipped – no screenshot available")
