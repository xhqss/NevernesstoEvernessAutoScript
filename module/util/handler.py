"""
Handler with ExitEvent - manages graceful shutdown across threads.
Adapted from ok-script ok/util/handler.py
"""

import threading
import time
from module.util.logger import logger


class ExitEvent:
    """Thread-safe exit event that supports multiple waiters."""

    def __init__(self):
        self._event = threading.Event()

    def set(self):
        self._event.set()

    def is_set(self):
        return self._event.is_set()

    def clear(self):
        self._event.clear()

    def wait(self, timeout=None):
        return self._event.wait(timeout)

    def sleep(self, seconds):
        """Sleep but wake early if exit is set."""
        if seconds <= 0:
            return
        self._event.wait(seconds)


class Handler:
    """Manages exit events and graceful shutdown for task execution."""

    def __init__(self, exit_event, name=''):
        self.exit_event = exit_event or ExitEvent()
        self.name = name
        self._callbacks = []

    @property
    def is_running(self):
        return not self.exit_event.is_set()

    def stop(self):
        logger.info(f'Handler[{self.name}] stop requested')
        self.exit_event.set()
        for cb in self._callbacks:
            try:
                cb()
            except Exception as e:
                logger.error(f'Handler callback error: {e}')

    def on_stop(self, callback):
        """Register callback to be called on stop."""
        self._callbacks.append(callback)

    def sleep(self, seconds):
        """Sleep that can be interrupted by exit event."""
        self.exit_event.sleep(seconds)

    def wait_until(self, condition, timeout=10, interval=0.5):
        """Wait until condition is true or timeout/exit."""
        start = time.time()
        while not self.exit_event.is_set():
            if condition():
                return True
            if time.time() - start > timeout:
                return False
            self.exit_event.sleep(interval)
        return False
