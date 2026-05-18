"""
Spec §11 — Confidence calibration thresholds.

Default thresholds for each matcher type.
Thresholds are tunable per deployment environment.
"""


class ConfidenceThresholds:
    """Calibrated confidence thresholds for vision matching."""

    # Default calibrated values (§11 spec)
    TEMPLATE: float = 0.85
    ORB: float = 0.70
    OCR: float = 0.80
    DIGIT: float = 0.90

    # Instance overrides
    def __init__(self, **kwargs):
        self.template = kwargs.get("template", self.TEMPLATE)
        self.orb = kwargs.get("orb", self.ORB)
        self.ocr = kwargs.get("ocr", self.OCR)
        self.digit = kwargs.get("digit", self.DIGIT)

    def get(self, matcher_type: str) -> float:
        mapping = {
            "template": self.template,
            "orb": self.orb,
            "ocr": self.ocr,
            "digit": self.digit,
        }
        return mapping.get(matcher_type, 0.80)

    def set(self, matcher_type: str, value: float):
        value = max(0.0, min(1.0, value))
        if matcher_type == "template":
            self.template = value
        elif matcher_type == "orb":
            self.orb = value
        elif matcher_type == "ocr":
            self.ocr = value
        elif matcher_type == "digit":
            self.digit = value

    def to_dict(self) -> dict:
        return {
            "template": self.template,
            "orb": self.orb,
            "ocr": self.ocr,
            "digit": self.digit,
        }

    @classmethod
    def strict(cls) -> "ConfidenceThresholds":
        """Stricter thresholds for safety-critical scenarios."""
        return cls(template=0.90, orb=0.80, ocr=0.85, digit=0.95)

    @classmethod
    def relaxed(cls) -> "ConfidenceThresholds":
        """Relaxed thresholds for noisy/compressed video feeds."""
        return cls(template=0.75, orb=0.60, ocr=0.70, digit=0.80)
