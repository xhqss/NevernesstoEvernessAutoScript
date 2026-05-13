"""
al-script App - main application class.
Initializes all subsystems and manages application lifecycle.
Adapted from ok-script ok/__init__.py OK class.
"""

import os
import sys
import threading
import time

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon

from module.util.logger import logger, config_logger
from module.util.file import get_path_relative_to_exe, install_path_isascii
from module.util.process import check_mutex, get_first_gpu_free_memory_mib
from module.util.handler import Handler, ExitEvent
from module.device.device_manager import DeviceManager, TARGET_WIDTH, TARGET_HEIGHT
from module.feature.feature_set import FeatureSet
from module.task.executor import TaskExecutor
from module.gui.communicate import communicate

# Try to import pyappify
try:
    import pyappify
    HAS_PYAPPIFY = True
except ImportError:
    HAS_PYAPPIFY = False


class App:
    """
    Main application class for al-script.

    Initializes all subsystems:
    - DeviceManager (capture + interaction)
    - FeatureSet (template management)
    - TaskExecutor (task execution engine)
    - GUI (PySide6 main window)

    Usage:
        app = App(config={'use_gui': True})
        app.start()
    """

    def __init__(self, config=None):
        self.config = config or {}
        self._apply_defaults()

        self.exit_event = ExitEvent()
        self.handler = Handler(self.exit_event, 'app')
        self.device_manager = None
        self.feature_set = None
        self.task_executor = None
        self.overlay_window = None
        self.main_window = None
        self.app = None

        logger.info(f'al-script v{self.config.get("version", "0.1.0")}')
        logger.info(f'Config: {self.config.get("config_name", "template")}')

        self._init()

    def _apply_defaults(self):
        """Apply default configuration values."""
        self.config.setdefault('version', '0.1.0')
        self.config.setdefault('config_name', 'template')
        self.config.setdefault('config_folder', 'config')
        self.config.setdefault('debug', False)
        self.config.setdefault('use_gui', True)
        self.config.setdefault('window_size', {
            'width': 1400,
            'height': 900,
            'min_width': 800,
            'min_height': 600,
        })

    def _init(self):
        """Initialize all subsystems."""
        # Check for mutex (single instance)
        if self.config.get('check_mutex', True):
            if not check_mutex('al-script-mutex'):
                logger.warning('Another instance may be running')

        # Initialize DeviceManager
        self._init_device_manager()

        # Initialize FeatureSet
        self._init_feature_set()

        # Initialize TaskExecutor
        self._init_task_executor()

    def _init_device_manager(self):
        """Initialize the device manager."""
        self.device_manager = DeviceManager(
            config=self.config,
            exit_event=self.exit_event,
            global_config=self.config.get('global_config')
        )
        logger.info(f'DeviceManager initialized: {self.device_manager}')

    def _init_feature_set(self):
        """Initialize the feature set."""
        tm_config = self.config.get('template_matching', {})
        self.feature_set = FeatureSet(
            assets_dir=self.config.get('assets_dir', './assets'),
            debug=self.config.get('debug', False),
            default_threshold=tm_config.get('default_threshold', 0.85),
            feature_processor=tm_config.get('feature_processor')
        )
        logger.info(f'FeatureSet initialized')

    def _init_task_executor(self):
        """Initialize the task executor."""
        self.task_executor = TaskExecutor(
            device_manager=self.device_manager,
            config=self.config,
            exit_event=self.exit_event,
            feature_set=self.feature_set,
            global_config=self.config.get('global_config'),
            debug=self.config.get('debug', False)
        )
        logger.info('TaskExecutor initialized')

    def start(self):
        """Start the application (GUI or CLI mode)."""
        if self.config.get('use_gui'):
            self._start_gui()
        else:
            self._start_cli()

    def _start_gui(self):
        """Start in GUI mode."""
        from PySide6.QtWidgets import QApplication

        self.app = QApplication(sys.argv)
        self.app.setApplicationName('al-script')
        self.app.setApplicationVersion(self.config.get('version', '0.1.0'))

        # Set icon
        try:
            icon_path = get_path_relative_to_exe('assets/icon.png')
            if os.path.exists(icon_path):
                self.app.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        # Create main window
        from module.gui.main_window import MainWindow
        self.main_window = MainWindow(self.config.get('config_name', 'template'))
        self.main_window.set_executor(self.task_executor)
        self.main_window.show()

        # Connect signals
        communicate.task_started.connect(self._on_gui_task_started)
        communicate.task_stopped.connect(self._on_gui_task_stopped)
        communicate.quit.connect(self.quit)

        logger.info('GUI started')
        sys.exit(self.app.exec())

    def _on_gui_task_started(self, config_name):
        """Handle task start from GUI."""
        if config_name == 'debug_screenshot':
            if self.device_manager:
                frame = self.device_manager.screenshot()
                if frame is not None:
                    communicate.new_frame.emit(frame)

    def _on_gui_task_stopped(self):
        """Handle task stop from GUI."""
        if self.task_executor:
            self.task_executor.stop()

    def _start_cli(self):
        """Start in CLI mode (headless)."""
        logger.info('Starting in CLI mode')
        self.task_executor.start()

        try:
            while not self.exit_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info('Keyboard interrupt received')
        finally:
            self.stop()

    def stop(self):
        """Stop the application."""
        logger.info('Stopping application...')
        self.exit_event.set()

        if self.task_executor:
            self.task_executor.stop()

        if self.app:
            from PySide6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(self.app, "quit", Qt.QueuedConnection)

    def quit(self):
        """Quit the application."""
        self.stop()

    def load_tasks_from_config(self):
        """Load and register tasks from configuration."""
        config_data = self.config.get('tasks', {})
        onetime_tasks = config_data.get('onetime_tasks', [])
        trigger_tasks = config_data.get('trigger_tasks', [])
        scheduled_tasks = config_data.get('scheduled_tasks', [])

        for task_def in onetime_tasks:
            self._register_task(task_def, 'onetime')

        for task_def in trigger_tasks:
            self._register_task(task_def, 'trigger')

        for task_def in scheduled_tasks:
            self._register_task(task_def, 'scheduled')

    def _register_task(self, task_def, task_type):
        """Register a task from its definition."""
        try:
            module_name = task_def.get('module', '')
            class_name = task_def.get('class', '')
            interval = task_def.get('interval_minutes', 60)

            if module_name and class_name:
                import importlib
                mod = importlib.import_module(module_name)
                task_cls = getattr(mod, class_name)
                task = task_cls(
                    config=self.config,
                    device_manager=self.device_manager,
                    exit_event=self.exit_event,
                    handler=self.handler
                )

                if task_type == 'onetime':
                    self.task_executor.add_task(task)
                elif task_type == 'trigger':
                    self.task_executor.add_trigger_task(task)
                elif task_type == 'scheduled':
                    self.task_executor.add_scheduled_task(task, interval)

                logger.info(f'Registered {task_type} task: {class_name}')
        except Exception as e:
            logger.error(f'Failed to register task {task_def}: {e}')

    @property
    def frame(self):
        """Get the current frame from device manager."""
        if self.device_manager:
            return self.device_manager._last_screenshot
        return None
