"""
Spec §11 — Vision Runtime top-level exports.

Subsystems: template matching, ORB feature matching, OCR routing,
image preprocessing, vision routing, confidence calibration.
"""

from module.vision.template import TemplateMatcher
from module.vision.orb import ORBMatcher
from module.vision.ocr import VisionOCR
from module.vision.preprocess import Preprocessor
from module.vision.router import VisionRouter
from module.vision.confidence import ConfidenceThresholds

__all__ = [
    "TemplateMatcher",
    "ORBMatcher",
    "VisionOCR",
    "Preprocessor",
    "VisionRouter",
    "ConfidenceThresholds",
]
