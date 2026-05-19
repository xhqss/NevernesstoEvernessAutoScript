"""
Spec §20-21 — Watchdog Runtime.

Detects: deadlock, frozen screen, OCR loops, memory leak,
CPU spike, stale state, tick starvation.
"""

import gc
import os
import threading
import time
from collections import deque

from module.runtime.event_bus import bus
from module.runtime import RuntimeContext
from module.util.logger import logger

try:
    import xxhash
    def _hash_frame(frame_bytes: bytes) -> str:
        return xxhash.xxh64(frame_bytes).hexdigest()
except ImportError:
    import hashlib
    def _hash_frame(frame_bytes: bytes) -> str:
        return hashlib.md5(frame_bytes).hexdigest()


FROZEN_SCREEN_THRESHOLD_S = 60
STALE_STATE_THRESHOLD_S = 120
TICK_STARVATION_THRESHOLD_S = 5
MEMORY_GROWTH_THRESHOLD = 0.20  # 20% per hour
CPU_SPIKE_THRESHOLD = 0.90  # 90%
OCR_LOOP_THRESHOLD = 10  # same OCR result 10x = loop

ALERT_COOLDOWN_S = 60  # minimum seconds between same-type alerts


class Watchdog:
    """Multi-metric runtime watchdog."""

    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx
        self._running = False
        self._thread: threading.Thread | None = None

        # Frozen screen
        self._frame_hashes: deque[tuple[float, str]] = deque(maxlen=300)
        self._last_frame_hash: str = ""

        # Stale state
        self._state_change_ts: float = time.time()

        # Tick starvation
        self._last_tick_ts: float = time.time()

        # Memory baseline
        self._baseline_memory: float = 0.0
        self._baseline_ts: float = 0.0

        # OCR loop
        self._ocr_results: deque[str] = deque(maxlen=20)

        # CPU
        self._cpu_samples: deque[float] = deque(maxlen=60)

        self._alert_cooldowns: dict[str, float] = {}

        bus.subscribe("TICK_END", self._on_tick)
        bus.subscribe("STATE_CHANGED", self._on_state_change)
        bus.subscribe("TICK_SCREENSHOT", self._on_screenshot)
        bus.subscribe("TICK_OCR", self._on_ocr)
        bus.subscribe("WATCHDOG_CHECK", lambda e, p: self.check())

    def start(self):
        if self._running:
            return
        self._running = True
        self._baseline_memory = _get_memory_mb()
        self._baseline_ts = time.time()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name='Watchdog')
        self._thread.start()
        logger.info('Watchdog started')

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _on_tick(self, event_type: str, payload: dict):
        self._last_tick_ts = time.time()

    def _on_state_change(self, event_type: str, payload: dict):
        self._state_change_ts = time.time()

    def _on_screenshot(self, event_type: str, payload: dict):
        now = time.time()
        frame = self.ctx.screenshot
        if frame is not None:
            try:
                if hasattr(frame, 'tobytes'):
                    h = _hash_frame(frame.tobytes())
                elif isinstance(frame, bytes):
                    h = _hash_frame(frame)
                else:
                    h = ""
                self._frame_hashes.append((now, h))
                self._last_frame_hash = h
            except Exception:
                pass

    def _on_ocr(self, event_type: str, payload: dict):
        text = payload.get("result", "")
        if text:
            self._ocr_results.append(text)

    def _monitor_loop(self):
        """Background checks every 10s."""
        while self._running:
            time.sleep(10)
            try:
                self.check()
            except Exception:
                logger.error('Watchdog check error', exc_info=True)

    def _can_alert(self, alert_type: str) -> bool:
        now = time.time()
        last = self._alert_cooldowns.get(alert_type, 0)
        if now - last < ALERT_COOLDOWN_S:
            return False
        self._alert_cooldowns[alert_type] = now
        return True

    def check(self):
        now = time.time()

        # Frozen screen
        if self._frame_hashes:
            oldest_ts, oldest_hash = self._frame_hashes[0]
            if now - oldest_ts > FROZEN_SCREEN_THRESHOLD_S:
                all_same = all(h == oldest_hash for _, h in self._frame_hashes)
                if all_same and oldest_hash and self._can_alert("FROZEN_SCREEN"):
                    logger.warning('FROZEN_SCREEN detected')
                    bus.emit("WATCHDOG_ALERT", {
                        "type": "FROZEN_SCREEN",
                        "duration_s": now - oldest_ts,
                    })

        # Tick starvation
        if now - self._last_tick_ts > TICK_STARVATION_THRESHOLD_S:
            if self._can_alert("TICK_STARVATION"):
                logger.warning('TICK_STARVATION detected')
                bus.emit("WATCHDOG_ALERT", {
                    "type": "TICK_STARVATION",
                    "last_tick_age_s": now - self._last_tick_ts,
                })

        # Stale state — only alert when actively RUNNING
        if now - self._state_change_ts > STALE_STATE_THRESHOLD_S:
            if self.ctx.state == "RUNNING" and self._can_alert("STALE_STATE"):
                bus.emit("WATCHDOG_ALERT", {
                    "type": "STALE_STATE",
                    "state": self.ctx.state,
                    "duration_s": now - self._state_change_ts,
                })

        # OCR loop
        if len(self._ocr_results) >= OCR_LOOP_THRESHOLD:
            recent = list(self._ocr_results)[-OCR_LOOP_THRESHOLD:]
            if len(set(recent)) == 1 and recent[0]:
                if self._can_alert("OCR_LOOP"):
                    logger.warning('OCR_LOOP detected')
                    bus.emit("WATCHDOG_ALERT", {
                        "type": "OCR_LOOP",
                        "repeated_result": recent[0],
                    })

        # Memory growth
        if self._baseline_memory > 0:
            current = _get_memory_mb()
            hours = max(0.001, (now - self._baseline_ts) / 3600.0)
            growth_rate = (current - self._baseline_memory) / max(1, self._baseline_memory) / hours
            if growth_rate > MEMORY_GROWTH_THRESHOLD:
                if self._can_alert("MEMORY_GROWTH"):
                    bus.emit("WATCHDOG_ALERT", {
                        "type": "MEMORY_GROWTH",
                        "growth_rate_per_hour": growth_rate,
                        "current_mb": current,
                    })

        # CPU spike
        cpu = _get_cpu_percent()
        if cpu is not None:
            self._cpu_samples.append(cpu)
            if len(self._cpu_samples) >= 3:
                avg = sum(self._cpu_samples) / len(self._cpu_samples)
                if avg > CPU_SPIKE_THRESHOLD:
                    if self._can_alert("CPU_SPIKE"):
                        bus.emit("WATCHDOG_ALERT", {
                            "type": "CPU_SPIKE",
                            "cpu_avg": avg,
                        })

    def stats(self) -> dict:
        return {
            "frozen_screen": bool(self._frame_hashes),
            "last_tick_age_s": time.time() - self._last_tick_ts,
            "state_duration_s": time.time() - self._state_change_ts,
            "current_state": self.ctx.state,
        }


def _get_memory_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0


def _get_cpu_percent() -> float | None:
    try:
        import psutil
        return psutil.Process(os.getpid()).cpu_percent() / 100.0
    except ImportError:
        return None
