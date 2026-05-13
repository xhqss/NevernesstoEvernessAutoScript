"""ScreenPosition – builds Box objects for common screen regions."""

from __future__ import annotations

from module.feature.box import Box


class ScreenPosition:
    """Helper that produces Box objects anchored to screen edges / centre.

    All methods return a ``Box`` whose coordinates are relative to the
    game window (typically 1280 x 720 or similar).
    """

    def __init__(self, screen_width: int = 1280, screen_height: int = 720):
        self.w = screen_width
        self.h = screen_height

    # ------------------------------------------------------------------
    # Corner regions
    # ------------------------------------------------------------------
    @staticmethod
    def top_left(
        width: int = 200, height: int = 140, margin_x: int = 0, margin_y: int = 0,
    ) -> Box:
        return Box(x=margin_x, y=margin_y, width=width, height=height, name="top_left")

    @staticmethod
    def top_right(
        width: int = 200, height: int = 140, margin_x: int = 0, margin_y: int = 0,
        screen_width: int = 1280,
    ) -> Box:
        return Box(
            x=screen_width - width - margin_x,
            y=margin_y,
            width=width,
            height=height,
            name="top_right",
        )

    @staticmethod
    def bottom_left(
        width: int = 200, height: int = 140, margin_x: int = 0, margin_y: int = 0,
        screen_height: int = 720,
    ) -> Box:
        return Box(
            x=margin_x,
            y=screen_height - height - margin_y,
            width=width,
            height=height,
            name="bottom_left",
        )

    @staticmethod
    def bottom_right(
        width: int = 200, height: int = 140, margin_x: int = 0, margin_y: int = 0,
        screen_width: int = 1280, screen_height: int = 720,
    ) -> Box:
        return Box(
            x=screen_width - width - margin_x,
            y=screen_height - height - margin_y,
            width=width,
            height=height,
            name="bottom_right",
        )

    @staticmethod
    def center(
        width: int = 400, height: int = 400,
        screen_width: int = 1280, screen_height: int = 720,
    ) -> Box:
        return Box(
            x=(screen_width - width) // 2,
            y=(screen_height - height) // 2,
            width=width,
            height=height,
            name="center",
        )

    @staticmethod
    def _scale_box(box: Box, scale_x: float, scale_y: float | None = None) -> Box:
        """Scale a box relative to screen size changes."""
        if scale_y is None:
            scale_y = scale_x
        return Box(
            x=int(box.x * scale_x),
            y=int(box.y * scale_y),
            width=int(box.width * scale_x),
            height=int(box.height * scale_y),
            confidence=box.confidence,
            name=box.name,
        )

    # ------------------------------------------------------------------
    # Character bar regions (bottom UI)
    # ------------------------------------------------------------------
    def char_skill_box(self) -> Box:
        """Region around the skill icon."""
        return Box(
            x=int(self.w * 0.365),
            y=int(self.h * 0.78),
            width=int(self.w * 0.06),
            height=int(self.h * 0.09),
            name="skill",
        )

    def char_ultimate_box(self) -> Box:
        """Region around the ultimate icon."""
        return Box(
            x=int(self.w * 0.42),
            y=int(self.h * 0.78),
            width=int(self.w * 0.06),
            height=int(self.h * 0.09),
            name="ultimate",
        )

    def char_switch_box(self, slot: int) -> Box:
        """Region for character switch slot 0-3."""
        base_x = int(self.w * 0.48)
        spacing = int(self.w * 0.07)
        return Box(
            x=base_x + slot * spacing,
            y=int(self.h * 0.78),
            width=int(self.w * 0.06),
            height=int(self.h * 0.09),
            name=f"switch_{slot}",
        )
