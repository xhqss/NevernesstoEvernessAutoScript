"""
Task executor - main execution engine.
Runs tasks with screenshot capture, trigger checking, and lifecycle management.
"""

import threading
import time

from module.util.logger import logger
from module.util.handler import Handler, ExitEvent
from module.task.exceptions import TaskError, FinishedError, TaskDisabledError


class TaskExecutor:
    """
    Main task execution engine.

    - Manages task lifecycle (start, pause, resume, stop)
    - Supports one-time tasks, trigger tasks, and scheduled tasks
    - Thread-based execution
    - Integrates with DeviceManager for capture/input
    """

    def __init__(self, device_manager=None, config=None, exit_event=None,
                 feature_set=None, global_config=None, debug=False):
        self.device_manager = device_manager
        self.config = config or {}
        self.global_config = global_config
        self.feature_set = feature_set
        self.debug = debug

        self._exit_event = exit_event or ExitEvent()
        self._handler = Handler(self._exit_event, 'executor')

        self._running = False
        self._paused = False
        self._thread = None

        self.current_task = None
        self.onetime_tasks = []
        self.trigger_tasks = []
        self.scheduled_tasks = []

        self._last_frame_time = 0
        self._lock = threading.Lock()
        self._frame_rate = 0.3  # min seconds between screenshots

    def start(self):
        """Start the executor thread."""
        if self._running:
            logger.warning('Executor already running')
            return

        self._running = True
        self._exit_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name='TaskExecutor')
        self._thread.start()
        logger.info('Task executor started')

    def stop(self):
        """Stop the executor."""
        logger.info('Stopping executor...')
        self._running = False
        self._exit_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info('Task executor stopped')

    def pause(self):
        """Pause execution."""
        self._paused = True
        logger.info('Task executor paused')

    def resume(self):
        """Resume execution."""
        self._paused = False
        logger.info('Task executor resumed')

    def add_task(self, task):
        """Add a one-time task to run next."""
        if hasattr(task, 'device_manager') and self.device_manager:
            task.device_manager = self.device_manager
        if hasattr(task, 'feature_set') and self.feature_set:
            task.feature_set = self.feature_set
        if hasattr(task, '_exit_event'):
            task._exit_event = self._exit_event
        if hasattr(task, '_handler'):
            task._handler = self._handler
        self.onetime_tasks.append(task)

    def add_trigger_task(self, task):
        """Add a trigger task that runs when its condition is met."""
        if hasattr(task, 'device_manager'):
            task.device_manager = self.device_manager
        if hasattr(task, 'feature_set'):
            task.feature_set = self.feature_set
        if hasattr(task, '_exit_event'):
            task._exit_event = self._exit_event
        self.trigger_tasks.append(task)

    def add_scheduled_task(self, task, interval_minutes):
        """Add a task that runs at intervals."""
        if hasattr(task, 'device_manager'):
            task.device_manager = self.device_manager
        if hasattr(task, 'feature_set'):
            task.feature_set = self.feature_set
        self.scheduled_tasks.append((task, interval_minutes * 60, 0))

    def _run_loop(self):
        """Main execution loop."""
        logger.info('Executor loop started')
        while not self._exit_event.is_set():
            try:
                # Check pause
                if self._paused:
                    self._exit_event.sleep(1)
                    continue

                # Check scheduled tasks
                self._check_scheduled()

                # Check trigger tasks
                self._check_triggers()

                # Run one-time tasks
                self._run_pending_tasks()

                # Sleep to prevent CPU spinning
                self._exit_event.sleep(0.1)

            except Exception as e:
                logger.error(f'Executor error: {e}')
                self._exit_event.sleep(1)

        logger.info('Executor loop ended')

    def _check_scheduled(self):
        """Run scheduled tasks that are due."""
        now = time.time()
        for i, (task, interval, last_run) in enumerate(self.scheduled_tasks):
            if now - last_run >= interval:
                try:
                    logger.info(f'Running scheduled: {task._task_name}')
                    if hasattr(task, 'execute'):
                        task.execute()
                    else:
                        task.run()
                    self.scheduled_tasks[i] = (task, interval, now)
                except FinishedError:
                    logger.info(f'Scheduled task finished: {task._task_name}')
                except Exception as e:
                    logger.error(f'Scheduled task error: {e}')

    def _check_triggers(self):
        """Check and run trigger tasks."""
        for task in self.trigger_tasks:
            if self._exit_event.is_set():
                return
            try:
                if self._should_trigger(task):
                    self.current_task = task
                    if hasattr(task, 'execute'):
                        task.execute()
                    else:
                        task.run()
                    self.current_task = None
            except FinishedError:
                logger.info(f'Trigger task finished: {task._task_name}')
                self.current_task = None
            except Exception as e:
                logger.error(f'Trigger task error: {e}')
                self.current_task = None

    def _should_trigger(self, task):
        """Check if trigger condition is met. Override for custom logic."""
        if hasattr(task, 'should_trigger'):
            return task.should_trigger()
        return True

    def _run_pending_tasks(self):
        """Run pending one-time tasks."""
        while self.onetime_tasks and not self._exit_event.is_set():
            task = self.onetime_tasks.pop(0)
            try:
                self.current_task = task
                if hasattr(task, 'execute'):
                    task.execute()
                else:
                    task.run()
            except FinishedError:
                logger.info(f'Task finished: {task._task_name}')
            except TaskDisabledError:
                logger.info(f'Task disabled: {task._task_name}')
            except Exception as e:
                logger.error(f'Task error in {task._task_name}: {e}')
            finally:
                self.current_task = None

    @property
    def is_running(self):
        return self._running

    @property
    def is_paused(self):
        return self._paused

    @property
    def exit_event(self):
        return self._exit_event

    @property
    def handler(self):
        return self._handler
