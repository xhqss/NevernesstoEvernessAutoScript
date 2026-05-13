"""Jiuyuan – wind DPS with crowd-control focus.

Jiuyuan groups enemies and deals area-of-effect damage.  His rotation
emphasises grouping (arcane) followed by AoE burst (skill / ultimate).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from module.neverness.char.base import BaseChar, Priority, Role, Element

logger = logging.getLogger(__name__)


class Jiuyuan(BaseChar):
    """Jiuyuan – wind AoE DPS with crowd control."""

    name = "Jiuyuan"
    role = Role.DPS
    element = Element.WIND

    skill_key = "E"
    ultimate_key = "Q"
    arc_key = "Z"

    skill_cd = 8.0
    ultimate_cd = 16.0
    arc_cd = 10.0

    skill_animation_duration = 2.0
    ultimate_animation_duration = 3.0
    arc_animation_duration = 2.0
    normal_attack_duration = 2.5

    def __init__(self, task: Any = None, pos: int = 0) -> None:
        super().__init__(task=task, pos=pos)
        self._enemies_grouped: bool = False
        self._group_expires: float = 0.0

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------
    def do_perform(self) -> None:
        """Jiuyuan rotation: arc (group) > skill (AoE) > ultimate > normals."""
        self._logger.debug(
            "Jiuyuan.do_perform() grouped=%s", self._enemies_grouped,
        )

        # First, group enemies with arc
        if not self._enemies_grouped:
            if self.click_arc():
                self._enemies_grouped = True
                self._group_expires = time.time() + 4.0
                return

        # After grouping, use AoE skills
        if self._enemies_grouped:
            if self.click_skill():
                return
            if self.click_ultimate():
                return

        # Refresh group if expired
        if self._enemies_grouped and time.time() > self._group_expires:
            self._enemies_grouped = False

        self.continues_normal_attack()

    def do_fast_perform(self) -> None:
        """Fast: ultimate > skill > arc (burn window)."""
        if self._enemies_grouped:
            if self.click_ultimate():
                return
            if self.click_skill():
                return
        if self.click_arc():
            self._enemies_grouped = True
            self._group_expires = time.time() + 4.0
            return
        self.continues_normal_attack()

    def need_fast_perform_entry(self) -> bool:
        return self._enemies_grouped

    # ------------------------------------------------------------------
    # Priority
    # ------------------------------------------------------------------
    def do_get_switch_priority(self) -> Priority:
        now = time.time()
        ult_ready = (now - self._last_ultimate) >= self.ultimate_cd
        skill_ready = (now - self._last_skill) >= self.skill_cd

        if ult_ready and self._enemies_grouped:
            return Priority.VERY_LOW  # Stay for grouped burst
        if skill_ready and self._enemies_grouped:
            return Priority.LOW
        if not ult_ready and not skill_ready:
            return Priority.HIGH
        return Priority.NORMAL

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_combat_end(self) -> None:
        super().on_combat_end()
        self._enemies_grouped = False
        self._group_expires = 0.0

    def reset_state(self) -> None:
        super().reset_state()
        self._enemies_grouped = False
        self._group_expires = 0.0
