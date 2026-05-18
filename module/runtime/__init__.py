"""
Runtime package — spec §6 RuntimeContext + module exports.

All runtime modules communicate through EventBus + RuntimeContext.
Direct module-to-module import is forbidden by convention.
"""

from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class RuntimeContext:
    """Spec §6 — thread-safe shared runtime context."""

    device: Any = None
    config: dict = field(default_factory=dict)
    state: str = "INIT"

    current_tick: int = 0
    runtime_start_ts: float = 0.0

    screenshot: Any = None
    last_action: str | None = None

    metrics: dict = field(default_factory=dict)
    cache: dict = field(default_factory=dict)

    lock: RLock = field(default_factory=RLock)

    def update(self, **kwargs):
        """Thread-safe batch update."""
        with self.lock:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)

    def get(self, key, default=None):
        with self.lock:
            return getattr(self, key, default)

    def set(self, key, value):
        with self.lock:
            setattr(self, key, value)
