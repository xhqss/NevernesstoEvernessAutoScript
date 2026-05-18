"""
Spec §28 — Plugin Sandbox.

PluginSandbox: 5 permission flags + path whitelist + violation audit.
PluginRegistry: global plugin registry.
"""

import os
import time
from dataclasses import dataclass, field
from collections import deque
from typing import Callable

from module.runtime.event_bus import bus
from module.runtime.base_module import BaseModule
from module.util.logger import logger


# ── Permission flags ──────────────────────────────────────────────────

@dataclass
class PluginPermissions:
    fs_read: bool = False
    fs_write: bool = False
    network: bool = False
    subprocess: bool = False
    device_control: bool = False

    def to_flags(self) -> list[str]:
        return [k for k, v in self.__dict__.items() if v]


# ── Plugin sandbox ────────────────────────────────────────────────────

class PluginSandbox:
    """Restricted execution sandbox for plugins."""

    def __init__(self, name: str, permissions: PluginPermissions, path_whitelist: list[str] | None = None):
        self.name = name
        self.permissions = permissions
        self.path_whitelist = [os.path.abspath(p) for p in (path_whitelist or [])]
        self._violations: deque[tuple[float, str, str]] = deque(maxlen=200)
        self._enabled = True

    def check_path(self, path: str, mode: str = "read") -> bool:
        if not self.path_whitelist:
            return True
        if mode == "read" and not self.permissions.fs_read:
            self._record_violation("fs_read", path)
            return False
        if mode == "write" and not self.permissions.fs_write:
            self._record_violation("fs_write", path)
            return False
        abs_path = os.path.abspath(path)
        allowed = any(abs_path.startswith(w) for w in self.path_whitelist)
        if not allowed:
            self._record_violation("path_whitelist", path)
        return allowed

    def check_permission(self, flag: str) -> bool:
        allowed = getattr(self.permissions, flag, False)
        if not allowed:
            self._record_violation(flag, "permission check")
        return allowed

    def _record_violation(self, flag: str, detail: str):
        self._violations.append((time.time(), flag, detail))
        logger.warning(f'Sandbox[{self.name}] violation: {flag} → {detail}')
        bus.emit("SANDBOX_VIOLATION", {
            "plugin": self.name, "flag": flag, "detail": detail,
        })

    @property
    def violations(self) -> list[tuple[float, str, str]]:
        return list(self._violations)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def disable(self):
        self._enabled = False

    def enable(self):
        self._enabled = True


# ── Plugin registry ───────────────────────────────────────────────────

class PluginRegistry:
    """Global registry for loaded plugins."""

    def __init__(self):
        self._entries: dict[str, PluginSandbox] = {}
        self._metadata: dict[str, dict] = {}

    def register(self, name: str, sandbox: PluginSandbox, meta: dict | None = None):
        self._entries[name] = sandbox
        self._metadata[name] = meta or {}
        logger.info(f'Plugin registered: {name}')

    def unregister(self, name: str):
        self._entries.pop(name, None)
        self._metadata.pop(name, None)
        logger.info(f'Plugin unregistered: {name}')

    def get(self, name: str) -> PluginSandbox | None:
        return self._entries.get(name)

    def list(self) -> list[str]:
        return sorted(self._entries.keys())

    def stats(self) -> dict:
        return {
            "plugin_count": len(self._entries),
            "plugins": {
                name: {
                    "permissions": sb.permissions.to_flags(),
                    "violations": len(sb.violations),
                    "enabled": sb.is_enabled,
                    "meta": self._metadata.get(name, {}),
                }
                for name, sb in self._entries.items()
            },
        }
