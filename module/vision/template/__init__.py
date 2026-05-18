"""
Spec §11 — Template matching subsystem.

Delegates to module.base.template.Template for core matching.
Adds multi-scale matching and batch matching on top.
"""

import cv2
import numpy as np

from module.base.template import Template
from module.util.logger import logger


class TemplateMatcher:
    """Wraps module.base.template.Template with multi-scale + batch support."""

    def __init__(self, default_threshold: float = 0.85):
        self.default_threshold = default_threshold
        self._templates: dict[str, Template] = {}

    def load(self, name: str, filepath: str) -> Template:
        t = Template(filepath)
        self._templates[name] = t
        return t

    def get(self, name: str) -> Template | None:
        return self._templates.get(name)

    def remove(self, name: str):
        self._templates.pop(name, None)

    def match(self, name: str, screenshot, threshold: float | None = None) -> tuple | None:
        """Match a single template. Returns (similarity, (x, y)) or None."""
        t = self._templates.get(name)
        if t is None:
            logger.warning(f'TemplateMatcher: template "{name}" not loaded')
            return None
        thresh = threshold or self.default_threshold
        return t.match_result(screenshot)

    def match_multi_scale(self, name: str, screenshot,
                          scales: list[float] | None = None,
                          threshold: float | None = None) -> list[tuple]:
        """Match template at multiple scales."""
        t = self._templates.get(name)
        if t is None:
            return []
        thresh = threshold or self.default_threshold
        scales = scales or [0.9, 1.0, 1.1]
        results = []
        h, w = screenshot.shape[:2]
        for scale in scales:
            sw = int(w * scale)
            sh = int(h * scale)
            if sw < 10 or sh < 10:
                continue
            scaled = cv2.resize(screenshot, (sw, sh))
            r = t.match_result(scaled)
            if r is not None and r[0] >= thresh:
                # Rescale coordinates back
                sim, (x, y) = r
                results.append((sim, (int(x / scale), int(y / scale)), scale))
        return sorted(results, key=lambda r: -r[0])

    def list_templates(self) -> list[str]:
        return sorted(self._templates.keys())

    @property
    def template_count(self) -> int:
        return len(self._templates)
