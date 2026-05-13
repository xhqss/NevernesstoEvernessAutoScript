import time


class Timer:
    """Simple timer with interval checking."""

    def __init__(self, limit=0, count=0):
        self.limit = limit
        self.count = count
        self._start = 0
        self._current = 0

    def start(self):
        self._start = time.time()
        self._current = self._start

    def reached(self):
        """Check if timer has reached its limit."""
        return time.time() - self._start > self.limit

    def wait(self):
        """Wait until timer limit."""
        while not self.reached():
            time.sleep(0.1)

    def reset(self):
        self._start = time.time()
        self._current = self._start

    @property
    def elapsed(self):
        """Elapsed time in seconds."""
        return time.time() - self._start

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        pass


class TimerError(Exception):
    pass
