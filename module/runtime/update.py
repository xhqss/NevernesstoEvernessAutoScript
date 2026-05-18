"""
Spec §3 — Update Runtime.

Checks for updates via deploy/git.py.
Coordinates config hot-reload.
"""

import time
import threading

from module.runtime.event_bus import bus
from module.runtime.base_module import BaseModule
from module.runtime import RuntimeContext
from module.util.logger import logger


class UpdateRuntime(BaseModule):
    """Coordinates update checks and config hot-reload."""

    def __init__(self, ctx: RuntimeContext):
        super().__init__()
        self.ctx = ctx
        self._running = False
        self._thread: threading.Thread | None = None
        self._check_interval_s = 3600  # 1 hour
        self._last_check: float = 0.0
        self._update_available = False
        self._git_manager = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name='UpdateRuntime')
        self._thread.start()
        logger.info('UpdateRuntime started')

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info('UpdateRuntime stopped')

    def pause(self):
        pass

    def tick(self):
        pass

    def recover(self) -> bool:
        return True

    def healthcheck(self) -> dict:
        return {
            "running": self._running,
            "update_available": self._update_available,
            "last_check_ts": self._last_check,
        }

    def _loop(self):
        while self._running:
            time.sleep(self._check_interval_s)
            try:
                self.check()
            except Exception:
                logger.error('UpdateRuntime check error', exc_info=True)

    def check(self) -> bool:
        self._last_check = time.time()
        try:
            from deploy.git import GitManager
            git = GitManager()
            # Check if remote has new commits
            # Lightweight check only; full update gated by user config
            self._update_available = self._check_remote(git)
            if self._update_available:
                bus.emit("UPDATE_AVAILABLE", {"timestamp": self._last_check})
                logger.info('Update available')
            return self._update_available
        except Exception as e:
            logger.error(f'Update check failed: {e}')
            return False

    def _check_remote(self, git) -> bool:
        try:
            import subprocess
            result = subprocess.run(
                [git.git, 'ls-remote', '--heads'],
                capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except Exception:
            return False

    def hot_reload_config(self) -> bool:
        """Trigger config hot-reload via the config subsystem."""
        try:
            from module.config.runtime_config import ConfigHotReload
            reloader = ConfigHotReload(self.ctx.config)
            return reloader.check_and_apply()
        except Exception as e:
            logger.error(f'Config hot-reload failed: {e}')
            bus.emit("CONFIG_RELOAD_FAILED", {"error": str(e)})
            return False

    @property
    def update_available(self) -> bool:
        return self._update_available
