"""
AutoCombatTask - Auto combat trigger with character switching.

Inherits BaseCombatTask for combat logic + BaseNTETask for game interaction.
Runs at trigger_interval when the player is in combat.
"""

import time

from module.util.logger import logger

from module.neverness.Labels import Labels
from module.neverness.task.base import BaseNTETask
from module.neverness.combat.base import BaseCombatTask, CharDeadException, NotInCombatException
from module.neverness.char.factory import get_char_by_name, get_char_by_pos


class AutoCombatTask(BaseCombatTask, BaseNTETask):
    """Background trigger task for automated combat with character switching."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "auto_combat"
        self.trigger_interval = 0.1
        self.default_config = {"_enabled": True}
        self.config.setdefault("auto_target", True)
        self.op_index = 0
        self.last_is_click = False

    # ------------------------------------------------------------------
    # Trigger entry point
    # ------------------------------------------------------------------

    def run(self):
        """Main combat loop: runs each trigger interval while in combat."""
        if not self._is_combat_trigger_ready():
            return

        ret = False
        combat_start = time.time()

        while self.in_combat():
            try:
                if not ret:
                    ret = True
                    self._on_combat_enter()
                self._perform_current_char()
            except CharDeadException:
                self.log_error("characters dead", notify=True)
                break
            except NotInCombatException as e:
                logger.info(f"out of combat: {int(time.time() - combat_start)}s {e}")
                break

        if ret:
            self._on_combat_exit()

    def _is_combat_trigger_ready(self) -> bool:
        """Guard: only run if in team and not already in another combat loop."""
        if not self.is_in_team():
            return False
        return True

    def _on_combat_enter(self):
        """Called when combat begins."""
        self.load_chars()
        self._switch_to_combat_start_char()

    def _on_combat_exit(self):
        """Called when combat ends."""
        self.combat_end()

    def _perform_current_char(self):
        """Execute the current character's combat rotation."""
        char = self.get_current_char()
        if char:
            char.perform()

    def _switch_to_combat_start_char(self):
        """Switch to the designated combat-start character."""
        start_chars = [c for c in self.chars if c and getattr(c, 'start_combat', False)]
        if not start_chars:
            return
        import random
        switch_to = random.choice(start_chars)
        current = self.get_current_char(raise_exception=False)
        if current == switch_to:
            return
        self._switch_to_char(switch_to, current_char=current, log_prefix="switch to start char")

    # ------------------------------------------------------------------
    # Team scan (for UI reporting)
    # ------------------------------------------------------------------

    def scan_team(self):
        """Scan the current team and report character identities."""
        self.log_info("scanning current team")
        in_team, _, count = self.in_team()
        if not in_team or count == 0:
            self.log_info("team does not exist, scan complete")
            return []
        if count < 2:
            self.log_info("team has fewer than 2 members, scan complete")
            return []

        from module.neverness.char.custom.manager import CustomCharManager
        manager = CustomCharManager()
        results = []
        frame = self._last_screenshot

        for i in range(count):
            from module.neverness.char.factory import get_char_feature_by_pos
            feature_mat, w, h = get_char_feature_by_pos(self, i, frame=frame)
            if feature_mat is not None and feature_mat.size > 0:
                is_match, match_name, confidence = manager.match_feature(self, feature_mat)
                name = match_name if is_match else None
                results.append({
                    "index": i, "mat": feature_mat, "width": w, "height": h, "match": name,
                })
                self.log_debug(f"char_{i + 1}: {name}, conf={confidence:.2f}")
        self.log_info("scan complete")
        return results
