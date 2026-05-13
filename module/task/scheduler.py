"""
Task scheduler - manages scheduled task execution.
Adapted from Alas scheduler_watcher.py.
"""

import time
import threading

from module.util.logger import logger


class TaskScheduler:
    """
    Schedules and runs tasks on a timer.
    """
    
    def __init__(self, config=None):
        self.config = config or {}
        self._running = False
        self._thread = None
        self._exit_event = threading.Event()
        self._tasks = []  # (task, interval_seconds, last_run_time)
    
    def add_scheduled_task(self, task, interval_minutes):
        """Add a task to run at regular intervals."""
        self._tasks.append((task, interval_minutes * 60, 0))
        logger.info(f'Scheduled task: {task._task_name} every {interval_minutes}min')
    
    def start(self):
        """Start the scheduler."""
        if self._running:
            return
        self._running = True
        self._exit_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info('Scheduler started')
    
    def stop(self):
        """Stop the scheduler."""
        self._running = False
        self._exit_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info('Scheduler stopped')
    
    def _run_loop(self):
        """Main scheduler loop."""
        while not self._exit_event.is_set():
            now = time.time()
            for task, interval, last_run in self._tasks:
                if now - last_run >= interval:
                    try:
                        logger.info(f'Running scheduled task: {task._task_name}')
                        task.run()
                        # Update last run time
                        idx = self._tasks.index((task, interval, last_run))
                        self._tasks[idx] = (task, interval, now)
                    except Exception as e:
                        logger.error(f'Scheduled task error: {e}')
            
            time.sleep(10)  # Check every 10 seconds
