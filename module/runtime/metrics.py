"""
Spec §29-30 — Metrics Runtime.

Mandatory metrics collected and emitted via EventBus.
Performance targets tracked: screenshot <80ms, OCR fast <50ms,
OCR full <300ms, tick <100ms, memory growth <5%/h, recovery success >90%.
"""

import os
import threading
import time
from collections import defaultdict

from module.runtime.event_bus import bus
from module.runtime import RuntimeContext
from module.util.logger import logger


class MetricsRuntime:
    """Collects and reports runtime performance metrics."""

    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx
        self._lock = threading.Lock()

        # Latency accumulators
        self._tick_durations: list[float] = []
        self._ocr_latencies: list[float] = []
        self._screenshot_latencies: list[float] = []
        self._device_latencies: list[float] = []

        # Counters
        self._recovery_total = 0
        self._recovery_success = 0
        self._state_transitions = 0
        self._errors: dict[str, int] = defaultdict(int)

        # Baseline
        self._start_ts = time.time()
        self._baseline_memory = _memory_mb()
        self._last_report_ts = self._start_ts

        # Subscribe to tick pipeline events
        bus.subscribe("TICK_BEGIN", self._on_tick_begin)
        bus.subscribe("TICK_END", self._on_tick_end)
        bus.subscribe("TICK_OCR", self._on_ocr)
        bus.subscribe("TICK_SCREENSHOT", self._on_screenshot)
        bus.subscribe("STATE_CHANGED", self._on_state_change)
        bus.subscribe("RECOVERY_COMPLETED", self._on_recovery_complete)
        bus.subscribe("RECOVERY_FAILED", self._on_recovery_fail)
        bus.subscribe("TICK_ERROR", self._on_error)
        bus.subscribe("METRICS_REPORT", lambda e, p: self.report())

        self._tick_start_ts: float = 0.0

    def _on_tick_begin(self, event_type: str, payload: dict):
        self._tick_start_ts = time.time()

    def _on_tick_end(self, event_type: str, payload: dict):
        if self._tick_start_ts:
            duration_ms = (time.time() - self._tick_start_ts) * 1000
            with self._lock:
                self._tick_durations.append(duration_ms)
                # Keep last 600 ticks (60s @ 10Hz)
                if len(self._tick_durations) > 600:
                    self._tick_durations = self._tick_durations[-600:]
            self.ctx.metrics['tick_duration_ms'] = duration_ms

    def _on_ocr(self, event_type: str, payload: dict):
        latency = payload.get("latency_ms", 0)
        if latency:
            with self._lock:
                self._ocr_latencies.append(latency)
                if len(self._ocr_latencies) > 600:
                    self._ocr_latencies = self._ocr_latencies[-600:]

    def _on_screenshot(self, event_type: str, payload: dict):
        latency = payload.get("latency_ms", 0)
        if latency:
            with self._lock:
                self._screenshot_latencies.append(latency)
                if len(self._screenshot_latencies) > 600:
                    self._screenshot_latencies = self._screenshot_latencies[-600:]

    def _on_state_change(self, event_type: str, payload: dict):
        with self._lock:
            self._state_transitions += 1
        self.ctx.metrics['state_transition_rate'] = (
            self._state_transitions / max(1, time.time() - self._start_ts)
        )

    def _on_recovery_complete(self, event_type: str, payload: dict):
        with self._lock:
            self._recovery_total += 1
            self._recovery_success += 1

    def _on_recovery_fail(self, event_type: str, payload: dict):
        with self._lock:
            self._recovery_total += 1

    def _on_error(self, event_type: str, payload: dict):
        code = payload.get("code", "UNKNOWN")
        with self._lock:
            self._errors[code] += 1

    # ---- computed metrics ----

    def tick_duration_avg_ms(self) -> float:
        with self._lock:
            if not self._tick_durations:
                return 0
            return sum(self._tick_durations) / len(self._tick_durations)

    def ocr_latency_avg_ms(self) -> float:
        with self._lock:
            if not self._ocr_latencies:
                return 0
            return sum(self._ocr_latencies) / len(self._ocr_latencies)

    def screenshot_latency_avg_ms(self) -> float:
        with self._lock:
            if not self._screenshot_latencies:
                return 0
            return sum(self._screenshot_latencies) / len(self._screenshot_latencies)

    def recovery_rate(self) -> float:
        with self._lock:
            if self._recovery_total == 0:
                return 1.0
            return self._recovery_success / self._recovery_total

    def memory_growth_per_hour(self) -> float:
        hours = max(0.001, (time.time() - self._start_ts) / 3600)
        current = _memory_mb()
        return (current - self._baseline_memory) / max(1, self._baseline_memory) / hours

    def cpu_usage(self) -> float:
        try:
            import psutil
            return psutil.Process(os.getpid()).cpu_percent() / 100.0
        except ImportError:
            return 0.0

    # ---- report ----

    def snapshot(self) -> dict:
        return {
            "tick_duration_ms": self.tick_duration_avg_ms(),
            "ocr_latency_ms": self.ocr_latency_avg_ms(),
            "screenshot_latency_ms": self.screenshot_latency_avg_ms(),
            "device_latency_ms": sum(self._device_latencies) / max(1, len(self._device_latencies)),
            "recovery_rate": self.recovery_rate(),
            "state_transitions": self._state_transitions,
            "cpu_usage": self.cpu_usage(),
            "memory_mb": _memory_mb(),
            "memory_growth_per_hour": self.memory_growth_per_hour(),
            "error_count": dict(self._errors),
            "uptime_s": time.time() - self._start_ts,
        }

    def report(self) -> dict:
        """Emit a metrics report and return snapshot."""
        s = self.snapshot()
        bus.emit("METRICS_SNAPSHOT", s)
        logger.info(
            f'Metrics | tick={s["tick_duration_ms"]:.1f}ms '
            f'ocr={s["ocr_latency_ms"]:.1f}ms '
            f'screenshot={s["screenshot_latency_ms"]:.1f}ms '
            f'recovery_rate={s["recovery_rate"]:.1%} '
            f'mem={s["memory_mb"]:.0f}MB'
        )
        self._last_report_ts = time.time()
        return s

    # ---- perf target checks ----

    def check_targets(self) -> list[str]:
        """Check against spec §30 targets. Returns list of violations."""
        violations = []
        s = self.snapshot()
        if s["tick_duration_ms"] > 100:
            violations.append(f'tick {s["tick_duration_ms"]:.0f}ms > 100ms')
        if s["ocr_latency_ms"] > 300:
            violations.append(f'OCR {s["ocr_latency_ms"]:.0f}ms > 300ms')
        if s["screenshot_latency_ms"] > 80:
            violations.append(f'screenshot {s["screenshot_latency_ms"]:.0f}ms > 80ms')
        if s["memory_growth_per_hour"] > 0.05:
            violations.append(f'memory growth {s["memory_growth_per_hour"]:.1%} > 5%/h')
        if s["recovery_rate"] < 0.9 and s["recovery_rate"] > 0:
            violations.append(f'recovery rate {s["recovery_rate"]:.1%} < 90%')
        return violations


def _memory_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0
