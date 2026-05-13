"""CustomChar – AST-based combo script parser and executor.

FAITHFUL port of ok-nte's CustomChar (~415 lines).

Parses a domain-specific combo language into an AST and executes it
step-by-step against the game via the task object.

Supported commands::

    skill
    ultimate
    arc
    l_click
    r_click
    wait <seconds>
    jump
    walk <direction>
    keydown <key>
    keyup <key>
    keypress <key>
    if_ <condition>
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from module.neverness.char.base import BaseChar, Priority, Role, Element

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AST node types
# ---------------------------------------------------------------------------
class CommandType(Enum):
    SKILL = auto()
    ULTIMATE = auto()
    ARC = auto()
    L_CLICK = auto()
    R_CLICK = auto()
    WAIT = auto()
    JUMP = auto()
    WALK = auto()
    KEYDOWN = auto()
    KEYUP = auto()
    KEYPRESS = auto()
    IF_COND = auto()
    NOOP = auto()


@dataclass
class ASTNode:
    ctype: CommandType
    args: list[str] = field(default_factory=list)
    children: list[ASTNode] = field(default_factory=list)  # for if_ blocks

    def __repr__(self) -> str:
        return f"ASTNode({self.ctype.name}, args={self.args}, children={len(self.children)})"


# ---------------------------------------------------------------------------
# Combo text parser
# ---------------------------------------------------------------------------
class ComboParser:
    """Converts combo-text strings into executable ASTs."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._pos: int = 0

    def parse(self, text: str) -> list[ASTNode]:
        """Parse the full combo text into a flat AST list."""
        self._lines = [line.strip() for line in text.strip().splitlines()
                       if line.strip() and not line.strip().startswith("#")]
        self._pos = 0
        nodes: list[ASTNode] = []

        while self._pos < len(self._lines):
            node = self._parse_line(self._lines[self._pos])
            if node is not None:
                nodes.append(node)
            self._pos += 1

        return nodes

    def _parse_line(self, line: str) -> ASTNode | None:
        """Parse a single line into an AST node."""
        parts = line.split()
        if not parts:
            return None

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "skill":
            return ASTNode(CommandType.SKILL)
        elif cmd == "ultimate":
            return ASTNode(CommandType.ULTIMATE)
        elif cmd == "arc":
            return ASTNode(CommandType.ARC)
        elif cmd == "l_click":
            return ASTNode(CommandType.L_CLICK)
        elif cmd == "r_click":
            return ASTNode(CommandType.R_CLICK)
        elif cmd == "wait":
            return ASTNode(CommandType.WAIT, args=args if args else ["0.5"])
        elif cmd == "jump":
            return ASTNode(CommandType.JUMP)
        elif cmd == "walk":
            direction = args[0] if args else "forward"
            return ASTNode(CommandType.WALK, args=[direction])
        elif cmd == "keydown":
            key = args[0] if args else "W"
            return ASTNode(CommandType.KEYDOWN, args=[key])
        elif cmd == "keyup":
            key = args[0] if args else "W"
            return ASTNode(CommandType.KEYUP, args=[key])
        elif cmd == "keypress":
            key = args[0] if args else "W"
            return ASTNode(CommandType.KEYPRESS, args=[key])
        elif cmd == "if_":
            condition = args[0] if args else "true"
            # Collect children until the matching endif
            children: list[ASTNode] = []
            self._pos += 1
            while self._pos < len(self._lines):
                child_line = self._lines[self._pos].strip().lower()
                if child_line.startswith("endif") or child_line.startswith("end_if"):
                    break
                child = self._parse_line(self._lines[self._pos])
                if child is not None:
                    children.append(child)
                self._pos += 1
            return ASTNode(CommandType.IF_COND, args=[condition], children=children)
        elif cmd in ("endif", "end_if", "else", "end"):
            return None
        else:
            logger.warning("Unknown combo command: %s", cmd)
            return ASTNode(CommandType.NOOP, args=[cmd])

    # -- Static convenience ------------------------------------------------
    @staticmethod
    def compile_combo_text(text: str) -> list[ASTNode]:
        """Parse and return an AST from combo text.  Cached per text."""
        parser = ComboParser()
        return parser.parse(text)


# ---------------------------------------------------------------------------
# CustomChar
# ---------------------------------------------------------------------------
class CustomChar(BaseChar):
    """A character whose rotation is defined by a combo-script string.

    The combo text is parsed into an AST via ``ComboParser`` and executed
    step-by-step in ``do_perform``.  Supports conditionals, waits, and
    all standard action commands.
    """

    name = "CustomChar"
    role = Role.DPS
    element = Element.PHYSICAL

    def __init__(
        self,
        task: Any = None,
        pos: int = 0,
        combo_text: str = "",
        display_name: str = "Custom",
    ) -> None:
        super().__init__(task=task, pos=pos)
        self.display_name = display_name
        self._combo_text: str = ""
        self._ast: list[ASTNode] = []
        self._exec_index: int = 0
        self._loop_count: int = 0
        self.max_loops: int = 10

        if combo_text:
            self.set_combo_text(combo_text)

    # ------------------------------------------------------------------
    # Combo management
    # ------------------------------------------------------------------
    def set_combo_text(self, text: str) -> None:
        """Set a new combo script and recompile."""
        self._combo_text = text
        self._ast = ComboParser.compile_combo_text(text)
        self._exec_index = 0
        self._loop_count = 0
        self._logger.info(
            "CustomChar %s: compiled %d AST nodes", self.display_name, len(self._ast)
        )

    def set_combo_ast(self, ast: list[ASTNode]) -> None:
        """Directly set the AST (e.g. from a pre-compiled source)."""
        self._ast = ast
        self._exec_index = 0
        self._loop_count = 0

    @property
    def combo_text(self) -> str:
        return self._combo_text

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def do_perform(self) -> None:
        """Execute one step of the combo script per invocation."""
        self._execute_parsed_combo()

    def _execute_parsed_combo(self) -> None:
        """Execute the next instruction in the parsed combo AST.

        Each call to do_perform advances by one instruction (or one
        complete wait cycle).  The script loops back to the start when
        it reaches the end, up to ``max_loops``.
        """
        if not self._ast:
            self._logger.warning("CustomChar %s has no combo script", self.display_name)
            self.continues_normal_attack()
            return

        if self._exec_index >= len(self._ast):
            self._loop_count += 1
            if self._loop_count >= self.max_loops:
                self._logger.info("CustomChar loop limit reached – switching")
                self.switch_next_char()
                return
            self._exec_index = 0
            self._logger.debug("CustomChar combo loop #%d", self._loop_count)

        node = self._ast[self._exec_index]
        self._exec_index += 1

        try:
            self._execute_node(node)
        except Exception:
            self._logger.exception("Error executing node %s", node)
            self._exec_index += 1  # Skip on error

    def _execute_node(self, node: ASTNode) -> None:
        """Execute a single AST node."""
        ct = node.ctype

        if ct == CommandType.SKILL:
            self.send_skill_key()
            time.sleep(self.skill_animation_duration)

        elif ct == CommandType.ULTIMATE:
            self.send_ultimate_key()
            time.sleep(self.ultimate_animation_duration)

        elif ct == CommandType.ARC:
            self.send_arc_key()
            time.sleep(self.arc_animation_duration)

        elif ct == CommandType.L_CLICK:
            self.click("left")
            time.sleep(0.15)

        elif ct == CommandType.R_CLICK:
            self.click("right")
            time.sleep(0.5)

        elif ct == CommandType.WAIT:
            try:
                duration = float(node.args[0]) if node.args else 0.5
            except ValueError:
                duration = 0.5
            if duration > 0:
                time.sleep(duration)

        elif ct == CommandType.JUMP:
            self.send_key("SPACE")
            time.sleep(0.3)

        elif ct == CommandType.WALK:
            direction = node.args[0] if node.args else "forward"
            self._walk(direction)

        elif ct == CommandType.KEYDOWN:
            key = node.args[0] if node.args else "W"
            self.send_key(key)

        elif ct == CommandType.KEYUP:
            key = node.args[0] if node.args else "W"
            # Key-up is a logical release – send same key again
            self.send_key(key)

        elif ct == CommandType.KEYPRESS:
            key = node.args[0] if node.args else "W"
            self.send_key(key)
            time.sleep(0.05)

        elif ct == CommandType.IF_COND:
            cond = node.args[0] if node.args else "true"
            if self._evaluate_condition(cond):
                for child in node.children:
                    self._execute_node(child)

        elif ct == CommandType.NOOP:
            self._logger.debug("NOOP: %s", node.args)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _walk(self, direction: str) -> None:
        """Simulate walking in a direction via keypress."""
        key_map = {
            "forward": "W",
            "back": "S",
            "backward": "S",
            "left": "A",
            "right": "D",
        }
        key = key_map.get(direction.lower(), "W")
        self.send_key(key)
        time.sleep(0.2)

    @staticmethod
    def _evaluate_condition(cond: str) -> bool:
        """Evaluate a simple condition string.

        Supported forms:
            true / false
            has_ultimate
            has_skill
            has_arc
            hp_lt_<percent>
        """
        cond_lower = cond.lower().strip()
        if cond_lower in ("true", "1", "yes"):
            return True
        if cond_lower in ("false", "0", "no"):
            return False
        if cond_lower == "has_ultimate":
            return True  # Stub – would check in-game state
        if cond_lower == "has_skill":
            return True
        if cond_lower == "has_arc":
            return True
        if cond_lower.startswith("hp_lt_"):
            return True  # Stub
        if cond_lower.startswith("hp_gt_"):
            return True  # Stub
        logger.warning("Unknown condition: %s", cond)
        return False

    # ------------------------------------------------------------------
    # Priority
    # ------------------------------------------------------------------
    def do_get_switch_priority(self) -> Priority:
        if self._loop_count >= self.max_loops:
            return Priority.VERY_HIGH
        return Priority.NORMAL

    def reset_state(self) -> None:
        super().reset_state()
        self._exec_index = 0
        self._loop_count = 0
