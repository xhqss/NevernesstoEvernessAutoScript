"""

Logger module - adapted from Alas module/logger.py.

Provides structured logging with hierarchy support.

"""



import os

import sys

import logging

from datetime import datetime





# Log format

LOG_FORMAT = '%(asctime)s.%(msecs)03d | %(levelname)s | %(message)s'

LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'



# Color codes for console output

LEVEL_COLORS = {

    'DEBUG': '\033[37m',     # White

    'INFO': '\033[32m',      # Green

    'WARNING': '\033[33m',   # Yellow

    'ERROR': '\033[31m',     # Red

    'CRITICAL': '\033[41m',  # Red background

}

RESET_COLOR = '\033[0m'





class ColoredFormatter(logging.Formatter):

    """Formatter with console colors."""

    

    def format(self, record):

        level_name = record.levelname

        color = LEVEL_COLORS.get(level_name, '')

        if color and sys.stderr.isatty():

            record.levelname = f'{color}{level_name}{RESET_COLOR}'

        return super().format(record)





def _get_log_path():

    """Get log file path."""

    log_dir = './log'

    os.makedirs(log_dir, exist_ok=True)

    log_file = f'al_{datetime.now().strftime("%Y%m%d")}.txt'

    return os.path.join(log_dir, log_file)





def config_logger(logger=None, level=logging.INFO):

    """Configure logger with console and file handlers."""

    if logger is None:

        logger = logging.getLogger()

    

    logger.setLevel(level)

    

    # Console handler with colors

    console_handler = logging.StreamHandler(sys.stdout)

    console_handler.setLevel(level)

    console_formatter = ColoredFormatter(

        LOG_FORMAT, datefmt=LOG_DATE_FORMAT

    )

    console_handler.setFormatter(console_formatter)

    logger.addHandler(console_handler)

    

    # File handler

    try:

        file_handler = logging.FileHandler(_get_log_path(), encoding='utf-8')

        file_handler.setLevel(level)

        file_formatter = logging.Formatter(

            LOG_FORMAT, datefmt=LOG_DATE_FORMAT

        )

        file_handler.setFormatter(file_formatter)

        logger.addHandler(file_handler)

    except Exception:

        pass





class Logger:

    """Logger utility class."""

    

    @staticmethod

    def get_logger(name=None):

        """Get or create a logger instance."""

        if name:

            return logging.getLogger(name)

        return logging.getLogger()

    

    @staticmethod

    @staticmethod
    def hr(title, level=0):
        """Print a horizontal rule with title."""
        logger = logging.getLogger()
        if level == 0:
            logger.info(f'[--- {title} ---]')
        elif level == 1:
            logger.info(f'==== {title} ====')
        elif level == 2:
            logger.info(f'---- {title} ----')
        elif level == 3:
            logger.info(f'<<< {title} >>>')

            logger.info(f'<<< {title} >>>')

    

    @staticmethod

    def attr(name, text):

        """Print attribute: [name] text."""

        logger = logging.getLogger()

        logger.info(f'[{name}] {text}')

    

    @staticmethod

    def attr_align(name, text, align=20):

        """Print aligned attribute."""

        logger = logging.getLogger()

        logger.info(f'[{name:<{align}}] {text}')





# Initialize default logger

config_logger()

logger = logging.getLogger('al')

