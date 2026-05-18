"""
Spec §14-16 — State Machine Runtime.

Explicit state transitions only. No implicit transitions allowed.
Each Transition: source, target, trigger, guard, action, timeout_ms.
"""

import time
import threading
from typing import Any, Callable

from module.runtime.event_bus import bus
from module.runtime import RuntimeContext
from module.util.logger import logger


class Transition:
    """Spec §15 — explicit state transition."""

    __slots__ = ('source', 'target', 'trigger', 'guard', 'action', 'timeout_ms')

    def __init__(self, *, source: str, target: str, trigger: str,
                 guard: Callable[[], bool] | None = None,
                 action: Callable[[], Any] | None = None,
                 timeout_ms: int = 5000):
        self.source = source
        self.target = target
        self.trigger = trigger
        self.guard = guard or (lambda: True)
        self.action = action or (lambda: None)
        self.timeout_ms = timeout_ms

    def __repr__(self):
        return f'Transition({self.source} → {self.target}, trigger={self.trigger})'


class StateMachine:
    """Spec §14 — deterministic state machine."""

    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx
        self._transitions: dict[tuple[str, str], Transition] = {}
        self._lock = threading.Lock()
        self._transition_history: list[tuple[float, str, str, str]] = []

        bus.subscribe("TRANSITION_REQUEST", self._on_transition_request)

    def register(self, t: Transition):
        with self._lock:
            self._transitions[(t.source, t.trigger)] = t

    def unregister(self, source: str, trigger: str):
        with self._lock:
            self._transitions.pop((source, trigger), None)

    def transition(self, trigger: str) -> bool:
        """Attempt a transition by trigger name from current state."""
        current = self.ctx.state
        key = (current, trigger)
        with self._lock:
            t = self._transitions.get(key)

        if t is None:
            logger.warning(f'No transition: ({current}, {trigger})')
            bus.emit("TRANSITION_INVALID", {"source": current, "trigger": trigger})
            return False

        if not t.guard():
            logger.info(f'Transition guard rejected: {t}')
            bus.emit("TRANSITION_GUARD_FAILED", {"transition": str(t)})
            return False

        # Execute action with timeout
        result = None
        try:
            result = _run_with_timeout(t.action, t.timeout_ms / 1000.0)
        except TimeoutError:
            logger.error(f'Transition action timeout: {t} ({t.timeout_ms}ms)')
            bus.emit("TRANSITION_TIMEOUT", {"transition": str(t), "timeout_ms": t.timeout_ms})
            return False
        except Exception:
            logger.error(f'Transition action error: {t}', exc_info=True)
            bus.emit("TRANSITION_ERROR", {"transition": str(t)})
            return False

        old_state = self.ctx.state
        self.ctx.state = t.target
        self._transition_history.append((time.time(), old_state, trigger, t.target))
        bus.emit("STATE_CHANGED", {"old": old_state, "new": t.target, "trigger": trigger})
        logger.info(f'State: {old_state} → {t.target} [{trigger}]')
        return True

    def _on_transition_request(self, event_type: str, payload: dict):
        trigger = payload.get("trigger", "")
        if trigger:
            self.transition(trigger)

    @property
    def state(self) -> str:
        return self.ctx.state

    @property
    def history(self) -> list[tuple[float, str, str, str]]:
        return list(self._transition_history)

    def can(self, trigger: str) -> bool:
        """Check if a trigger is valid from current state."""
        with self._lock:
            return (self.ctx.state, trigger) in self._transitions

    def available_triggers(self) -> list[str]:
        with self._lock:
            return [
                trigger for (src, trigger), t in self._transitions.items()
                if src == self.ctx.state and t.guard()
            ]


def _run_with_timeout(fn: Callable, timeout_s: float) -> Any:
    result_container: list[Any] = []
    error_container: list[Exception] = []

    def wrapper():
        try:
            result_container.append(fn())
        except Exception as e:
            error_container.append(e)

    t = threading.Thread(target=wrapper, daemon=True)
    t.start()
    t.join(timeout=timeout_s)
    if t.is_alive():
        raise TimeoutError(f'Action timed out after {timeout_s}s')
    if error_container:
        raise error_container[0]
    return result_container[0] if result_container else None
