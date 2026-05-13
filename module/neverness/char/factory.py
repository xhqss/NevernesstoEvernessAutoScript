"""CharFactory – creates character instances by name or position.

Maintains a character registry dict mapping keys to builder functions.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, ClassVar

from module.neverness.char.base import BaseChar

logger = logging.getLogger(__name__)


class CharFactory:
    """Factory that creates and caches character instances.

    All character classes are registered via ``char_dict``.
    """

    # Maps lowercase name keys → (class, alias_list)
    char_dict: ClassVar[dict[str, tuple[type[BaseChar], list[str]]]] = {}

    _instance_cache: dict[str, BaseChar] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    @classmethod
    def register(cls, char_class: type[BaseChar]) -> None:
        """Register a character class."""
        key = char_class.name.lower()
        aliases: list[str] = []

        # Collect aliases if defined on the class
        if hasattr(char_class, "aliases"):
            aliases = list(char_class.aliases)

        cls.char_dict[key] = (char_class, aliases)
        logger.debug("Registered char: %s (aliases: %s)", key, aliases)

    @classmethod
    def _ensure_registered(cls) -> None:
        """Lazy-import all known character classes."""
        if cls.char_dict:
            return

        from module.neverness.char.zero import Zero
        from module.neverness.char.mint import Mint
        from module.neverness.char.sakiri import Sakiri
        from module.neverness.char.nanally import Nanally
        from module.neverness.char.jiuyuan import Jiuyuan
        from module.neverness.char.hotori import Hotori
        from module.neverness.char.healer import Healer

        cls.register(Zero)
        cls.register(Mint)
        cls.register(Sakiri)
        cls.register(Nanally)
        cls.register(Jiuyuan)
        cls.register(Hotori)
        cls.register(Healer)

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    @classmethod
    def _find_class(cls, name: str) -> type[BaseChar] | None:
        """Find a character class by name or alias."""
        cls._ensure_registered()
        key = name.lower().strip()

        # Direct match
        if key in cls.char_dict:
            return cls.char_dict[key][0]

        # Alias match
        for char_cls, aliases in cls.char_dict.values():
            if key in [a.lower() for a in aliases]:
                return char_cls

        return None

    # ------------------------------------------------------------------
    # Build / get
    # ------------------------------------------------------------------
    @classmethod
    def _build_char_instance(cls, name: str, task: Any = None, pos: int = 0) -> BaseChar | None:
        """Create a fresh character instance by name."""
        char_cls = cls._find_class(name)
        if char_cls is None:
            logger.warning("Unknown character: %s", name)
            return None

        try:
            instance = char_cls(task=task, pos=pos)
            logger.info("Built %s at pos %d", instance.name, pos)
            return instance
        except Exception:
            logger.exception("Failed to build character %s", name)
            return None

    @classmethod
    def get_char_by_name(cls, name: str, task: Any = None, pos: int = 0) -> BaseChar | None:
        """Get a cached or new character instance by name."""
        cache_key = f"{name.lower().strip()}:{pos}"

        if cache_key in cls._instance_cache:
            instance = cls._instance_cache[cache_key]
            if task is not None:
                instance.task = task
            return instance

        instance = cls._build_char_instance(name, task=task, pos=pos)
        if instance is not None:
            cls._instance_cache[cache_key] = instance
        return instance

    @classmethod
    def get_char_by_pos(cls, pos: int, char_names: list[str], task: Any = None) -> BaseChar | None:
        """Get character at team position *pos* (0-3)."""
        if pos < 0 or pos >= len(char_names):
            logger.warning("Invalid pos %d for team of %d", pos, len(char_names))
            return None
        return cls.get_char_by_name(char_names[pos], task=task, pos=pos)

    @classmethod
    def get_char_feature_by_pos(cls, pos: int) -> dict[str, Any] | None:
        """Get feature metadata for a character at position *pos*.

        Returns a dict with keys: name, role, element, skill_key, etc.
        """
        cls._ensure_registered()
        # In practice this would map pos → feature data loaded from JSON/DB;
        # for now return the class attributes of the first matching char.
        names = list(cls.char_dict.keys())
        if pos < 0 or pos >= len(names):
            return None

        char_cls, _ = cls.char_dict[names[pos]]
        return {
            "name": char_cls.name,
            "role": char_cls.role.value if hasattr(char_cls.role, "value") else str(char_cls.role),
            "element": char_cls.element.value if hasattr(char_cls.element, "value") else str(char_cls.element),
            "skill_key": char_cls.skill_key,
            "ultimate_key": char_cls.ultimate_key,
            "arc_key": char_cls.arc_key,
            "skill_cd": char_cls.skill_cd,
            "ultimate_cd": char_cls.ultimate_cd,
            "arc_cd": char_cls.arc_cd,
        }

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the instance cache."""
        cls._instance_cache.clear()
        logger.debug("CharFactory cache cleared")

    @classmethod
    def list_registered(cls) -> list[str]:
        """List all registered character names."""
        cls._ensure_registered()
        return [cls_char.name for cls_char, _ in cls.char_dict.values()]


# ------------------------------------------------------------------
# Module-level convenience functions
# ------------------------------------------------------------------
def get_char_by_name(name: str, task: Any = None, pos: int = 0) -> BaseChar | None:
    return CharFactory.get_char_by_name(name, task=task, pos=pos)


def get_char_by_pos(pos: int, char_names: list[str], task: Any = None) -> BaseChar | None:
    return CharFactory.get_char_by_pos(pos, char_names, task=task)


def get_char_feature_by_pos(pos: int) -> dict[str, Any] | None:
    return CharFactory.get_char_feature_by_pos(pos)
