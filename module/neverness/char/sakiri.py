"""Sakiri – electric DPS with high burst potential.

Sakiri builds stacks through normal attacks and spends them on a
powerful charged skill.  Her rotation weaves normals between skill uses.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from module.neverness.char.base import BaseChar, Priority, Role, Element

logger = logging.getLogger(__name__)


class Sakiri(BaseChar):
    """Sakiri – electric burst DPS."""

    name = "Sakiri"
    role = Role.DPS
    element = Element.ELECTRIC

    skill_key = "E"
    ultimate_key = "Q"
    arc_key = "Z"

    skill_cd = 5.0
    ultimate_cd = 15.0
    arc_cd = 10.0

    skill_animation_duration = 1.0
    ultimate_animation_duration = 2.2
    arc_animation_duration = 1.5
    normal_attack_duration = 1.8

    MAX_STACKS: int = 5

    def __init__(self, task: Any = None, pos: int = 0) -> None:
        super().__init__(task=task, pos=pos)
        self._stacks: int = 0
        self._normal_hits: int = 0

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------
    def do_perform(self) -> None:
        """Sakiri rotation: build stacks with normals, spend with skill.

        At max stacks the skill does bonus damage, so we prioritise
        reaching max stacks before using the skill.
        """
        self._logger.debug("Sakiri.do_perform() stacks=%d/%d", self._stacks, self.MAX_STACKS)

        # Use ultimate whenever available
        if self.click_ultimate():
            self._stacks = self.MAX_STACKS  # Ultimate grants full stacks
            return

        # Spend stacks if at max
        if self._stacks >= self.MAX_STACKS:
            if self.click_skill():
                self._stacks = 0
                return

        # Otherwise build stacks via normals
        if self.click_arc():
            self._stacks = min(self._stacks + 2, self.MAX_STACKS)
            return

        # Normal attacks build 1 stack per hit
        self.continues_normal_attack()
        self._normal_hits += 1
        if self._normal_hits >= 3:
            self._stacks = min(self._stacks + 1, self.MAX_STACKS)
            self._normal_hits = 0

    def do_fast_perform(self) -> None:
        """Fast: ultimate > skill > arc."""
        if self.click_ultimate():
            self._stacks = self.MAX_STACKS
            return
        if self.click_skill():
            self._stacks = 0
            return
        if self.click_arc():
            self._stacks = min(self._stacks + 2, self.MAX_STACKS)
            return
        self.continues_normal_attack()

    def need_fast_perform_entry(self) -> bool:
        return self._stacks >= self.MAX_STACKS

    # ------------------------------------------------------------------
    # Priority
    # ------------------------------------------------------------------
    def do_get_switch_priority(self) -> Priority:
        now = time.time()
        skill_ready = (now - self._last_skill) >= self.skill_cd
        ult_ready = (now - self._last_ultimate) >= self.ultimate_cd

        if ult_ready:
            return Priority.VERY_LOW  # Stay for burst
        if skill_ready and self._stacks >= self.MAX_STACKS:
            return Priority.LOW
        if not skill_ready and not ult_ready and self._stacks < self.MAX_STACKS // 2:
            return Priority.HIGH
        return Priority.NORMAL

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_switch_in(self) -> None:
        super().on_switch_in()
        self._logger.info("Sakiri switched in – stacks=%d", self._stacks)

    def on_combat_end(self) -> None:
        super().on_combat_end()
        self._stacks = 0
        self._normal_hits = 0

    def reset_state(self) -> None:
        super().reset_state()
        self._stacks = 0
        self._normal_hits = 0
