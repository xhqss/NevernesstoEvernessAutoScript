"""
Spec §4 — Tick Loop.

Fixed 10Hz runtime tick. All core behavior synchronized through this loop.
Screenshot → Vision → OCR → Events → State → Action → Recovery → Metrics.
100ms max budget per tick. Exceed = WARNING, extreme = CRITICAL escalation.
"""

import time
import threading

from module.runtime.event_bus import bus
from module.runtime import RuntimeContext
from module.util.logger import logger


TICK_RATE_HZ = 10
TICK_INTERVAL_MS = 1000 // TICK_RATE_HZ  # 100ms
MAX_TICK_DURATION_MS = 100
MAX_TICK_JITTER_MS = 15


class TickLoop:
    """Fixed-rate runtime tick loop."""

    def __init__(self, ctx: RuntimeContext, hz: int = TICK_RATE_HZ):
        self.ctx = ctx
        self.hz = hz
        self.interval = 1.0 / hz
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_tick_ts = 0.0

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        self.ctx.runtime_start_ts = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True, name='TickLoop')
        self._thread.start()
        bus.emit("RUNTIME_STARTED", {"tick_hz": self.hz})
        logger.info(f'TickLoop started @ {self.hz}Hz')

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        bus.emit("RUNTIME_STOPPED", {"total_ticks": self.ctx.current_tick})
        logger.info('TickLoop stopped')

    def _run(self):
        next_tick = time.perf_counter()
        while self._running:
            tick_start = time.perf_counter()
            self.ctx.current_tick += 1
            self._last_tick_ts = tick_start

            try:
                self._execute_tick()
            except Exception:
                logger.error(f'Tick #{self.ctx.current_tick} unhandled error', exc_info=True)
                bus.emit("TICK_ERROR", {"tick": self.ctx.current_tick})

            # Duration check
            elapsed = (time.perf_counter() - tick_start) * 1000
            if elapsed > MAX_TICK_DURATION_MS:
                bus.emit("TICK_BUDGET_EXCEEDED", {
                    "tick": self.ctx.current_tick,
                    "elapsed_ms": elapsed,
                    "budget_ms": MAX_TICK_DURATION_MS,
                    "level": "CRITICAL" if elapsed > MAX_TICK_DURATION_MS * 2 else "WARNING",
                })
                if elapsed > MAX_TICK_DURATION_MS * 2:
                    logger.warning(f'Tick #{self.ctx.current_tick}: {elapsed:.1f}ms > {MAX_TICK_DURATION_MS}ms budget')

            # Sleep to next tick
            next_tick += self.interval
            sleep_time = next_tick - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # We're behind — skip frames
                jitter = abs(sleep_time) * 1000
                if jitter > MAX_TICK_JITTER_MS:
                    bus.emit("TICK_JITTER", {"tick": self.ctx.current_tick, "jitter_ms": jitter})
                next_tick = time.perf_counter()

    def _execute_tick(self):
        """Single tick: screenshot → detect → OCR → events → state → action → recovery → metrics."""
        bus.emit("TICK_BEGIN", {"tick": self.ctx.current_tick})

        # 1. Screenshot
        bus.emit("TICK_SCREENSHOT", {"tick": self.ctx.current_tick})

        # 2. Vision Detection
        bus.emit("TICK_VISION", {"tick": self.ctx.current_tick})

        # 3. OCR Routing
        bus.emit("TICK_OCR", {"tick": self.ctx.current_tick})

        # 4. Event Generation
        bus.emit("TICK_EVENTS", {"tick": self.ctx.current_tick})

        # 5. State Evaluation
        bus.emit("TICK_STATE_EVAL", {"tick": self.ctx.current_tick})

        # 6. Transition Validation
        bus.emit("TICK_TRANSITION", {"tick": self.ctx.current_tick})

        # 7. Action Scheduling
        bus.emit("TICK_ACTION", {"tick": self.ctx.current_tick})

        # 8. Recovery Evaluation
        bus.emit("TICK_RECOVERY", {"tick": self.ctx.current_tick})

        # 9. Metrics Commit
        bus.emit("TICK_METRICS", {"tick": self.ctx.current_tick})

        bus.emit("TICK_END", {"tick": self.ctx.current_tick, "state": self.ctx.state})
