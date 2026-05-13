"""CustomCharManager – singleton managing custom characters and their combos.

FAITHFUL port of ok-nte's CustomCharManager (~790 lines).

Features:
- JSON-based persistence (schema-migration aware)
- Feature-image caching with template matching (cv2.matchTemplate)
- Character CRUD (create, read, update, delete)
- Combo CRUD (per-character combo scripts)
- Fixed team management (preset team configurations)
- Thread-safe singleton
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from copy import deepcopy
from typing import Any, ClassVar

import cv2
import numpy as np

from module.neverness.char.custom.char import CustomChar, ComboParser
from module.feature.box import Box
from module.feature.feature import Feature

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema version for migration
# ---------------------------------------------------------------------------
CURRENT_SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# CustomCharManager
# ---------------------------------------------------------------------------
class CustomCharManager:
    """Singleton managing user-defined characters, combos, and feature images.

    Data is persisted to ``<config_dir>/custom_chars.json``.
    """

    _instance: CustomCharManager | None = None
    _instance_lock = threading.Lock()

    # Configurable
    max_workers: int = 4
    default_match_threshold: float = 0.80

    def __new__(cls) -> CustomCharManager:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialise()
                    cls._instance = instance
        return cls._instance

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def _initialise(self) -> None:
        self._lock = threading.RLock()

        # Determine config directory
        self._config_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "..", "..", "config",
        )
        self._data_path = os.path.join(self._config_dir, "custom_chars.json")
        self._feature_dir = os.path.join(self._config_dir, "features")

        os.makedirs(self._feature_dir, exist_ok=True)

        # In-memory state
        self._characters: dict[str, dict] = {}       # char_id → data dict
        self._combos: dict[str, dict[str, str]] = {}  # char_id → {combo_name: text}
        self._teams: dict[str, list[str]] = {}        # team_name → [char_id, ...]
        self._feature_cache: dict[str, np.ndarray] = {}  # char_id → image mat
        self._dirty: bool = False

        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        """Load from JSON, creating defaults if not present."""
        if not os.path.isfile(self._data_path):
            self._save()
            return

        try:
            with open(self._data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.exception("Failed to load %s – using defaults", self._data_path)
            data = {}

        # Schema migration
        version = data.get("schema_version", 0)
        if version < CURRENT_SCHEMA_VERSION:
            data = self._migrate(data, version)

        self._characters = data.get("characters", {})
        self._combos = data.get("combos", {})
        self._teams = data.get("teams", {})
        self._dirty = False

        logger.info(
            "Loaded %d characters, %d combos, %d teams from %s",
            len(self._characters), len(self._combos), len(self._teams),
            self._data_path,
        )

    def _save(self) -> None:
        """Persist current state to JSON."""
        with self._lock:
            data = {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "characters": self._characters,
                "combos": self._combos,
                "teams": self._teams,
            }
            try:
                with open(self._data_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self._dirty = False
                logger.debug("Saved custom_chars.json")
            except OSError:
                logger.exception("Failed to save %s", self._data_path)

    def mark_dirty(self) -> None:
        self._dirty = True

    def flush(self) -> None:
        """Persist if dirty."""
        if self._dirty:
            self._save()

    # ------------------------------------------------------------------
    # Schema migration
    # ------------------------------------------------------------------
    def _migrate(self, data: dict, from_version: int) -> dict:
        """Migrate data from an older schema version to current."""
        logger.info("Migrating schema v%d → v%d", from_version, CURRENT_SCHEMA_VERSION)

        if from_version < 1:
            # v0 → v1: added teams section
            data.setdefault("teams", {})
        if from_version < 2:
            # v1 → v2: added combo display names
            for char_id in data.get("combos", {}):
                if isinstance(data["combos"][char_id], list):
                    # Convert old list format to dict
                    old_list = data["combos"][char_id]
                    data["combos"][char_id] = {f"combo_{i}": c for i, c in enumerate(old_list)}

        data["schema_version"] = CURRENT_SCHEMA_VERSION
        return data

    # ------------------------------------------------------------------
    # Character CRUD
    # ------------------------------------------------------------------
    def create_character(
        self,
        char_id: str,
        display_name: str,
        role: str = "dps",
        element: str = "physical",
        pos: int = 0,
        combo_text: str = "",
        image_path: str = "",
    ) -> dict | None:
        """Create a new custom character.  Returns the data dict or None."""
        with self._lock:
            if char_id in self._characters:
                logger.warning("Character %s already exists", char_id)
                return None

            entry = {
                "char_id": char_id,
                "display_name": display_name,
                "role": role,
                "element": element,
                "pos": pos,
                "combo_text": combo_text,
                "image_path": image_path,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            self._characters[char_id] = entry

            if combo_text:
                self._combos[char_id] = {"default": combo_text}

            self.mark_dirty()
            logger.info("Created character %s (%s)", char_id, display_name)
            return deepcopy(entry)

    def get_character(self, char_id: str) -> dict | None:
        """Retrieve a character's data."""
        with self._lock:
            entry = self._characters.get(char_id)
            return deepcopy(entry) if entry else None

    def update_character(self, char_id: str, **kwargs) -> bool:
        """Update fields of an existing character.  Returns True on success."""
        with self._lock:
            entry = self._characters.get(char_id)
            if entry is None:
                logger.warning("Character %s not found for update", char_id)
                return False

            allowed = {
                "display_name", "role", "element", "pos",
                "combo_text", "image_path",
            }
            for key, value in kwargs.items():
                if key in allowed:
                    entry[key] = value

            entry["updated_at"] = time.time()

            # Sync combo text if changed
            if "combo_text" in kwargs:
                self._combos.setdefault(char_id, {})["default"] = kwargs["combo_text"]

            # Invalidate feature cache if image changed
            if "image_path" in kwargs:
                self._feature_cache.pop(char_id, None)

            self.mark_dirty()
            logger.info("Updated character %s", char_id)
            return True

    def delete_character(self, char_id: str) -> bool:
        """Remove a character and its data.  Returns True if deleted."""
        with self._lock:
            existed = char_id in self._characters
            if existed:
                del self._characters[char_id]
                self._combos.pop(char_id, None)
                self._feature_cache.pop(char_id, None)

                # Remove from all teams
                for team in self._teams.values():
                    if char_id in team:
                        team.remove(char_id)

                self.mark_dirty()
                logger.info("Deleted character %s", char_id)
            return existed

    def list_characters(self) -> list[dict]:
        """List all characters (shallow copies)."""
        with self._lock:
            return [
                {
                    "char_id": cid,
                    "display_name": c["display_name"],
                    "role": c.get("role", "dps"),
                    "element": c.get("element", "physical"),
                    "pos": c.get("pos", 0),
                }
                for cid, c in self._characters.items()
            ]

    # ------------------------------------------------------------------
    # Combo CRUD
    # ------------------------------------------------------------------
    def get_combos(self, char_id: str) -> dict[str, str]:
        """Get all combo scripts for a character.  Returns {name: text}."""
        with self._lock:
            return dict(self._combos.get(char_id, {}))

    def get_combo(self, char_id: str, combo_name: str = "default") -> str | None:
        """Get a specific combo script."""
        with self._lock:
            return self._combos.get(char_id, {}).get(combo_name)

    def set_combo(self, char_id: str, combo_name: str, combo_text: str) -> bool:
        """Add or update a combo script.  Returns True if char exists."""
        with self._lock:
            if char_id not in self._characters:
                logger.warning("Character %s not found for combo update", char_id)
                return False

            self._combos.setdefault(char_id, {})[combo_name] = combo_text
            self.mark_dirty()
            logger.info("Set combo %s/%s (%d chars)", char_id, combo_name, len(combo_text))
            return True

    def delete_combo(self, char_id: str, combo_name: str) -> bool:
        """Remove a combo.  Returns True if it existed."""
        with self._lock:
            combos = self._combos.get(char_id, {})
            existed = combo_name in combos
            if existed:
                del combos[combo_name]
                if not combos:
                    self._combos.pop(char_id, None)
                self.mark_dirty()
                logger.info("Deleted combo %s/%s", char_id, combo_name)
            return existed

    def list_combos(self, char_id: str) -> list[str]:
        """List all combo names for a character."""
        with self._lock:
            return list(self._combos.get(char_id, {}).keys())

    # ------------------------------------------------------------------
    # Feature image management
    # ------------------------------------------------------------------
    def get_feature_image(self, char_id: str) -> np.ndarray | None:
        """Load (or retrieve cached) the feature image for a character."""
        with self._lock:
            if char_id in self._feature_cache:
                return self._feature_cache[char_id]

            entry = self._characters.get(char_id)
            if entry is None:
                return None

            image_path = entry.get("image_path", "")
            if not image_path or not os.path.isfile(image_path):
                # Look for a feature image in the features directory
                image_path = os.path.join(self._feature_dir, f"{char_id}.png")
                if not os.path.isfile(image_path):
                    logger.debug("No feature image for %s", char_id)
                    return None

            try:
                img = cv2.imread(image_path)
                if img is not None:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    self._feature_cache[char_id] = img
                    return img
            except Exception:
                logger.exception("Failed to load feature image %s", image_path)

            return None

    def set_feature_image(self, char_id: str, image: np.ndarray) -> bool:
        """Set the feature image directly (overwrites cached and on-disk)."""
        with self._lock:
            if char_id not in self._characters:
                logger.warning("Character %s not found", char_id)
                return False

            self._feature_cache[char_id] = image.copy()

            image_path = os.path.join(self._feature_dir, f"{char_id}.png")
            try:
                bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                cv2.imwrite(image_path, bgr)
                self._characters[char_id]["image_path"] = image_path
                self._characters[char_id]["updated_at"] = time.time()
                self.mark_dirty()
                logger.info("Feature image saved for %s", char_id)
                return True
            except Exception:
                logger.exception("Failed to save feature image for %s", char_id)
                return False

    def clear_feature_cache(self, char_id: str | None = None) -> None:
        """Clear cached feature images."""
        with self._lock:
            if char_id is None:
                self._feature_cache.clear()
            else:
                self._feature_cache.pop(char_id, None)

    # ------------------------------------------------------------------
    # Template matching
    # ------------------------------------------------------------------
    def match_feature(
        self,
        char_id: str,
        screenshot: np.ndarray,
        threshold: float | None = None,
    ) -> Box | None:
        """Template-match the character's feature image on a screenshot.

        Args:
            char_id: Character identifier.
            screenshot: Game screenshot (numpy RGB array).
            threshold: Minimum match confidence (0-1).  Uses default if None.

        Returns:
            Box of the best match, or None.
        """
        feature_img = self.get_feature_image(char_id)
        if feature_img is None:
            logger.debug("match_feature: no image for %s", char_id)
            return None

        if threshold is None:
            threshold = self.default_match_threshold

        h_f, w_f = feature_img.shape[:2]
        h_s, w_s = screenshot.shape[:2]

        if h_f > h_s or w_f > w_s:
            logger.debug(
                "match_feature: feature %s is larger than screenshot", char_id,
            )
            return None

        try:
            result = cv2.matchTemplate(
                screenshot, feature_img, cv2.TM_CCOEFF_NORMED,
            )
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val < threshold:
                logger.debug(
                    "match_feature %s: best=%.3f < %.3f", char_id, max_val, threshold,
                )
                return None

            x, y = max_loc
            box = Box(
                x=int(x),
                y=int(y),
                width=w_f,
                height=h_f,
                confidence=float(max_val),
                name=char_id,
            )
            logger.debug(
                "match_feature %s: found at (%d, %d) conf=%.3f",
                char_id, x, y, max_val,
            )
            return box

        except Exception:
            logger.exception("match_feature failed for %s", char_id)
            return None

    def match_all_features(
        self,
        screenshot: np.ndarray,
        threshold: float | None = None,
    ) -> dict[str, Box]:
        """Match all known character features against a screenshot.

        Returns a dict mapping char_id → best Box.
        """
        results: dict[str, Box] = {}
        with self._lock:
            char_ids = list(self._characters.keys())

        for cid in char_ids:
            box = self.match_feature(cid, screenshot, threshold)
            if box is not None:
                results[cid] = box

        return results

    # ------------------------------------------------------------------
    # Team management
    # ------------------------------------------------------------------
    def get_team(self, team_name: str) -> list[str]:
        """Get the character IDs for a named team."""
        with self._lock:
            return list(self._teams.get(team_name, []))

    def set_team(self, team_name: str, char_ids: list[str]) -> None:
        """Set (or overwrite) a team configuration."""
        with self._lock:
            # Validate that all char_ids exist
            unknown = [cid for cid in char_ids if cid not in self._characters]
            if unknown:
                logger.warning("Team %s references unknown characters: %s", team_name, unknown)

            self._teams[team_name] = list(char_ids)[:4]  # Max 4 characters
            self.mark_dirty()
            logger.info("Team %s set: %s", team_name, self._teams[team_name])

    def delete_team(self, team_name: str) -> bool:
        """Remove a team.  Returns True if it existed."""
        with self._lock:
            existed = team_name in self._teams
            if existed:
                del self._teams[team_name]
                self.mark_dirty()
                logger.info("Deleted team %s", team_name)
            return existed

    def list_teams(self) -> list[str]:
        """List all team names."""
        with self._lock:
            return list(self._teams.keys())

    # ------------------------------------------------------------------
    # Convenience – build character instances
    # ------------------------------------------------------------------
    def build_char(self, char_id: str, task: Any = None, pos: int = 0) -> CustomChar | None:
        """Build a CustomChar instance from stored data."""
        entry = self.get_character(char_id)
        if entry is None:
            return None

        combo_text = entry.get("combo_text", "")
        if not combo_text:
            # Check combos dict
            combos = self.get_combos(char_id)
            combo_text = combos.get("default", "")

        try:
            char = CustomChar(
                task=task,
                pos=pos,
                combo_text=combo_text,
                display_name=entry.get("display_name", char_id),
            )
            # Override role/element from stored config
            from module.neverness.char.base import Role, Element
            try:
                char.role = Role(entry.get("role", "dps"))
            except ValueError:
                char.role = Role.DPS
            try:
                char.element = Element(entry.get("element", "physical"))
            except ValueError:
                char.element = Element.PHYSICAL

            return char
        except Exception:
            logger.exception("Failed to build CustomChar %s", char_id)
            return None

    def build_team(self, team_name: str, task: Any = None) -> list[CustomChar | None]:
        """Build a full team of CustomChar instances."""
        char_ids = self.get_team(team_name)
        return [self.build_char(cid, task=task, pos=i) for i, cid in enumerate(char_ids)]

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------
    def export_data(self) -> dict:
        """Export all data as a serialisable dict."""
        with self._lock:
            return {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "characters": deepcopy(self._characters),
                "combos": deepcopy(self._combos),
                "teams": deepcopy(self._teams),
            }

    def import_data(self, data: dict, merge: bool = False) -> int:
        """Import data from a dict.

        Args:
            data: The data dict (must match schema).
            merge: If True, merge with existing; if False, replace.

        Returns:
            Number of characters imported.
        """
        version = data.get("schema_version", 0)
        if version < CURRENT_SCHEMA_VERSION:
            data = self._migrate(data, version)

        with self._lock:
            if merge:
                self._characters.update(data.get("characters", {}))
                for cid, combos in data.get("combos", {}).items():
                    self._combos.setdefault(cid, {}).update(combos)
                self._teams.update(data.get("teams", {}))
            else:
                self._characters = data.get("characters", {})
                self._combos = data.get("combos", {})
                self._teams = data.get("teams", {})

            self._feature_cache.clear()
            self.mark_dirty()
            count = len(data.get("characters", {}))
            logger.info("Imported %d characters (merge=%s)", count, merge)
            return count

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------
    def delete_all(self) -> None:
        """Remove everything – characters, combos, teams, cache."""
        with self._lock:
            self._characters.clear()
            self._combos.clear()
            self._teams.clear()
            self._feature_cache.clear()
            self.mark_dirty()
            logger.warning("All custom char data cleared")

    def reload(self) -> None:
        """Reload from disk, discarding in-memory changes."""
        self._feature_cache.clear()
        self._load()

    def shutdown(self) -> None:
        """Persist and clean up."""
        self.flush()
        self._feature_cache.clear()
        logger.info("CustomCharManager shut down")
