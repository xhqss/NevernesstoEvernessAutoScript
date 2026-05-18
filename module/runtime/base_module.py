"""
Spec §7 — BaseModule ABC.

Every runtime component inherits from BaseModule.
Defines the six mandatory lifecycle methods.
"""

from abc import ABC, abstractmethod


class BaseModule(ABC):
    """Abstract base for all runtime modules.

    All modules must implement: start, stop, pause, tick, recover, healthcheck.
    """

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__

    @abstractmethod
    def start(self):
        ...

    @abstractmethod
    def stop(self):
        ...

    @abstractmethod
    def pause(self):
        ...

    @abstractmethod
    def tick(self):
        ...

    @abstractmethod
    def recover(self) -> bool:
        ...

    @abstractmethod
    def healthcheck(self) -> dict:
        ...
