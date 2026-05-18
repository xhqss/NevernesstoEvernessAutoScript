"""
Spec §33 — Instance Manager.

Creates isolated instance directories:
  instances/instance_001/
    ├── logs/
    ├── cache/
    ├── temp/
    ├── screenshots/
    ├── metrics/
    └── config/
"""

import os
import shutil
import threading
from dataclasses import dataclass, field

from module.runtime.base_module import BaseModule
from module.runtime import RuntimeContext
from module.util.logger import logger


INSTANCE_ROOT = "instances"
INSTANCE_PREFIX = "instance"


@dataclass
class InstanceContext:
    """Isolated filesystem context for one instance."""
    instance_id: str
    root: str
    logs: str
    cache: str
    temp: str
    screenshots: str
    metrics: str
    config: str


class InstanceManager(BaseModule):
    """Manages multi-instance isolation directories."""

    def __init__(self, ctx: RuntimeContext, root: str = INSTANCE_ROOT):
        super().__init__()
        self.ctx = ctx
        self.root = os.path.abspath(root)
        self._instances: dict[str, InstanceContext] = {}
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        self._running = True
        logger.info('InstanceManager started')

    def stop(self):
        self._running = False
        logger.info('InstanceManager stopped')

    def pause(self):
        pass

    def tick(self):
        pass

    def recover(self) -> bool:
        return True

    def healthcheck(self) -> dict:
        return {
            "instance_count": len(self._instances),
            "instances": list(self._instances.keys()),
        }

    # ── instance lifecycle ────────────────────────────────────────

    def create(self, instance_id: str | None = None) -> InstanceContext:
        """Create an isolated instance directory tree."""
        with self._lock:
            if instance_id is None:
                n = len(self._instances) + 1
                instance_id = f"{INSTANCE_PREFIX}_{n:03d}"
            if instance_id in self._instances:
                return self._instances[instance_id]
            base = os.path.join(self.root, instance_id)
            ctx = InstanceContext(
                instance_id=instance_id,
                root=base,
                logs=os.path.join(base, "logs"),
                cache=os.path.join(base, "cache"),
                temp=os.path.join(base, "temp"),
                screenshots=os.path.join(base, "screenshots"),
                metrics=os.path.join(base, "metrics"),
                config=os.path.join(base, "config"),
            )
            for attr in ("logs", "cache", "temp", "screenshots", "metrics", "config"):
                d = getattr(ctx, attr)
                os.makedirs(d, exist_ok=True)
            self._instances[instance_id] = ctx
            logger.info(f'Instance created: {instance_id} at {base}')
            return ctx

    def remove(self, instance_id: str, delete_files: bool = False):
        with self._lock:
            ctx = self._instances.pop(instance_id, None)
            if ctx and delete_files:
                try:
                    shutil.rmtree(ctx.root)
                except Exception as e:
                    logger.warning(f'Failed to remove instance dir: {e}')
        if ctx:
            logger.info(f'Instance removed: {instance_id}')

    def get(self, instance_id: str) -> InstanceContext | None:
        return self._instances.get(instance_id)

    def list(self) -> list[str]:
        return sorted(self._instances.keys())

    def stats(self) -> dict:
        return self.healthcheck()
