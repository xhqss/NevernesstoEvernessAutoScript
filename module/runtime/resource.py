"""
Spec §3 — Resource Runtime.

Monitors: disk free space, available memory, GPU memory.
"""

import gc
import os
import time

from module.runtime.event_bus import bus
from module.runtime.base_module import BaseModule
from module.runtime import RuntimeContext
from module.util.logger import logger

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ── Thresholds ────────────────────────────────────────────────────────

DISK_MIN_FREE_MB = 500
MEMORY_MIN_FREE_MB = 256
GPU_MIN_FREE_MIB = 1024  # 1 GiB


class ResourceRuntime(BaseModule):
    """Monitors system resource availability."""

    def __init__(self, ctx: RuntimeContext):
        super().__init__()
        self.ctx = ctx
        self._running = False
        self._last_check_ts: float = 0.0

    def start(self):
        self._running = True
        logger.info('ResourceRuntime started')

    def stop(self):
        self._running = False
        logger.info('ResourceRuntime stopped')

    def pause(self):
        pass

    def tick(self):
        now = time.time()
        if now - self._last_check_ts < 30:
            return
        self._last_check_ts = now
        status = self.check()
        if status["alerts"]:
            bus.emit("RESOURCE_ALERT", status)

    def recover(self) -> bool:
        gc.collect()
        return True

    def healthcheck(self) -> dict:
        return self.check()

    # ── resource checks ───────────────────────────────────────────

    def check(self) -> dict:
        alerts: list[str] = []
        result: dict = {"alerts": alerts}

        # Disk
        disk = self._disk_free_mb()
        result["disk_free_mb"] = disk
        if disk is not None and disk < DISK_MIN_FREE_MB:
            alerts.append(f"disk_free={disk:.0f}MB < {DISK_MIN_FREE_MB}MB")

        # Memory
        mem = self._memory_available_mb()
        result["memory_available_mb"] = mem
        if mem is not None and mem < MEMORY_MIN_FREE_MB:
            alerts.append(f"memory_avail={mem:.0f}MB < {MEMORY_MIN_FREE_MB}MB")

        # GPU
        gpu = self._gpu_free_mib()
        result["gpu_free_mib"] = gpu
        if gpu is not None and gpu < GPU_MIN_FREE_MIB:
            alerts.append(f"gpu_free={gpu:.0f}MiB < {GPU_MIN_FREE_MIB}MiB")

        return result

    def _disk_free_mb(self) -> float | None:
        try:
            path = os.getcwd()
            if HAS_PSUTIL:
                return psutil.disk_usage(path).free / (1024 * 1024)
            import shutil
            usage = shutil.disk_usage(path)
            return usage.free / (1024 * 1024)
        except Exception:
            return None

    def _memory_available_mb(self) -> float | None:
        try:
            if HAS_PSUTIL:
                return psutil.virtual_memory().available / (1024 * 1024)
        except Exception:
            pass
        return None

    def _gpu_free_mib(self) -> float | None:
        try:
            from module.util.process import get_first_gpu_free_memory_mib
            return get_first_gpu_free_memory_mib()
        except Exception:
            return None

    def stats(self) -> dict:
        return self.check()
