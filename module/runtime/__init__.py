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


# Re-export complete runtime topology (§3)
from module.runtime.base_module import BaseModule
from module.runtime.lifecycle import ModuleLifecycle, ModuleState
from module.runtime.event_bus import EventBus, bus
from module.runtime.tick_loop import TickLoop
from module.runtime.state_machine import StateMachine, Transition
from module.runtime.recovery import RecoveryRuntime, RECOVERY_CHAIN
from module.runtime.watchdog import Watchdog
from module.runtime.metrics import MetricsRuntime
from module.runtime.manager import RuntimeManager
from module.runtime.security import SecurityRuntime, AESGCM, encryptor, desensitize
from module.runtime.error_codes import (
    SpecError,
    get_error, error_category, all_codes,
    DEVICE_ERRORS, OCR_ERRORS, RUNTIME_ERRORS, RECOVERY_ERRORS, SCHEDULER_ERRORS,
)
from module.runtime.sandbox import PluginSandbox, PluginPermissions, PluginRegistry
from module.runtime.resource import ResourceRuntime
from module.runtime.update import UpdateRuntime
from module.runtime.debug import DebugRuntime
from module.runtime.instances import InstanceManager, InstanceContext

__all__ = [
    # Core
    "RuntimeContext",
    "BaseModule",
    "ModuleLifecycle",
    "ModuleState",
    # Communication
    "EventBus",
    "bus",
    # Timing
    "TickLoop",
    # State
    "StateMachine",
    "Transition",
    # Recovery
    "RecoveryRuntime",
    "RECOVERY_CHAIN",
    # Monitoring
    "Watchdog",
    "MetricsRuntime",
    # Orchestration
    "RuntimeManager",
    # Security
    "SecurityRuntime",
    "AESGCM",
    "encryptor",
    "desensitize",
    # Errors
    "SpecError",
    "get_error",
    "error_category",
    "all_codes",
    "DEVICE_ERRORS",
    "OCR_ERRORS",
    "RUNTIME_ERRORS",
    "RECOVERY_ERRORS",
    "SCHEDULER_ERRORS",
    # Sandbox
    "PluginSandbox",
    "PluginPermissions",
    "PluginRegistry",
    # Resources & Operations
    "ResourceRuntime",
    "UpdateRuntime",
    "DebugRuntime",
    # Multi-instance
    "InstanceManager",
    "InstanceContext",
]
