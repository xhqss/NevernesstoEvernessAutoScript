"""Mint – support / healer character.

Mint focuses on keeping the team alive and providing buffs.  Her rotation
prioritises arc (buff) then skill (heal), and she switches out quickly once
her contributions are done.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from module.neverness.char.base import BaseChar, Priority, Role, Element

logger = logging.getLogger(__name__)


class Mint(BaseChar):
    """Mint – support healer with team buffs."""

    name = "Mint"
    role = Role.SUPPORT
    element = Element.ICE

    skill_key = "E"
    ultimate_key = "Q"
    arc_key = "Z"

    skill_cd = 10.0
    ultimate_cd = 20.0
    arc_cd = 12.0

    skill_animation_duration = 1.2
    ultimate_animation_duration = 2.0
    arc_animation_duration = 1.5
    normal_attack_duration = 2.0

    def __init__(self, task: Any = None, pos: int = 0) -> None:
        super().__init__(task=task, pos=pos)
        self._buffs_applied: bool = False
        self._healed: bool = False

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------
    def do_perform(self) -> None:
        """Mint rotation: arc (buff) > skill (heal) > switch out."""
        self._logger.debug(
            "Mint.do_perform() buffs=%s healed=%s",
            self._buffs_applied, self._healed,
        )

        if self.click_arc():
            self._buffs_applied = True
            return

        if self.click_skill():
            self._healed = True
            return

        if self.click_ultimate():
            return

        # Mint doesn't bother with normals – switch priority handles that
        self.continues_normal_attack()

    # ------------------------------------------------------------------
    # Priority
    # ------------------------------------------------------------------
    def do_get_switch_priority(self) -> Priority:
        """Mint switches out once arc and skill are both used."""
        now = time.time()
        arc_ready = (now - self._last_arc) >= self.arc_cd
        skill_ready = (now - self._last_skill) >= self.skill_cd

        if self._buffs_applied and self._healed:
            # Job done – switch to DPS
            return Priority.HIGH
        if arc_ready or skill_ready:
            # Still has useful actions
            return Priority.LOW
        return Priority.NORMAL

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_switch_in(self) -> None:
        super().on_switch_in()
        self._logger.info("Mint switched in")

    def on_switch_out(self) -> None:
        super().on_switch_out()
        # Reset per-field flags
        self._buffs_applied = False
        self._healed = False

    def reset_state(self) -> None:
        super().reset_state()
        self._buffs_applied = False
        self._healed = False
