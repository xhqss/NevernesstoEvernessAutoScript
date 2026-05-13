"""Zero – mechanic DPS character.

Zero excels at rapid skill cycling and fast-perform windows against
broken enemies.  His priority logic keeps him on-field when his skill
is ready.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from module.neverness.char.base import BaseChar, Priority, Role, Element

logger = logging.getLogger(__name__)


class Zero(BaseChar):
    """Zero – melee DPS with fast skill rotation."""

    name = "Zero"
    role = Role.DPS
    element = Element.PHYSICAL

    skill_key = "E"
    ultimate_key = "Q"
    arc_key = "Z"

    skill_cd = 6.0
    ultimate_cd = 18.0
    arc_cd = 12.0

    skill_animation_duration = 1.5
    ultimate_animation_duration = 2.5
    arc_animation_duration = 1.8
    normal_attack_duration = 2.0

    def __init__(self, task: Any = None, pos: int = 0) -> None:
        super().__init__(task=task, pos=pos)
        self._combo_counter: int = 0
        self._last_fast_window: float = 0.0

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------
    def do_perform(self) -> None:
        """Zero rotation: skill > arc > skill > normal."""
        self._logger.debug("Zero.do_perform() combo=%d", self._combo_counter)

        if self.click_skill():
            self._combo_counter += 1
            return

        if self.click_arc():
            self._combo_counter = 0
            return

        if self.click_ultimate():
            self._combo_counter = 0
            return

        self.continues_normal_attack()

    def do_fast_perform(self) -> None:
        """Fast perform: ultimate > skill > arc."""
        self._logger.debug("Zero.do_fast_perform()")

        if self.click_ultimate():
            return
        if self.click_skill():
            self._combo_counter += 1
            return
        if self.click_arc():
            return
        self.continues_normal_attack()

    def need_fast_perform_entry(self) -> bool:
        """Zero fast-performs when combo counter is high (enemy staggered)."""
        return self._combo_counter >= 4

    # ------------------------------------------------------------------
    # Priority
    # ------------------------------------------------------------------
    def do_get_switch_priority(self) -> Priority:
        now = time.time()
        skill_ready = (now - self._last_skill) >= self.skill_cd
        ult_ready = (now - self._last_ultimate) >= self.ultimate_cd

        if skill_ready and ult_ready:
            return Priority.VERY_LOW  # Stay on field
        if skill_ready:
            return Priority.LOW
        if not skill_ready and not ult_ready:
            return Priority.HIGH
        return Priority.NORMAL

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_switch_in(self) -> None:
        super().on_switch_in()
        self._combo_counter = 0
        self._logger.info("Zero switched in – combo reset")

    def on_combat_end(self) -> None:
        super().on_combat_end()
        self._combo_counter = 0
