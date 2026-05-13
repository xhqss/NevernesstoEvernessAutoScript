"""
FastTravelTask - Auto teleport via map interaction.

Detects the map_location_card and clicks the teleport button
when a matching destination is found.
"""

from module.util.logger import logger

from module.neverness.Labels import Labels
from module.neverness.task.base import BaseNTETask
from module.neverness.util import image as iu


text_black_color = {
    "r": (0, 10),
    "g": (0, 10),
    "b": (0, 10),
}


class FastTravelTask(BaseNTETask):
    """Background trigger for auto-clicking teleport on the map."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "fast_travel"
        self.trigger_interval = 0.5
        self.default_config = {"_enabled": False}
        self.config.setdefault("match_text", "")
        self._match_keywords = ["Teleport", "传送"]

    # ------------------------------------------------------------------
    # Trigger entry point
    # ------------------------------------------------------------------

    def run(self):
        """Check if map is open and click teleport."""
        # Only run when NOT in team (i.e., map is open)
        if self.is_in_team():
            return

        # Check for map location card
        if not self.find_one(Labels.map_location_card, threshold=0.8):
            return

        # Find and click teleport button
        if not (btn := self.find_traval_button()):
            return

        # Parse match text config
        if config_match := self.config.get("match_text"):
            self._match_keywords = [s.strip() for s in config_match.split(",")]

        # OCR the teleport destination text
        to_x = (btn.x + btn.width) / self.width
        results = self.ocr(
            area=self.box_of_screen(0.7438, 0.8736, to_x, 0.9118).area,
            letter=(0, 0, 0),
            threshold=128,
        )

        # Match against keywords
        if any(
            any(keyword in str(r) for keyword in self._match_keywords)
            for r in (results or [])
        ):
            self.click_traval_button(btn)
            return True

        return False
