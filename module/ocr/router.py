"""
Spec §12 — Deterministic OCR router.

Routes OCR requests to the optimal engine based on content type:
  digit           → rapidocr (fast, numeric)
  latency<50ms    → rapidocr (speed-optimized)
  text_complexity=high → paddleocr (accuracy-optimized)
  icon            → orb (feature matching, delegated to vision)
"""

from enum import Enum


class OcrTaskType(str, Enum):
    DIGIT = "digit"
    TEXT = "text"
    ICON = "icon"
    AUTO = "auto"


class OcrEnginePreference(str, Enum):
    RAPID = "rapid"
    PADDLE = "paddle"
    CNOCR = "cnocr"
    DEFAULT = "default"


LATENCY_BUDGET_MS = 50


class OcrRequest:
    __slots__ = ('task_type', 'latency_budget_ms', 'text_complexity',
                 'image_hash', 'roi_hash', 'allow_list')

    def __init__(self, *, task_type: OcrTaskType = OcrTaskType.AUTO,
                 latency_budget_ms: float = 500,
                 text_complexity: str = "low",
                 image_hash: str = "",
                 roi_hash: str = "",
                 allow_list: str | None = None):
        self.task_type = task_type
        self.latency_budget_ms = latency_budget_ms
        self.text_complexity = text_complexity
        self.image_hash = image_hash
        self.roi_hash = roi_hash
        self.allow_list = allow_list


def route_ocr(request: OcrRequest) -> OcrEnginePreference:
    """Deterministic OCR engine router (§12).

    Priority:
      1. digit → rapidocr
      2. latency_budget < 50ms → rapidocr
      3. text_complexity=high → paddleocr
      4. icon → orb (not an OCR engine, handled by vision router)
      5. default → cnocr
    """
    if request.task_type == OcrTaskType.ICON:
        return OcrEnginePreference.DEFAULT  # delegated to vision ORB

    if request.task_type == OcrTaskType.DIGIT:
        return OcrEnginePreference.RAPID

    if request.latency_budget_ms < LATENCY_BUDGET_MS:
        return OcrEnginePreference.RAPID

    if request.text_complexity == "high":
        return OcrEnginePreference.PADDLE

    return OcrEnginePreference.CNOCR


def resolve_engine_name(preference: OcrEnginePreference) -> str:
    """Map OCR engine preference to actual engine name string."""
    mapping = {
        OcrEnginePreference.RAPID: "rapid",
        OcrEnginePreference.PADDLE: "paddle",
        OcrEnginePreference.CNOCR: "cnocr",
        OcrEnginePreference.DEFAULT: "default",
    }
    return mapping.get(preference, "default")
