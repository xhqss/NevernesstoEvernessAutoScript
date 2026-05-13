"""Nanally – fire sub-DPS with off-field damage.

Nanally excels at deploying persistent off-field effects then switching
to the main DPS.  Her rotation emphasises getting arc + skill out quickly.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from module.neverness.char.base import BaseChar, Priority, Role, Element

logger = logging.getLogger(__name__)


class Nanally(BaseChar):
    """Nanally – fire sub-DPS with off-field presence."""

    name = "Nanally"
    role = Role.SUB_DPS
    element = Element.FIRE

    skill_key = "E"
    ultimate_key = "Q"
    arc_key = "Z"

    skill_cd = 10.0
    ultimate_cd = 18.0
    arc_cd = 8.0

    skill_animation_duration = 1.8
    ultimate_animation_duration = 2.8
    arc_animation_duration = 1.2
    normal_attack_duration = 2.0

    def __init__(self, task: Any = None, pos: int = 0) -> None:
        super().__init__(task=task, pos=pos)
        self._off_field_active: bool = False
        self._off_field_end: float = 0.0

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------
    def do_perform(self) -> None:
        """Nanally rotation: arc > skill > ultimate, then switch out ASAP.

        As a sub-DPS, Nanally wants to deploy her off-field effects and
        leave the field to the main DPS.
        """
        self._logger.debug(
            "Nanally.do_perform() off_field=%s", self._off_field_active,
        )

        # Arc starts the off-field effect
        if self.click_arc():
            self._off_field_active = True
            self._off_field_end = time.time() + self.arc_cd
            return

        # Skill extends / empowers the off-field effect
        if self.click_skill():
            self._off_field_active = True
            self._off_field_end = time.time() + self.skill_cd
            return

        # Ultimate as burst finisher
        if self.click_ultimate():
            self._off_field_end = time.time() + self.ultimate_cd
            return

        # Once everything is deployed, normal attacks are low priority
        self.continues_normal_attack()

    # ------------------------------------------------------------------
    # Priority – Nanally wants to leave quickly
    # ------------------------------------------------------------------
    def do_get_switch_priority(self) -> Priority:
        now = time.time()

        # Off-field effect is active – no reason to stay
        if self._off_field_active and now < self._off_field_end:
            return Priority.HIGH

        arc_ready = (now - self._last_arc) >= self.arc_cd
        skill_ready = (now - self._last_skill) >= self.skill_cd

        if arc_ready:
            return Priority.LOW  # Need to deploy arc
        if skill_ready:
            return Priority.NORMAL
        # Nothing useful to do
        return Priority.HIGH

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_switch_out(self) -> None:
        super().on_switch_out()
        self._logger.info("Nanally switched out – off_field=%s", self._off_field_active)

    def reset_state(self) -> None:
        super().reset_state()
        self._off_field_active = False
        self._off_field_end = 0.0

    def on_combat_end(self) -> None:
        super().on_combat_end()
        self._off_field_active = False
        self._off_field_end = 0.0
