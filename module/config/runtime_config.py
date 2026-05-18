"""
Spec §23-24 — RuntimeConfig Pydantic model + ConfigHotReload.

RuntimeConfig: Tick/Device/OCR/Recovery/Watchdog/Metrics sub-models.
ConfigHotReload: file-change → schema validate → sandbox load → diff → apply → rollback.
"""

import json
import os
import time
from typing import Any

from module.util.logger import logger

try:
    from pydantic import BaseModel, Field, ValidationError
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


# ── Sub-models (fallback to dict-based if pydantic unavailable) ──────

class _SubConfig:
    """Lightweight config holder when pydantic is not available."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


if HAS_PYDANTIC:

    class TickConfig(BaseModel):
        hz: int = 10
        budget_ms: int = 100
        max_jitter_ms: int = 15

    class DeviceConfig(BaseModel):
        platform: str = "auto"
        target_width: int = 1280
        target_height: int = 720
        screenshot_timeout_ms: int = 500
        input_timeout_ms: int = 300

    class OCRConfig(BaseModel):
        engine: str = "default"
        lang: str = "ch"
        cache_ttl_s: float = 2.0
        cache_max_entries: int = 500
        latency_budget_ms: int = 300

    class RecoveryConfig(BaseModel):
        enabled: bool = True
        max_escalation: str = "L9_RESTART_RUNTIME"
        cooldown_s: float = 5.0
        weight_adapt_rate: float = 0.2

    class WatchdogConfig(BaseModel):
        enabled: bool = True
        check_interval_s: int = 10
        frozen_screen_threshold_s: int = 60
        stale_state_threshold_s: int = 30
        tick_starvation_threshold_s: int = 5
        memory_growth_threshold: float = 0.05
        cpu_spike_threshold: float = 0.90

    class MetricsConfig(BaseModel):
        enabled: bool = True
        report_interval_s: int = 60
        retention_ticks: int = 600

    class RuntimeConfig(BaseModel):
        tick: TickConfig = Field(default_factory=TickConfig)
        device: DeviceConfig = Field(default_factory=DeviceConfig)
        ocr: OCRConfig = Field(default_factory=OCRConfig)
        recovery: RecoveryConfig = Field(default_factory=RecoveryConfig)
        watchdog: WatchdogConfig = Field(default_factory=WatchdogConfig)
        metrics: MetricsConfig = Field(default_factory=MetricsConfig)

else:
    # Fallback when pydantic not installed
    class TickConfig(_SubConfig):
        def __init__(self, **kwargs):
            super().__init__(hz=10, budget_ms=100, max_jitter_ms=15, **kwargs)

    class DeviceConfig(_SubConfig):
        def __init__(self, **kwargs):
            super().__init__(platform="auto", target_width=1280, target_height=720,
                             screenshot_timeout_ms=500, input_timeout_ms=300, **kwargs)

    class OCRConfig(_SubConfig):
        def __init__(self, **kwargs):
            super().__init__(engine="default", lang="ch", cache_ttl_s=2.0,
                             cache_max_entries=500, latency_budget_ms=300, **kwargs)

    class RecoveryConfig(_SubConfig):
        def __init__(self, **kwargs):
            super().__init__(enabled=True, max_escalation="L9_RESTART_RUNTIME",
                             cooldown_s=5.0, weight_adapt_rate=0.2, **kwargs)

    class WatchdogConfig(_SubConfig):
        def __init__(self, **kwargs):
            super().__init__(enabled=True, check_interval_s=10,
                             frozen_screen_threshold_s=60, stale_state_threshold_s=30,
                             tick_starvation_threshold_s=5, memory_growth_threshold=0.05,
                             cpu_spike_threshold=0.90, **kwargs)

    class MetricsConfig(_SubConfig):
        def __init__(self, **kwargs):
            super().__init__(enabled=True, report_interval_s=60, retention_ticks=600, **kwargs)

    class RuntimeConfig:
        def __init__(self, d: dict | None = None):
            d = d or {}
            self.tick = TickConfig(**d.get("tick", {}))
            self.device = DeviceConfig(**d.get("device", {}))
            self.ocr = OCRConfig(**d.get("ocr", {}))
            self.recovery = RecoveryConfig(**d.get("recovery", {}))
            self.watchdog = WatchdogConfig(**d.get("watchdog", {}))
            self.metrics = MetricsConfig(**d.get("metrics", {}))

        def dict(self) -> dict:
            return {
                "tick": self.tick.dict(),
                "device": self.device.dict(),
                "ocr": self.ocr.dict(),
                "recovery": self.recovery.dict(),
                "watchdog": self.watchdog.dict(),
                "metrics": self.metrics.dict(),
            }


# ── ConfigHotReload ──────────────────────────────────────────────────

class ConfigHotReload:
    """File-change → Schema validate → Sandbox load → Diff → Apply → Rollback."""

    def __init__(self, config: dict, path: str = ""):
        self.config = config
        self.path = path or self._default_path()
        self._last_mtime: float = 0.0
        self._last_hash: str = ""
        self._backup: dict | None = None

    def _default_path(self) -> str:
        return os.path.join(os.getcwd(), "config", "runtime.json")

    def check_and_apply(self) -> bool:
        """Check for file changes and apply if valid. Returns True on success."""
        if not os.path.exists(self.path):
            return False

        try:
            mtime = os.path.getmtime(self.path)
            if mtime == self._last_mtime:
                return False
            self._last_mtime = mtime

            with open(self.path, 'r', encoding='utf-8') as f:
                raw = f.read()

            import hashlib
            new_hash = hashlib.sha256(raw.encode()).hexdigest()
            if new_hash == self._last_hash:
                return False
            self._last_hash = new_hash

            new_cfg = json.loads(raw)

            # Validate via schema
            validated = self._validate(new_cfg)
            if validated is None:
                logger.warning('ConfigHotReload: schema validation failed, keeping current config')
                return False

            # Backup, diff, apply
            self._backup = dict(self.config)
            diff = self._compute_diff(self.config, validated)
            self._apply(validated)
            logger.info(f'ConfigHotReload: applied {len(diff)} changes')
            return True

        except Exception as e:
            logger.error(f'ConfigHotReload: error during reload: {e}')
            if self._backup is not None:
                self._apply(self._backup)
                logger.info('ConfigHotReload: rolled back to previous config')
            return False

    def _validate(self, raw: dict) -> dict | None:
        try:
            if HAS_PYDANTIC:
                RuntimeConfig(**raw)
            return raw
        except Exception:
            return None

    def _compute_diff(self, old: dict, new: dict) -> dict:
        diff = {}
        for key in set(list(old.keys()) + list(new.keys())):
            old_v = old.get(key)
            new_v = new.get(key)
            if old_v != new_v:
                diff[key] = {"old": old_v, "new": new_v}
        return diff

    def _apply(self, cfg: dict):
        self.config.clear()
        self.config.update(cfg)
