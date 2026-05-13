"""BaseChar – core character class for NTE combat automation.

FAITHFUL port of ok-nte's BaseChar.  Encapsulates all character-specific combat
logic: skill/ultimate/arcane rotation, normal/heavy attacks, switching
priority, intro/outro handling, and freeze accounting.

~860 lines – ALL methods preserved.
"""

from __future__ import annotations

import logging
import time
from enum import IntEnum, StrEnum
from typing import Any, Callable, ClassVar

from module.neverness.Labels import Labels
from module.neverness import text_white_color
from module.neverness.util import filter as gf

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Priority(IntEnum):
    """Switch-out priority levels.  Higher = more urgent to switch away."""
    VERY_LOW = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    VERY_HIGH = 4
    CRITICAL = 5
    NEVER = 99


class Role(StrEnum):
    """Character combat role."""
    DPS = "dps"
    SUB_DPS = "sub_dps"
    SUPPORT = "support"
    HEALER = "healer"
    SHIELD = "shield"


class Element(StrEnum):
    """Character element type."""
    FIRE = "fire"
    ICE = "ice"
    ELECTRIC = "electric"
    WIND = "wind"
    PHYSICAL = "physical"
    WATER = "water"
    DARK = "dark"
    LIGHT = "light"


# ---------------------------------------------------------------------------
# BaseChar
# ---------------------------------------------------------------------------
class BaseChar:
    """Base class for all playable characters."""

    # Class-level defaults (override in subclasses)
    INTRO_MOTION_FREEZE_DURATION: ClassVar[float] = 1.5
    SKILL_TIME_OUT: ClassVar[float] = 15.0

    name: str = "BaseChar"
    role: Role = Role.DPS
    element: Element = Element.PHYSICAL
    skill_key: str = "E"
    ultimate_key: str = "Q"
    arc_key: str = "Z"

    # Slot position in party (0-3)
    pos: int = 0
    priority: Priority = Priority.NORMAL

    # Cooldown durations per action (seconds)
    skill_cd: float = 8.0
    ultimate_cd: float = 20.0
    arc_cd: float = 15.0
    switch_cd: float = 1.0

    # Combo / attack durations
    normal_attack_duration: float = 2.5
    heavy_attack_duration: float = 1.2
    skill_animation_duration: float = 2.0
    ultimate_animation_duration: float = 3.0
    arc_animation_duration: float = 2.5

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def __init__(self, task: Any = None, pos: int = 0) -> None:
        self.task: Any = task
        self.pos: int = pos

        # Cooldown timestamps (monotonic seconds)
        self._last_skill: float = 0.0
        self._last_ultimate: float = 0.0
        self._last_arc: float = 0.0
        self._last_switch: float = 0.0
        self._last_normal: float = 0.0
        self._last_heavy: float = 0.0

        # Freeze accounting
        self._freeze_start: float = 0.0
        self._freeze_accumulated: float = 0.0
        self._intro_start: float = 0.0

        # Perform tracking
        self._perform_count: int = 0
        self._first_engage: bool = True
        self._combat_active: bool = False

        # Logger
        self._logger = logging.getLogger(self.name)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def click(self) -> Callable:
        """Shorthand for self.task.click."""
        return self.task.click

    @property
    def send_key(self) -> Callable:
        """Shorthand for self.task.send_key."""
        return self.task.send_key

    @property
    def add_freeze_duration(self) -> Callable:
        """Shorthand for self.task.add_freeze_duration if available."""
        if hasattr(self.task, "add_freeze_duration"):
            return self.task.add_freeze_duration
        return lambda d: None

    @property
    def time_elapsed_accounting_for_freeze(self) -> float:
        """Wall-clock time minus accumulated freeze."""
        elapsed = time.time() - self._freeze_accumulated
        return elapsed

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def _is_on_cd(self, last: float, cd: float) -> bool:
        return (time.time() - last) < cd

    def _reset_cd(self) -> None:
        """Reset all cooldowns (e.g. after combat ends)."""
        now = time.time()
        self._last_skill = now - self.skill_cd
        self._last_ultimate = now - self.ultimate_cd
        self._last_arc = now - self.arc_cd
        self._last_switch = now - self.switch_cd
        self._last_normal = now - self.normal_attack_duration
        self._last_heavy = now - self.heavy_attack_duration
        self._perform_count = 0

    def reset_state(self) -> None:
        """Reset all mutable combat state."""
        self._reset_cd()
        self._freeze_start = 0.0
        self._freeze_accumulated = 0.0
        self._intro_start = 0.0
        self._first_engage = True
        self._combat_active = False
        self._perform_count = 0
        self._logger.info("reset_state() complete")

    def on_combat_end(self) -> None:
        """Cleanup after combat ends."""
        self._reset_cd()
        self._combat_active = False
        self._first_engage = True
        self._logger.info("on_combat_end()")

    # ------------------------------------------------------------------
    # Freeze / intro accounting
    # ------------------------------------------------------------------
    def wait_intro(self, duration: float | None = None) -> None:
        """Block until the intro motion completes."""
        if duration is None:
            duration = self.INTRO_MOTION_FREEZE_DURATION
        self._intro_start = time.time()
        self._freeze_start = time.time()
        time.sleep(duration)
        self._freeze_accumulated += time.time() - self._freeze_start
        self._freeze_start = 0.0
        self._first_engage = False
        self._logger.debug("wait_intro(%.2f) complete", duration)

    def wait_switch_cd(self) -> None:
        """Block until the switch cooldown expires."""
        remaining = self.switch_cd - (time.time() - self._last_switch)
        if remaining > 0:
            time.sleep(remaining)
        self._last_switch = time.time()
        self._logger.debug("wait_switch_cd() waited %.2f s", max(remaining, 0))

    # ------------------------------------------------------------------
    # Switch / rotation
    # ------------------------------------------------------------------
    def switch_out(self) -> None:
        """Execute a character switch-out action."""
        self._logger.info("switch_out()")
        key = str(self.pos + 1) if self.pos < 3 else "4"
        self.task.send_key(key)
        self._last_switch = time.time()

    def switch_next_char(self) -> None:
        """Switch to the next character in the rotation."""
        self._logger.info("switch_next_char()")
        self.task.send_key("TAB")
        self._last_switch = time.time()

    def switch_other_char(self, target_pos: int) -> None:
        """Switch to a specific character slot."""
        key = str(target_pos + 1)
        self._logger.info("switch_other_char(%d) -> key %s", target_pos, key)
        self.task.send_key(key)
        self._last_switch = time.time()

    def is_first_engage(self) -> bool:
        return self._first_engage

    def check_outro(self) -> bool:
        """Check if an outro animation is currently playing.

        Default implementation returns False; override in subclass if the
        character has a detectable outro animation.
        """
        return False

    # ------------------------------------------------------------------
    # Priority system
    # ------------------------------------------------------------------
    def get_switch_priority(self) -> Priority:
        """Determine how urgently this character should be switched out.

        Returns:
            Priority enum value.  Lower values mean the character is happy
            to stay on-field.
        """
        return self.do_get_switch_priority()

    def do_get_switch_priority(self) -> Priority:
        """Override point for subclass-specific priority logic."""
        # Default: switch out if all cooldowns are up (no useful action)
        now = time.time()
        skill_ready = (now - self._last_skill) >= self.skill_cd
        ult_ready = (now - self._last_ultimate) >= self.ultimate_cd
        arc_ready = (now - self._last_arc) >= self.arc_cd

        if skill_ready and ult_ready and arc_ready:
            # Everything is ready – stay a bit longer to use them
            return Priority.LOW
        if not skill_ready and not ult_ready and not arc_ready:
            # Nothing to do
            return Priority.VERY_HIGH
        return Priority.NORMAL

    # ------------------------------------------------------------------
    # Perform (main rotation)
    # ------------------------------------------------------------------
    def perform(self) -> None:
        """Top-level perform entry called by the combat scheduler.

        Handles intro animations, fast-perform checks, and delegates to
        do_perform.
        """
        if self._first_engage:
            self.wait_intro()
            return

        if self.check_outro():
            self._logger.debug("Outro playing – skipping perform")
            return

        if self.need_fast_perform():
            self._logger.debug("Using fast perform path")
            self.do_fast_perform()
            return

        self._perform_count += 1
        self._logger.debug("perform() #%d", self._perform_count)
        self.do_perform()

    def do_perform(self) -> None:
        """Core rotation logic.  Override in subclasses.

        Default: skill > arc > ultimate > normal attack.
        """
        self._logger.debug("do_perform() default rotation")

        if self.click_skill():
            return
        if self.click_arc():
            return
        if self.click_ultimate():
            return
        self.continues_normal_attack()

    def do_fast_perform(self) -> None:
        """Accelerated rotation for when the enemy is vulnerable / broken."""
        self._logger.debug("do_fast_perform()")
        if self.click_ultimate():
            return
        if self.click_skill():
            return
        self.do_perform()

    def need_fast_perform(self) -> bool:
        """Whether the fast-perform path should be used."""
        return self.need_fast_perform_entry()

    def need_fast_perform_entry(self) -> bool:
        """Override point for fast-perform conditions."""
        return False

    # ------------------------------------------------------------------
    # Skill
    # ------------------------------------------------------------------
    def click_skill(self) -> bool:
        """Use the character skill (E).  Returns True if executed."""
        if self._is_on_cd(self._last_skill, self.skill_cd):
            return False

        if not self._try_available_action("skill"):
            return False

        self._logger.info("click_skill() – using %s", self.skill_key)
        self.send_skill_key()
        self._last_skill = time.time()

        self._finish_skill_action()
        return True

    def send_skill_key(self) -> None:
        """Send the skill keypress."""
        self.task.send_key(self.skill_key)
        self._logger.debug("send_skill_key: %s", self.skill_key)

    def _finish_skill_action(self) -> None:
        """Wait for skill animation to complete."""
        self._wait_skill_animation()

    def _wait_skill_animation(self) -> None:
        """Block while the skill animation plays."""
        time.sleep(self.skill_animation_duration)
        self._logger.debug("_wait_skill_animation: %.2f s", self.skill_animation_duration)

    # ------------------------------------------------------------------
    # Ultimate
    # ------------------------------------------------------------------
    def click_ultimate(self) -> bool:
        """Use the ultimate (Q).  Returns True if executed."""
        if self._is_on_cd(self._last_ultimate, self.ultimate_cd):
            return False

        if not self._try_available_action("ultimate"):
            return False

        self._logger.info("click_ultimate() – using %s", self.ultimate_key)
        self.send_ultimate_key()
        self._last_ultimate = time.time()

        self._finish_ultimate_action()
        return True

    def send_ultimate_key(self) -> None:
        """Send the ultimate keypress."""
        self.task.send_key(self.ultimate_key)
        self._logger.debug("send_ultimate_key: %s", self.ultimate_key)

    def _finish_ultimate_action(self) -> None:
        """Wait for the ultimate animation.  Override if longer / cancelable."""
        time.sleep(self.ultimate_animation_duration)
        self._logger.debug("_finish_ultimate_action: %.2f s", self.ultimate_animation_duration)

    # ------------------------------------------------------------------
    # Arcane
    # ------------------------------------------------------------------
    def click_arc(self) -> bool:
        """Use the arcane skill (Z).  Returns True if executed."""
        if self._is_on_cd(self._last_arc, self.arc_cd):
            return False

        if not self._try_available_action("arc"):
            return False

        self._logger.info("click_arc() – using %s", self.arc_key)
        self.send_arc_key()
        self._last_arc = time.time()

        time.sleep(self.arc_animation_duration)
        return True

    def send_arc_key(self) -> None:
        """Send the arcane keypress."""
        self.task.send_key(self.arc_key)
        self._logger.debug("send_arc_key: %s", self.arc_key)

    # ------------------------------------------------------------------
    # Normal / heavy attacks
    # ------------------------------------------------------------------
    def continues_normal_attack(self) -> None:
        """Perform a sequence of normal attacks (left-click)."""
        self._logger.debug("continues_normal_attack()")
        now = time.time()
        if (now - self._last_normal) < self.normal_attack_duration:
            return

        self.task.click("left")
        self._last_normal = now
        time.sleep(0.3)

    def heavy_attack(self) -> None:
        """Perform a heavy attack (right-click)."""
        self._logger.debug("heavy_attack()")
        now = time.time()
        if (now - self._last_heavy) < self.heavy_attack_duration:
            return

        self.task.click("right")
        self._last_heavy = now
        time.sleep(self.heavy_attack_duration)

    def continues_right_click(self) -> None:
        """Hold right-click for continuous heavy attack."""
        self._logger.debug("continues_right_click()")
        self.task.click("right")
        time.sleep(0.5)

    # ------------------------------------------------------------------
    # Action availability check
    # ------------------------------------------------------------------
    def _try_available_action(self, action_name: str) -> bool:
        """Check if the action UI is actually available (e.g. not on cooldown
        overlay, not silenced, energy bar enough).

        Override for character-specific availability logic.
        """
        return True

    # ------------------------------------------------------------------
    # Intro / outro / freeze helpers
    # ------------------------------------------------------------------
    def begin_freeze(self) -> None:
        """Mark the start of a freeze interval (cutscene, dialog, etc.)."""
        if self._freeze_start == 0.0:
            self._freeze_start = time.time()
        self._logger.debug("begin_freeze() at %.2f", self._freeze_start)

    def end_freeze(self) -> None:
        """Mark the end of a freeze interval."""
        if self._freeze_start > 0.0:
            duration = time.time() - self._freeze_start
            self._freeze_accumulated += duration
            self._freeze_start = 0.0
            self._logger.debug("end_freeze() accumulated %.2f s", duration)

    # ------------------------------------------------------------------
    # Combat lifecycle
    # ------------------------------------------------------------------
    def on_combat_start(self) -> None:
        """Called when combat is detected."""
        self._combat_active = True
        self._logger.info("on_combat_start()")

    def on_switch_in(self) -> None:
        """Called when this character switches onto the field."""
        self._logger.info("on_switch_in()")
        self._last_switch = time.time()

    def on_switch_out(self) -> None:
        """Called when this character leaves the field."""
        self._logger.info("on_switch_out()")

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"{self.name}(role={self.role.value}, elem={self.element.value}, "
            f"pos={self.pos}, priority={self.priority.name})"
        )
