"""Deploy logger - minimal logger that works before dependencies are installed."""

import sys
import time


class Logger:
    def __init__(self):
        self._file = None

    def hr(self, message, level=0):
        if level == 0:
            self.info('=' * 60)
            self.info(message)
            self.info('=' * 60)
        else:
            self.info('-' * 40)
            self.info(message)
            self.info('-' * 40)

    def info(self, message):
        text = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {message}'
        print(text)
        sys.stdout.flush()

    def warning(self, message):
        text = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] WARN: {message}'
        print(text)
        sys.stdout.flush()

    def error(self, message):
        text = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] ERROR: {message}'
        print(text)
        sys.stdout.flush()

    def critical(self, message):
        text = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] CRITICAL: {message}'
        print(text)
        sys.stdout.flush()


logger = Logger()
