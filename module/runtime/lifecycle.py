"""
Spec §8 — ModuleLifecycle state machine.

Enforces exactly 7 legal state transitions.
Rejects all implicit / undefined transitions.
"""

from enum import Enum


class ModuleState(str, Enum):
    INIT = "INIT"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RECOVERING = "RECOVERING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


# Spec §8: only these 7 transitions are legal
LEGAL_TRANSITIONS: dict[ModuleState, set[ModuleState]] = {
    ModuleState.INIT:       {ModuleState.READY, ModuleState.ERROR},
    ModuleState.READY:      {ModuleState.RUNNING, ModuleState.STOPPED, ModuleState.ERROR},
    ModuleState.RUNNING:    {ModuleState.PAUSED, ModuleState.RECOVERING, ModuleState.STOPPING, ModuleState.ERROR},
    ModuleState.PAUSED:     {ModuleState.RUNNING, ModuleState.STOPPING, ModuleState.ERROR},
    ModuleState.RECOVERING: {ModuleState.RUNNING, ModuleState.ERROR},
    ModuleState.STOPPING:   {ModuleState.STOPPED, ModuleState.ERROR},
    ModuleState.STOPPED:    set(),
    ModuleState.ERROR:      {ModuleState.INIT, ModuleState.STOPPED},
}


class IllegalTransition(Exception):
    """Raised when an undefined state transition is attempted."""
    pass


class ModuleLifecycle:
    """State machine that enforces legal module transitions only."""

    def __init__(self, name: str = ""):
        self.name = name
        self._state: ModuleState = ModuleState.INIT
        self._transition_count = 0
        self._history: list[tuple[ModuleState, ModuleState]] = []

    @property
    def state(self) -> ModuleState:
        return self._state

    def transition(self, target: ModuleState) -> bool:
        current = self._state
        legal = LEGAL_TRANSITIONS.get(current, set())
        if target not in legal:
            raise IllegalTransition(
                f"{self.name}: {current.value} → {target.value} is not a legal transition"
            )
        self._state = target
        self._transition_count += 1
        self._history.append((current, target))
        return True

    def can_transition(self, target: ModuleState) -> bool:
        return target in LEGAL_TRANSITIONS.get(self._state, set())

    @property
    def history(self) -> list[tuple[ModuleState, ModuleState]]:
        return list(self._history)

    def stats(self) -> dict:
        return {
            "name": self.name,
            "state": self._state.value,
            "transitions": self._transition_count,
        }
