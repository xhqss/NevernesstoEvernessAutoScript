"""
Spec §31 — Structured error codes.

5 categories, 25 error codes (E1000-E5004).
Each error includes recoverable, user_action, developer_action.
"""

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True)
class SpecError:
    code: str
    category: str
    message: str
    recoverable: bool = True
    user_action: str = ""
    developer_action: str = ""

    def __str__(self):
        return f"[{self.code}] {self.message}"

    @property
    def is_critical(self) -> bool:
        return not self.recoverable


# ── Category definitions ──────────────────────────────────────────────

DEVICE_ERRORS: dict[str, SpecError] = {
    "E1000": SpecError("E1000", "DEVICE", "Device connection lost",
                        recoverable=True, user_action="Check cable/network",
                        developer_action="Verify ADB daemon or window handle"),
    "E1001": SpecError("E1001", "DEVICE", "Screenshot capture failed",
                        recoverable=True, user_action="Restart capture method",
                        developer_action="Check screenshot backend availability"),
    "E1002": SpecError("E1002", "DEVICE", "Input injection failed",
                        recoverable=True, user_action="Retry input",
                        developer_action="Verify interaction backend permissions"),
    "E1003": SpecError("E1003", "DEVICE", "Device resolution mismatch",
                        recoverable=True, user_action="Set resolution to 1280x720",
                        developer_action="Force resize in capture pipeline"),
    "E1004": SpecError("E1004", "DEVICE", "Device latency exceeds budget",
                        recoverable=True, user_action="Close background apps",
                        developer_action="Profile device, adjust tick budget"),
}

OCR_ERRORS: dict[str, SpecError] = {
    "E2000": SpecError("E2000", "OCR", "OCR engine not available",
                        recoverable=True, user_action="Install OCR dependencies",
                        developer_action="Check cnocr/paddleocr/rapidocr installation"),
    "E2001": SpecError("E2001", "OCR", "OCR result empty",
                        recoverable=True, user_action="Check game screen visibility",
                        developer_action="Adjust ROI or preprocess parameters"),
    "E2002": SpecError("E2002", "OCR", "OCR confidence below threshold",
                        recoverable=True, user_action="Check for visual noise",
                        developer_action="Tune threshold or preprocess pipeline"),
    "E2003": SpecError("E2003", "OCR", "OCR digit parse failure",
                        recoverable=True, user_action="Verify number display",
                        developer_action="Check digit model and alphabet filter"),
    "E2004": SpecError("E2004", "OCR", "OCR loop detected",
                        recoverable=True, user_action="Check for frozen game UI",
                        developer_action="Add loop-breaking heuristic or cache invalidation"),
}

RUNTIME_ERRORS: dict[str, SpecError] = {
    "E3000": SpecError("E3000", "RUNTIME", "Tick budget exceeded",
                        recoverable=True, user_action="Wait for system to stabilize",
                        developer_action="Profile tick pipeline, optimize slow stages"),
    "E3001": SpecError("E3001", "RUNTIME", "Tick starvation detected",
                        recoverable=True, user_action="Check system load",
                        developer_action="Verify TickLoop thread scheduling"),
    "E3002": SpecError("E3002", "RUNTIME", "Invalid state transition",
                        recoverable=True, user_action="Restart automation",
                        developer_action="Audit StateMachine transition table"),
    "E3003": SpecError("E3003", "RUNTIME", "Event bus listener error",
                        recoverable=True, user_action="Retry operation",
                        developer_action="Check listener exception handling"),
    "E3004": SpecError("E3004", "RUNTIME", "Module healthcheck failed",
                        recoverable=True, user_action="Restart failing module",
                        developer_action="Investigate module healthcheck report"),
}

RECOVERY_ERRORS: dict[str, SpecError] = {
    "E4000": SpecError("E4000", "RECOVERY", "Recovery action failed",
                        recoverable=True, user_action="Manual intervention may be needed",
                        developer_action="Check recovery handler implementation"),
    "E4001": SpecError("E4001", "RECOVERY", "Recovery escalation limit reached",
                        recoverable=False, user_action="Restart application",
                        developer_action="Investigate root cause of L9 escalation"),
    "E4002": SpecError("E4002", "RECOVERY", "Recovery cooldown active",
                        recoverable=True, user_action="Wait for cooldown to expire",
                        developer_action="Adjust cooldown threshold if too aggressive"),
    "E4003": SpecError("E4003", "RECOVERY", "Recovery weight exhausted",
                        recoverable=True, user_action="Reset recovery weights",
                        developer_action="Check if recovery strategy is effective"),
    "E4004": SpecError("E4004", "RECOVERY", "Module restart failed",
                        recoverable=True, user_action="Manually restart module",
                        developer_action="Check module stop/start cycle"),
}

SCHEDULER_ERRORS: dict[str, SpecError] = {
    "E5000": SpecError("E5000", "SCHEDULER", "Task scheduling conflict",
                        recoverable=True, user_action="Adjust task schedule",
                        developer_action="Check task dependency graph"),
    "E5001": SpecError("E5001", "SCHEDULER", "Task timeout exceeded",
                        recoverable=True, user_action="Increase task timeout",
                        developer_action="Profile task execution time"),
    "E5002": SpecError("E5002", "SCHEDULER", "Task queue overflow",
                        recoverable=True, user_action="Reduce task frequency",
                        developer_action="Increase queue size or add backpressure"),
    "E5003": SpecError("E5003", "SCHEDULER", "Config hot reload failed",
                        recoverable=True, user_action="Check config file syntax",
                        developer_action="Verify schema validation and fallback"),
    "E5004": SpecError("E5004", "SCHEDULER", "Resource threshold exceeded",
                        recoverable=True, user_action="Free disk/memory resources",
                        developer_action="Add resource-aware scheduling"),
}


# ── Combined lookup ───────────────────────────────────────────────────

_ALL_MAP: dict[str, SpecError] = {}
_ALL_MAP.update(DEVICE_ERRORS)
_ALL_MAP.update(OCR_ERRORS)
_ALL_MAP.update(RUNTIME_ERRORS)
_ALL_MAP.update(RECOVERY_ERRORS)
_ALL_MAP.update(SCHEDULER_ERRORS)

_all_codes: list[str] = sorted(_ALL_MAP.keys())


def get_error(code: str) -> SpecError | None:
    return _ALL_MAP.get(code.upper())


def error_category(code: str) -> str:
    err = _ALL_MAP.get(code.upper())
    return err.category if err else "UNKNOWN"


def all_codes() -> list[str]:
    return list(_all_codes)
