"""BuiltinComboRegistry – manages built-in combo text storage.

Builtin combos are keyed by a human-readable label and stored with the
prefix ``[内置代码] `` (Chinese: "built-in code").

References use the ``builtin:`` URI scheme.
"""

from __future__ import annotations

import logging
from typing import Iterator

logger = logging.getLogger(__name__)


class BuiltinComboRegistry:
    """Registry mapping built-in combo labels to their script text.

    References are encoded as ``builtin:<label>`` and stored in a dict
    that can be iterated and queried.
    """

    REF_PREFIX: str = "builtin:"
    LABEL_PREFIX: str = "[内置代码] "

    def __init__(self) -> None:
        self._data: dict[str, str] = {}  # label → combo_text

    # ------------------------------------------------------------------
    # Reference helpers
    # ------------------------------------------------------------------
    @classmethod
    def make_ref(cls, label: str) -> str:
        """Make a reference string from a label.

        >>> BuiltinComboRegistry.make_ref("basic_rotation")
        'builtin:basic_rotation'
        """
        return f"{cls.REF_PREFIX}{label}"

    @classmethod
    def ref_to_key(cls, ref: str) -> str:
        """Extract the label from a reference string.

        >>> BuiltinComboRegistry.ref_to_key("builtin:basic_rotation")
        'basic_rotation'
        """
        if ref.startswith(cls.REF_PREFIX):
            return ref[len(cls.REF_PREFIX):]
        return ref

    @classmethod
    def to_ref(cls, label: str) -> str:
        """Alias for make_ref."""
        return cls.make_ref(label)

    @classmethod
    def to_label(cls, ref_or_label: str) -> str:
        """Convert a reference (or raw label) to a display label."""
        label = cls.ref_to_key(ref_or_label)
        return f"{cls.LABEL_PREFIX}{label}"

    @classmethod
    def is_ref(cls, value: str) -> bool:
        """Check if a string is a builtin reference."""
        return value.startswith(cls.REF_PREFIX)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def add(self, label: str, combo_text: str) -> None:
        """Register a built-in combo."""
        self._data[label] = combo_text
        logger.debug("BuiltinComboRegistry: added %s (%d chars)", label, len(combo_text))

    def get(self, label: str) -> str | None:
        """Retrieve a built-in combo by label."""
        return self._data.get(label)

    def remove(self, label: str) -> bool:
        """Remove a built-in combo.  Returns True if it existed."""
        existed = label in self._data
        if existed:
            del self._data[label]
            logger.debug("BuiltinComboRegistry: removed %s", label)
        return existed

    def clear(self) -> None:
        """Remove all entries."""
        self._data.clear()
        logger.debug("BuiltinComboRegistry cleared")

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------
    def iter_builtin_pairs(self) -> Iterator[tuple[str, str]]:
        """Yield (label, combo_text) pairs."""
        yield from self._data.items()

    def labels(self) -> list[str]:
        """Return all registered labels."""
        return list(self._data.keys())

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, label: str) -> bool:
        return label in self._data

    def __repr__(self) -> str:
        return f"BuiltinComboRegistry({len(self._data)} entries)"


# ------------------------------------------------------------------
# Seed the registry with some sensible defaults
# ------------------------------------------------------------------
_DEFAULT_COMBOS = {
    "basic_dps": (
        "skill\n"
        "wait 0.5\n"
        "ultimate\n"
        "wait 0.5\n"
        "arc\n"
        "wait 0.2\n"
        "l_click\n"
        "wait 0.2\n"
        "l_click"
    ),
    "fast_dps": (
        "ultimate\n"
        "wait 0.3\n"
        "skill\n"
        "wait 0.3\n"
        "arc"
    ),
    "heal_rotation": (
        "arc\n"
        "wait 0.5\n"
        "skill\n"
        "wait 1.0"
    ),
    "shield_bot": (
        "skill\n"
        "wait 0.5\n"
        "r_click\n"
        "wait 1.0\n"
        "r_click"
    ),
}

_builtin_registry = BuiltinComboRegistry()
for _label, _text in _DEFAULT_COMBOS.items():
    _builtin_registry.add(_label, _text)


def get_builtin_registry() -> BuiltinComboRegistry:
    """Get the module-level built-in combo registry singleton."""
    return _builtin_registry
