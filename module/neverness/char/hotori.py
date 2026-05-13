"""Hotori – shield / tank character.

Hotori provides damage mitigation and crowd control via shields.  Her
rotation prioritises shield uptime and taunt windows.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from module.neverness.char.base import BaseChar, Priority, Role, Element

logger = logging.getLogger(__name__)


class Hotori(BaseChar):
    """Hotori – shield tank with taunt capability."""

    name = "Hotori"
    role = Role.SHIELD
    element = Element.DARK

    skill_key = "E"
    ultimate_key = "Q"
    arc_key = "Z"

    skill_cd = 12.0
    ultimate_cd = 20.0
    arc_cd = 15.0

    skill_animation_duration = 1.5
    ultimate_animation_duration = 2.5
    arc_animation_duration = 1.8
    normal_attack_duration = 2.0

    SHIELD_DURATION: float = 12.0

    def __init__(self, task: Any = None, pos: int = 0) -> None:
        super().__init__(task=task, pos=pos)
        self._shield_active: bool = False
        self._shield_expires: float = 0.0
        self._taunt_active: bool = False

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------
    def do_perform(self) -> None:
        """Hotori rotation: maintain shield > taunt > normal attacks."""
        self._logger.debug(
            "Hotori.do_perform() shield=%s taunt=%s",
            self._shield_active, self._taunt_active,
        )

        # Shield is priority when not up
        if not self._shield_active or time.time() > self._shield_expires:
            if self.click_skill():
                self._shield_active = True
                self._shield_expires = time.time() + self.SHIELD_DURATION
                return

        # Taunt via arc
        if not self._taunt_active:
            if self.click_arc():
                self._taunt_active = True
                return

        # Ultimate when available
        if self.click_ultimate():
            self._shield_active = True
            self._shield_expires = time.time() + self.SHIELD_DURATION
            return

        # Fill with normals (generates aggro)
        self.continues_normal_attack()

    # ------------------------------------------------------------------
    # Priority – Hotori stays as long as possible
    # ------------------------------------------------------------------
    def do_get_switch_priority(self) -> Priority:
        now = time.time()
        shield_up = self._shield_active and now < self._shield_expires

        if shield_up:
            # Shield is up – can stay a while
            return Priority.LOW
        if (now - self._last_skill) >= self.skill_cd:
            # Need to reapply shield
            return Priority.VERY_LOW
        # Shield on cooldown, no taunt – consider switching
        return Priority.NORMAL

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_switch_out(self) -> None:
        super().on_switch_out()
        # Shield persists when off-field in some games – we track it
        self._logger.info("Hotori switched out – shield remains %.1f s",
                          max(0, self._shield_expires - time.time()))

    def on_combat_end(self) -> None:
        super().on_combat_end()
        self._shield_active = False
        self._shield_expires = 0.0
        self._taunt_active = False

    def reset_state(self) -> None:
        super().reset_state()
        self._shield_active = False
        self._shield_expires = 0.0
        self._taunt_active = False
