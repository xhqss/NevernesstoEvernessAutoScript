"""
Log handler that emits log messages to the GUI.
"""

import logging
from module.gui.communicate import communicate


class GuiLogHandler(logging.Handler):
    """Log handler that sends messages to GUI via signals."""
    
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.setFormatter(logging.Formatter(
            '%(asctime)s.%(msecs)03d | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
    
    def emit(self, record):
        try:
            msg = self.format(record)
            communicate.new_log.emit(msg)
        except Exception:
            self.handleError(record)
