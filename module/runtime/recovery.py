"""
Spec §17-19 — Recovery Runtime.

L1-L9 escalating recovery chain with dynamic weight adaptation.
Failed recovery → weight decay. Successful recovery → weight increase.
"""

import time
import threading
from collections import defaultdict

from module.runtime.event_bus import bus
from module.runtime import RuntimeContext
from module.util.logger import logger


# Spec §18 — Recovery escalation chain
RECOVERY_CHAIN = [
    "L1_RETRY",
    "L2_REFOCUS_WINDOW",
    "L3_REDETECT",
    "L4_INJECT_ESC",
    "L5_RECONNECT_DEVICE",
    "L6_RESTART_MODULE",
    "L7_RESTART_GAME",
    "L8_RESTART_EMULATOR",
    "L9_RESTART_RUNTIME",
]

# Spec §19 — initial recovery weights
INITIAL_WEIGHTS: dict[str, float] = {
    "L1_RETRY": 0.9,
    "L2_REFOCUS_WINDOW": 0.8,
    "L3_REDETECT": 0.8,
    "L4_INJECT_ESC": 0.5,
    "L5_RECONNECT_DEVICE": 0.4,
    "L6_RESTART_MODULE": 0.3,
    "L7_RESTART_GAME": 0.2,
    "L8_RESTART_EMULATOR": 0.15,
    "L9_RESTART_RUNTIME": 0.1,
}

WEIGHT_ADAPT_RATE = 0.2
OLD_WEIGHT_RATE = 0.8


RecoveryHandler = type(object)  # placeholder; actual handlers are callables


class RecoveryRuntime:
    """Progressive escalation recovery engine."""

    MAX_TOTAL_ATTEMPTS = 50
    LEVEL_COOLDOWN_S = 10

    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx
        self._weights: dict[str, float] = dict(INITIAL_WEIGHTS)
        self._handlers: dict[str, list[RecoveryHandler]] = defaultdict(list)
        self._success: dict[str, int] = defaultdict(int)
        self._failure: dict[str, int] = defaultdict(int)
        self._current_attempts: dict[str, int] = defaultdict(int)
        self._total_attempts: int = 0
        self._lock = threading.Lock()
        self._cooldown: dict[str, float] = {}
        self._max_attempts = {level: 3 + i for i, level in enumerate(RECOVERY_CHAIN)}

        bus.subscribe("RECOVERY_TRIGGER", self._on_recovery_trigger)
        bus.subscribe("RECOVERY_SUCCESS", self._on_recovery_success)
        bus.subscribe("RECOVERY_FAILED", self._on_recovery_failed)

    def register_handler(self, level: str, handler: callable):
        """Register a recovery action for a given escalation level."""
        if level not in RECOVERY_CHAIN:
            raise ValueError(f'Unknown recovery level: {level}')
        self._handlers[level].append(handler)

    def trigger(self, reason: str, level: str = "L1_RETRY"):
        """Initiate recovery for a given reason."""
        if level not in RECOVERY_CHAIN:
            level = "L1_RETRY"

        with self._lock:
            # Global max attempts check
            if self._total_attempts >= self.MAX_TOTAL_ATTEMPTS:
                return
            self._total_attempts += 1

            # Cooldown check
            now = time.time()
            if level in self._cooldown and now - self._cooldown[level] < self.LEVEL_COOLDOWN_S:
                return
            self._cooldown[level] = now
            self._current_attempts[level] += 1

        logger.info(f'Recovery triggered: {reason} → {level} '
                     f'(attempt {self._current_attempts[level]})')
        bus.emit("RECOVERY_STARTED", {"reason": reason, "level": level})

        success = False
        for handler in self._handlers.get(level, []):
            try:
                result = handler()
                if result:
                    success = True
                    break
            except Exception:
                logger.error(f'Recovery handler error [{level}]', exc_info=True)

        if success:
            self._on_recovery_success("RECOVERY_SUCCESS", {"level": level})
        else:
            self._on_recovery_failed("RECOVERY_FAILED", {"level": level, "reason": reason})

    def _on_recovery_trigger(self, event_type: str, payload: dict):
        reason = payload.get("reason", "unknown")
        level = payload.get("level", "L1_RETRY")
        self.trigger(reason, level)

    def _on_recovery_success(self, event_type: str, payload: dict):
        level = payload.get("level", "L1_RETRY")
        with self._lock:
            self._success[level] += 1
            self._current_attempts[level] = 0
            # Spec §19: weight increase on success
            success_rate = self._success[level] / max(1, self._success[level] + self._failure[level])
            self._weights[level] = (self._weights[level] * OLD_WEIGHT_RATE
                                     + success_rate * WEIGHT_ADAPT_RATE)
        bus.emit("RECOVERY_COMPLETED", {"level": level, "result": "success"})

    def _on_recovery_failed(self, event_type: str, payload: dict):
        level = payload.get("level", "L1_RETRY")
        reason = payload.get("reason", "unknown")

        with self._lock:
            self._failure[level] += 1
            # Spec §19: weight decay on failure
            self._weights[level] *= OLD_WEIGHT_RATE

        # Escalate if max attempts exceeded
        max_attempts = self._max_attempts.get(level, 3)
        if self._current_attempts[level] >= max_attempts:
            next_level = self._next_level(level)
            if next_level:
                logger.warning(f'Recovery escalation: {level} → {next_level} after {max_attempts} attempts')
                bus.emit("RECOVERY_ESCALATE", {
                    "from_level": level, "to_level": next_level, "reason": reason,
                })
                self.trigger(reason, next_level)
        else:
            # Retry same level
            bus.emit("RECOVERY_RETRY", {"level": level, "attempt": self._current_attempts[level]})

    def _next_level(self, current: str) -> str | None:
        try:
            idx = RECOVERY_CHAIN.index(current)
            if idx + 1 < len(RECOVERY_CHAIN):
                return RECOVERY_CHAIN[idx + 1]
        except ValueError:
            pass
        return None

    def get_weight(self, level: str) -> float:
        return self._weights.get(level, 0.0)

    def stats(self) -> dict:
        return {
            "weights": dict(self._weights),
            "successes": dict(self._success),
            "failures": dict(self._failure),
            "attempts": dict(self._current_attempts),
        }

    @property
    def success_rate(self) -> float:
        total_s = sum(self._success.values())
        total_f = sum(self._failure.values())
        if total_s + total_f == 0:
            return 1.0
        return total_s / (total_s + total_f)
