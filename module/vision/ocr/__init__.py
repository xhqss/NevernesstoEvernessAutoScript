"""
Spec §11 — Vision OCR subsystem.

Delegates to module.ocr for text recognition.
Adds ROI-based batch OCR on top.
"""

import time
from typing import Any

from module.ocr import Ocr, OcrBase, OcrResult
from module.ocr.router import OcrRequest, OcrTaskType, route_ocr, resolve_engine_name
from module.ocr.cache import OcrCache
from module.util.logger import logger


class VisionOCR:
    """Vision-layer OCR wrapper. Delegates to module.ocr engines."""

    def __init__(self, cache_ttl_s: float = 2.0):
        self.cache = OcrCache(ttl_s=cache_ttl_s)
        self._engines: dict[str, Any] = {}

    def read_text(self, image, region=None, engine: str = "default",
                  allow_list: str | None = None) -> str:
        """Read text from image or region. Returns text string."""
        try:
            ocr = Ocr(
                buttons=[region] if region is not None else [(0, 0, image.shape[1], image.shape[0])],
                engine=engine,
                alphabet=allow_list,
            )
            results = ocr.ocr(image)
            if results:
                return results[0]
            return ""
        except Exception as e:
            logger.error(f'VisionOCR read_text failed: {e}')
            return ""

    def read_digit(self, image, region=None) -> int:
        """Read a digit value from image. Returns int."""
        from module.ocr import Digit
        try:
            digit = Digit(
                buttons=[region] if region is not None else [(0, 0, image.shape[1], image.shape[0])],
                engine="rapid",
            )
            return digit.ocr(image)
        except Exception:
            return 0

    def route(self, request: OcrRequest) -> str:
        """Route OCR request to best engine. Returns engine name."""
        pref = route_ocr(request)
        return resolve_engine_name(pref)

    def stats(self) -> dict:
        return {
            "cache": self.cache.stats(),
            "engines": list(self._engines.keys()),
        }
