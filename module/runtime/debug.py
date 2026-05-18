"""
Spec §3 — Debug Runtime.

Records: tick timeline, event trace, state changes.
Supports dump_json() for offline analysis.
"""

import json
import os
import time
import threading
from collections import deque

from module.runtime.event_bus import bus
from module.runtime.base_module import BaseModule
from module.runtime import RuntimeContext
from module.util.logger import logger


MAX_TIMELINE = 36000  # 1 hour @ 10Hz
MAX_TRACE = 5000
MAX_STATE_LOG = 1000


class DebugRuntime(BaseModule):
    """Tick timeline, event tracer, state recorder for debugging."""

    def __init__(self, ctx: RuntimeContext):
        super().__init__()
        self.ctx = ctx
        self._running = False
        self._lock = threading.Lock()

        # Tick timeline: (tick_number, timestamp, duration_ms, state)
        self._timeline: deque[tuple[int, float, float, str]] = deque(maxlen=MAX_TIMELINE)

        # Event trace: (timestamp, event_type, payload_keys)
        self._trace: deque[tuple[float, str, list[str]]] = deque(maxlen=MAX_TRACE)

        # State change log: (timestamp, old_state, new_state, trigger)
        self._state_log: deque[tuple[float, str, str, str]] = deque(maxlen=MAX_STATE_LOG)

        self._tick_start: float = 0.0

        bus.subscribe("TICK_BEGIN", self._on_tick_begin)
        bus.subscribe("TICK_END", self._on_tick_end)
        bus.subscribe("STATE_CHANGED", self._on_state_change)

        # Subscribe to ALL events for tracing (lightweight, only stores keys)
        self._event_types = set()

    def start(self):
        self._running = True
        logger.info('DebugRuntime started')

    def stop(self):
        self._running = False
        logger.info('DebugRuntime stopped')

    def pause(self):
        pass

    def tick(self):
        pass

    def recover(self) -> bool:
        return True

    def healthcheck(self) -> dict:
        return {
            "timeline_entries": len(self._timeline),
            "trace_entries": len(self._trace),
            "state_log_entries": len(self._state_log),
        }

    def _on_tick_begin(self, event_type: str, payload: dict):
        self._tick_start = time.time()

    def _on_tick_end(self, event_type: str, payload: dict):
        duration_ms = (time.time() - self._tick_start) * 1000
        tick_num = payload.get("tick", 0)
        with self._lock:
            self._timeline.append((tick_num, self._tick_start, duration_ms, self.ctx.state))

    def _on_state_change(self, event_type: str, payload: dict):
        old = payload.get("old", "")
        new = payload.get("new", "")
        trigger = payload.get("trigger", "")
        with self._lock:
            self._state_log.append((time.time(), old, new, trigger))

    def trace_event(self, event_type: str, payload: dict):
        with self._lock:
            self._trace.append((time.time(), event_type, list(payload.keys())[:10]))

    def timeline(self) -> list[tuple[int, float, float, str]]:
        with self._lock:
            return list(self._timeline)

    def state_changes(self) -> list[tuple[float, str, str, str]]:
        with self._lock:
            return list(self._state_log)

    def event_trace(self) -> list[tuple[float, str, list[str]]]:
        with self._lock:
            return list(self._trace)

    def dump_json(self, path: str | None = None) -> str:
        """Serialize debug data to JSON. Writes to file if path given."""
        data = {
            "dump_ts": time.time(),
            "uptime_s": time.time() - self.ctx.runtime_start_ts,
            "total_ticks": self.ctx.current_tick,
            "state": self.ctx.state,
            "timeline": [
                {"tick": t[0], "ts": t[1], "dur_ms": round(t[2], 2), "state": t[3]}
                for t in self._timeline
            ],
            "state_changes": [
                {"ts": s[0], "old": s[1], "new": s[2], "trigger": s[3]}
                for s in self._state_log
            ],
            "event_trace": [
                {"ts": e[0], "type": e[1], "keys": e[2]}
                for e in list(self._trace)[-500:]
            ],
        }
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f'Debug dump written: {path}')
        return json.dumps(data, indent=2, ensure_ascii=False)

    def stats(self) -> dict:
        return self.healthcheck()
