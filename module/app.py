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
        app_name = self.config.get('gui_title', 'al-script')
        self.app.setApplicationName(app_name)
        self.app.setApplicationVersion(self.config.get('version', '0.1.0'))

        # Set icon
        try:
            icon_path = get_path_relative_to_exe('assets/icon.png')
            if os.path.exists(icon_path):
                self.app.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        # Create main window, passing full config for title/i18n/task info
        from module.gui.main_window import MainWindow
        self.main_window = MainWindow(self.config)
        self.main_window.set_executor(self.task_executor)
        self.main_window.show()

        # Connect signals
        communicate.task_started.connect(self._on_gui_task_started)
        communicate.task_stopped.connect(self._on_gui_task_stopped)
        communicate.task_paused.connect(self._on_gui_task_paused)
        communicate.task_resumed.connect(self._on_gui_task_resumed)
        communicate.quit.connect(self.quit)

        # Auto-start if configured
        if self.config.get('auto_start', False):
            self._start_execution()

        logger.info('GUI started')
        sys.exit(self.app.exec())

    def _on_gui_task_started(self, json_task_name):
        """Handle task start from GUI. json_task_name is the JSON config task key."""
        if json_task_name == 'debug_screenshot':
            if self.device_manager:
                frame = self.device_manager.screenshot()
                if frame is not None:
                    communicate.new_frame.emit(frame)
            return
        self._start_execution(json_task_name)

    def _on_gui_task_stopped(self):
        """Handle task stop from GUI."""
        if self.task_executor:
            self.task_executor.stop()
        communicate.new_status.emit('Stopped')

    def _on_gui_task_paused(self):
        """Handle task pause from GUI."""
        if self.task_executor:
            self.task_executor.pause()

    def _on_gui_task_resumed(self):
        """Handle task resume from GUI."""
        if self.task_executor:
            self.task_executor.resume()

    def _build_task_class_map(self):
        """Build mapping: JSON task name → (module_path, class_name)."""
        mapping = {}
        for task_def in self.config.get('onetime_tasks', []):
            if isinstance(task_def, (list, tuple)) and len(task_def) == 2:
                cls = task_def[1]
                json_name = cls[:-4] if cls.endswith('Task') else cls
                mapping[json_name] = tuple(task_def)
        for task_def in self.config.get('trigger_tasks', []):
            if isinstance(task_def, (list, tuple)) and len(task_def) == 2:
                cls = task_def[1]
                json_name = cls[:-4] if cls.endswith('Task') else cls
                mapping[json_name] = tuple(task_def)
        return mapping

    def _start_execution(self, json_task_name=None):
        """Load and start the specific task (or all if json_task_name is None)."""
        self.load_tasks_from_config(json_task_name)
        if self.task_executor:
            self.task_executor.start()
            communicate.new_status.emit('Running')

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

    def load_tasks_from_config(self, json_task_name=None):
        """Load and register tasks from configuration.

        If json_task_name is provided, only that task is loaded.
        Otherwise all onetime + trigger tasks are loaded.

        Supports two formats:
        - make_config list format: ["module.path", "ClassName"]
        - Dict format: {"module": "module.path", "class": "ClassName", "interval_minutes": 60}
        """
        onetime_tasks = self.config.get('onetime_tasks', [])
        trigger_tasks = self.config.get('trigger_tasks', [])
        scheduled_tasks = self.config.get('scheduled_tasks', [])

        # Build mapping: json_name → (mod, cls)
        task_map = self._build_task_class_map()

        # Filter to single task if requested
        if json_task_name and json_task_name in task_map:
            mod, cls = task_map[json_task_name]
            # Find which list it belongs to and load just that one
            for task_def in onetime_tasks:
                if isinstance(task_def, (list, tuple)) and task_def[1] == cls:
                    self._register_task(task_def, 'onetime')
                    logger.info(f'Loaded single task: {cls}')
                    return
            for task_def in trigger_tasks:
                if isinstance(task_def, (list, tuple)) and task_def[1] == cls:
                    self._register_task(task_def, 'trigger')
                    logger.info(f'Loaded single trigger task: {cls}')
                    return
            # Fallback: load it as one-time
            self._register_task([mod, cls], 'onetime')
            logger.info(f'Loaded single task (fallback): {cls}')
            return

        # No filter → load all
        for task_def in onetime_tasks:
            self._register_task(task_def, 'onetime')

        for task_def in trigger_tasks:
            self._register_task(task_def, 'trigger')

        for task_def in scheduled_tasks:
            self._register_task(task_def, 'scheduled')

    def _register_task(self, task_def, task_type):
        """Register a task from its definition (list or dict format)."""
        try:
            # list format: ["module.path", "ClassName"]
            if isinstance(task_def, (list, tuple)):
                module_name, class_name = task_def[0], task_def[1]
                interval = 60
            # dict format: {"module": "...", "class": "...", "interval_minutes": ...}
            elif isinstance(task_def, dict):
                module_name = task_def.get('module', '')
                class_name = task_def.get('class', '')
                interval = task_def.get('interval_minutes', 60)
            else:
                logger.error(f'Unknown task definition format: {task_def}')
                return

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
                # Inject feature_set
                if hasattr(task, 'feature_set') and self.feature_set:
                    task.feature_set = self.feature_set

                if task_type == 'onetime':
                    self.task_executor.add_task(task)
                elif task_type == 'trigger':
                    self.task_executor.add_trigger_task(task)
                elif task_type == 'scheduled':
                    self.task_executor.add_scheduled_task(task, interval)

                logger.info(f'Registered {task_type} task: {class_name}')
        except Exception as e:
            logger.error(f'Failed to register task {task_def}: {e}')
            import traceback
            traceback.print_exc()

    @property
    def frame(self):
        """Get the current frame from device manager."""
        if self.device_manager:
            return self.device_manager._last_screenshot
        return None
