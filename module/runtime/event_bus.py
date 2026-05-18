"""
Spec §5, §22 — EventBus.

Modules communicate ONLY through EventBus + typed payloads.
Features: async/sync listeners, priority, event tracing, replay.
"""

import threading
import time
import traceback
from collections import defaultdict
from typing import Any, Callable

from module.util.logger import logger


Listener = Callable[[str, dict], None]


class EventBus:
    """Central event bus for all runtime communication."""

    def __init__(self, trace: bool = False):
        self._lock = threading.Lock()
        # event_type -> [(priority, listener, is_async)]
        self._listeners: dict[str, list[tuple[int, Listener, bool]]] = defaultdict(list)
        self._trace_enabled = trace
        self._trace_log: list[tuple[float, str, dict]] = []
        self._event_count: dict[str, int] = defaultdict(int)

    def subscribe(self, event_type: str, listener: Listener,
                  priority: int = 0, async_: bool = False):
        """Register a listener. Higher priority = called first."""
        with self._lock:
            self._listeners[event_type].append((priority, listener, async_))
            self._listeners[event_type].sort(key=lambda x: -x[0])

    def unsubscribe(self, event_type: str, listener: Listener):
        """Remove a listener."""
        with self._lock:
            self._listeners[event_type] = [
                (p, l, a) for p, l, a in self._listeners[event_type]
                if l is not listener
            ]

    def emit(self, event_type: str, payload: dict | None = None):
        """Emit an event to all registered listeners.

        Sync listeners run in caller thread.
        Async listeners run in daemon threads.
        """
        payload = payload or {}
        self._event_count[event_type] += 1

        if self._trace_enabled:
            self._trace_log.append((time.time(), event_type, dict(payload)))

        with self._lock:
            listeners = list(self._listeners[event_type])

        for priority, listener, is_async in listeners:
            try:
                if is_async:
                    t = threading.Thread(
                        target=_safe_call,
                        args=(listener, event_type, payload),
                        daemon=True,
                        name=f'eb-{event_type}'
                    )
                    t.start()
                else:
                    _safe_call(listener, event_type, payload)
            except Exception:
                pass

    def emit_sync(self, event_type: str, payload: dict | None = None):
        """Emit event — wait for all async listeners to finish."""
        payload = payload or {}
        self._event_count[event_type] += 1

        if self._trace_enabled:
            self._trace_log.append((time.time(), event_type, dict(payload)))

        with self._lock:
            listeners = list(self._listeners[event_type])

        threads = []
        for priority, listener, is_async in listeners:
            try:
                if is_async:
                    t = threading.Thread(
                        target=_safe_call,
                        args=(listener, event_type, payload),
                        daemon=True
                    )
                    t.start()
                    threads.append(t)
                else:
                    _safe_call(listener, event_type, payload)
            except Exception:
                pass

        for t in threads:
            t.join(timeout=5)

    # ---- tracing ----

    def enable_tracing(self):
        self._trace_enabled = True

    def disable_tracing(self):
        self._trace_enabled = False

    def trace_entries(self) -> list[tuple[float, str, dict]]:
        return list(self._trace_log)

    def replay(self, target_bus: "EventBus"):
        """Replay recorded events onto another bus."""
        for ts, event_type, payload in self._trace_log:
            target_bus.emit(event_type, payload)

    # ---- stats ----

    def stats(self) -> dict:
        return {
            "listener_count": sum(len(v) for v in self._listeners.values()),
            "event_types": len(self._listeners),
            "event_count": dict(self._event_count),
        }


def _safe_call(listener: Callable, event_type: str, payload: dict):
    try:
        listener(event_type, payload)
    except Exception:
        logger.error(f'EventBus listener error [{event_type}]:\n{traceback.format_exc()}')


# Global singleton
bus = EventBus(trace=False)
