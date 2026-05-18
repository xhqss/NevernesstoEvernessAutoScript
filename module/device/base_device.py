"""
Spec §9 — BaseDevice ABC + DeviceCapability dataclass.

Provides abstract interface for all device backends
and latency profile presets for timing compensation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class DeviceCapability:
    """Device capability profile for latency compensation.

    Provides presets for ADB emulator and PC window modes.
    """

    screenshot_latency_ms: float = 15.0
    screenshot_jitter_ms: float = 5.0
    input_latency_ms: float = 10.0
    input_jitter_ms: float = 3.0
    refresh_rate_hz: int = 60
    resolution: tuple[int, int] = (1280, 720)

    # ── Computed ──────────────────────────────────────────────────

    @property
    def total_action_latency_ms(self) -> float:
        """Total round-trip latency for one action cycle."""
        return (self.screenshot_latency_ms + self.input_latency_ms
                + self.screenshot_jitter_ms + self.input_jitter_ms)

    @property
    def tick_timing_budget_ms(self) -> float:
        """How much of the 100ms tick budget is available after device overhead."""
        min_budget = 20.0  # absolute minimum for logic
        available = 100.0 - self.total_action_latency_ms
        return max(min_budget, available)

    # ── Presets ───────────────────────────────────────────────────

    @classmethod
    def adb_emulator(cls) -> "DeviceCapability":
        return cls(
            screenshot_latency_ms=45.0,
            screenshot_jitter_ms=10.0,
            input_latency_ms=30.0,
            input_jitter_ms=8.0,
            refresh_rate_hz=60,
            resolution=(1280, 720),
        )

    @classmethod
    def pc_window(cls) -> "DeviceCapability":
        return cls(
            screenshot_latency_ms=15.0,
            screenshot_jitter_ms=5.0,
            input_latency_ms=10.0,
            input_jitter_ms=3.0,
            refresh_rate_hz=60,
            resolution=(1280, 720),
        )

    def dict(self) -> dict:
        return {
            "screenshot_latency_ms": self.screenshot_latency_ms,
            "screenshot_jitter_ms": self.screenshot_jitter_ms,
            "input_latency_ms": self.input_latency_ms,
            "input_jitter_ms": self.input_jitter_ms,
            "refresh_rate_hz": self.refresh_rate_hz,
            "resolution": list(self.resolution),
            "total_action_latency_ms": self.total_action_latency_ms,
            "tick_timing_budget_ms": self.tick_timing_budget_ms,
        }


class BaseDevice(ABC):
    """Abstract interface for all device backends.

    Must implement: screenshot, click, swipe, key, reconnect, latency_profile.
    """

    @abstractmethod
    def screenshot(self):
        """Capture current screen. Returns image array or None."""
        ...

    @abstractmethod
    def click(self, x: int, y: int) -> bool:
        """Tap at (x, y) in 1280x720 coordinate space."""
        ...

    @abstractmethod
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> bool:
        """Swipe from (x1,y1) to (x2,y2)."""
        ...

    @abstractmethod
    def key(self, key_code: str) -> bool:
        """Send a key event."""
        ...

    @abstractmethod
    def reconnect(self) -> bool:
        """Re-establish connection after disconnect."""
        ...

    @abstractmethod
    def latency_profile(self) -> dict:
        """Return device capability profile for timing compensation."""
        ...
