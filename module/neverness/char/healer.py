"""Healer – generic healer base with team-health-aware priority.

Extends BaseChar with healer-specific do_get_switch_priority logic that
considers party HP levels.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from module.neverness.char.base import BaseChar, Priority, Role, Element

logger = logging.getLogger(__name__)


class Healer(BaseChar):
    """Generic healer character with HP-aware switching logic.

    Subclasses should set ``name``, ``element``, and skill cooldowns.
    """

    name = "Healer"
    role = Role.HEALER
    element = Element.WATER

    skill_key = "E"
    ultimate_key = "Q"
    arc_key = "Z"

    skill_cd = 10.0
    ultimate_cd = 18.0
    arc_cd = 12.0

    skill_animation_duration = 1.5
    ultimate_animation_duration = 2.0
    arc_animation_duration = 1.5

    HEAL_THRESHOLD_PCT: float = 0.70
    EMERGENCY_THRESHOLD_PCT: float = 0.35

    def __init__(self, task: Any = None, pos: int = 0) -> None:
        super().__init__(task=task, pos=pos)
        self._team_hp: list[float] = [1.0, 1.0, 1.0, 1.0]

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------
    def do_perform(self) -> None:
        """Healer rotation: heal when needed, otherwise do off-field support."""
        hp_lowest = min(self._team_hp) if self._team_hp else 1.0

        self._logger.debug("Healer.do_perform() lowest_hp=%.0f%%", hp_lowest * 100)

        if hp_lowest < self.EMERGENCY_THRESHOLD_PCT:
            # Emergency – burst heal with ultimate
            if self.click_ultimate():
                return

        if hp_lowest < self.HEAL_THRESHOLD_PCT:
            # Moderate damage – use skill heal
            if self.click_skill():
                return

        # Buff via arc when nobody needs healing
        if self.click_arc():
            return

        self.continues_normal_attack()

    # ------------------------------------------------------------------
    # Priority – healer stays when team HP is low
    # ------------------------------------------------------------------
    def do_get_switch_priority(self) -> Priority:
        hp_lowest = min(self._team_hp) if self._team_hp else 1.0
        now = time.time()
        skill_ready = (now - self._last_skill) >= self.skill_cd
        ult_ready = (now - self._last_ultimate) >= self.ultimate_cd

        if hp_lowest < self.EMERGENCY_THRESHOLD_PCT:
            if ult_ready:
                return Priority.VERY_LOW  # Must stay for emergency heal
            return Priority.LOW  # Stay and wait for ultimate

        if hp_lowest < self.HEAL_THRESHOLD_PCT and skill_ready:
            return Priority.LOW

        # Team is healthy – switch to DPS
        if hp_lowest > 0.85:
            return Priority.HIGH

        return Priority.NORMAL

    # ------------------------------------------------------------------
    # HP tracking
    # ------------------------------------------------------------------
    def update_team_hp(self, hp_list: list[float]) -> None:
        """Update the known HP values for the party (0.0-1.0)."""
        if len(hp_list) != 4:
            self._logger.warning("update_team_hp expects 4 values, got %d", len(hp_list))
        self._team_hp = hp_list[:4]

    def update_single_hp(self, index: int, hp: float) -> None:
        """Update a single character's HP."""
        if 0 <= index < 4:
            self._team_hp[index] = hp

    def reset_state(self) -> None:
        super().reset_state()
        self._team_hp = [1.0, 1.0, 1.0, 1.0]
