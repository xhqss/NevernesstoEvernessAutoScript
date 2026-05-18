"""
GUI signal communication bus.
Central signal bus for inter-component communication.
Adapted from ok-script ok/gui/Communicate.py
"""

from PySide6.QtCore import QObject, Signal


class Communicate(QObject):
    """Central signal bus for GUI communication."""

    # Task execution
    task_started = Signal(str)
    task_stopped = Signal()
    task_paused = Signal()
    task_resumed = Signal()

    # Frame display
    new_frame = Signal(object)  # numpy array
    new_boxes = Signal(object)  # list of Box
    clear_boxes = Signal()

    # Logging
    new_log = Signal(str)  # single line
    log = Signal(int, str)  # (level, message)

    # Status
    new_status = Signal(str)

    # Config
    config_changed = Signal()
    config_saved = Signal()

    # Overlay
    window = Signal(bool, int, int, int, int, int, int, float)

    # App lifecycle
    quit = Signal()

    # Theme
    theme_changed = Signal(str)  # 'dark' | 'light'

    # Instance management
    instance_list_changed = Signal()

    # Debug
    draw_box = Signal(object, str)
    draw_text = Signal(str, int, int)
    clear_overlay = Signal()
    debug_info = Signal(str, object)


communicate = Communicate()
