"""
Emulator base classes - adapted from Alas module/device/platform/emulator_base.py
"""

import os
import re
from dataclasses import dataclass


def abspath(path):
    return os.path.abspath(path).replace('\\', '/')


def get_serial_pair(serial):
    """
    Get ADB serial pair from a serial.
    E.g., '127.0.0.1:5555' -> ('127.0.0.1:5555', 'emulator-5554')
    """
    if serial.startswith('127.0.0.1:'):
        try:
            port = int(serial[10:])
            if 5555 <= port <= 5555 + 32:
                return f'127.0.0.1:{port}', f'emulator-{port - 1}'
        except (ValueError, IndexError):
            pass
    if serial.startswith('emulator-'):
        try:
            port = int(serial[9:])
            if 5554 <= port <= 5554 + 32:
                return f'127.0.0.1:{port + 1}', f'emulator-{port}'
        except (ValueError, IndexError):
            pass
    return None, None


def remove_duplicated_path(paths):
    """Remove duplicated paths (case-insensitive)."""
    paths = sorted(set(paths))
    seen = {}
    for path in paths:
        seen.setdefault(path.lower(), path)
    return list(seen.values())


class cached_property:
    """Simple cached property descriptor."""
    
    def __init__(self, func):
        self.func = func
    
    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


def iter_folder(folder, is_dir=False, ext=None):
    """Iterate files in a folder."""
    try:
        files = os.listdir(folder)
    except FileNotFoundError:
        return
    
    for file in files:
        sub = os.path.join(folder, file)
        if is_dir:
            if os.path.isdir(sub):
                yield sub.replace('\\\\', '/').replace('\\', '/')
        elif ext is not None:
            if not os.path.isdir(sub):
                _, extension = os.path.splitext(file)
                if extension == ext:
                    yield sub.replace('\\\\', '/').replace('\\', '/')
        else:
            if not os.path.isdir(sub):
                yield sub.replace('\\\\', '/').replace('\\', '/')


@dataclass
class EmulatorInstanceBase:
    """Base class for emulator instance."""
    serial: str
    name: str
    path: str
    
    def __str__(self):
        return f'{self.type}(serial="{self.serial}", name="{self.name}", path="{self.path}")'
    
    @cached_property
    def type(self):
        return self.emulator.type
    
    @cached_property
    def emulator(self):
        return EmulatorBase(self.path)


class EmulatorBase:
    """
    Base class for emulator type detection.
    """
    # Emulator type constants
    NoxPlayer = 'NoxPlayer'
    NoxPlayer64 = 'NoxPlayer64'
    BlueStacks4 = 'BlueStacks4'
    BlueStacks5 = 'BlueStacks5'
    LDPlayer3 = 'LDPlayer3'
    LDPlayer4 = 'LDPlayer4'
    LDPlayer9 = 'LDPlayer9'
    LDPlayer14 = 'LDPlayer14'
    MuMuPlayer = 'MuMuPlayer'
    MuMuPlayer9 = 'MuMuPlayer9'
    MuMuVMM = 'MuMuVMM'
    MuMuPlayerX = 'MuMuPlayerX'
    NemuIPC = 'NemuIPC'
    WSA = 'WSA'
    GooglePlay = 'GooglePlay'
    
    def __init__(self, path: str = ''):
        self.path = path
    
    @property
    def type(self) -> str:
        """Override in subclass."""
        return 'Unknown'
    
    def __str__(self):
        return f'{self.type}(path="{self.path}")'
    
    def __repr__(self):
        return str(self)


class EmulatorManagerBase:
    """Base class for emulator management."""
    
    @classmethod
    def all_emulators(cls):
        """Return all installed emulator types."""
        return []
    
    @classmethod
    def all_emulator_instances(cls):
        """Return all emulator instances."""
        return []
