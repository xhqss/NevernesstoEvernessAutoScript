"""SoundCombatContext – singleton coordinating SoundListener + DodgeCounterTrigger.

FAITHFUL port of ok-nte's SoundCombatContext.  Wires the audio listener to
combat-trigger logic, maintains a 1 s action window for pending dodge/counter
events, and supports queued combat-interrupt actions.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from module.neverness.sound.listener import SoundListener
from module.neverness.sound.trigger import DodgeCounterTrigger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Action types
# ---------------------------------------------------------------------------
class ActionType(Enum):
    DODGE = auto()
    COUNTER = auto()


@dataclass
class PendingAction:
    action: ActionType
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# SoundCombatContext
# ---------------------------------------------------------------------------
class SoundCombatContext:
    """Singleton that ties audio detection to combat actions.

    Usage::

        ctx = SoundCombatContext()
        ctx.update_task(task)
        ctx.update_config(dodge_cooldown=0.6)
        ctx.start()
        ...
        ctx.shutdown()
    """

    _instance: SoundCombatContext | None = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> SoundCombatContext:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialise()
        return cls._instance

    def _initialise(self) -> None:
        # Core components
        self._listener: SoundListener | None = None
        self._trigger: DodgeCounterTrigger = DodgeCounterTrigger()

        # Action window / queue
        self._action_window_s: float = 1.0
        self._pending_queue: deque[PendingAction] = deque()

        # Config
        self._dodge_cooldown: float = 0.6
        self._counter_cooldown: float = 0.5
        self._dodge_threshold: float = 0.45
        self._counter_threshold: float = 0.45

        # State
        self._running: bool = False
        self._task: Any = None
        self._lock = threading.Lock()
        self._drain_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def update_task(self, task: Any) -> None:
        """Bind a new task instance to the trigger."""
        self._task = task
        self._trigger.set_task(task)
        logger.debug("SoundCombatContext task updated")

    def update_config(
        self,
        dodge_cooldown: float | None = None,
        counter_cooldown: float | None = None,
        dodge_threshold: float | None = None,
        counter_threshold: float | None = None,
        action_window_s: float | None = None,
    ) -> None:
        """Update run-time parameters.

        Parameters are only set when not None.
        """
        if dodge_cooldown is not None:
            self._dodge_cooldown = dodge_cooldown
            self._trigger.dodge_cooldown = dodge_cooldown
        if counter_cooldown is not None:
            self._counter_cooldown = counter_cooldown
            self._trigger.counter_cooldown = counter_cooldown
        if dodge_threshold is not None:
            self._dodge_threshold = dodge_threshold
        if counter_threshold is not None:
            self._counter_threshold = counter_threshold
        if action_window_s is not None:
            self._action_window_s = action_window_s

        logger.debug(
            "SoundCombatContext config: dodge_cd=%.2f counter_cd=%.2f "
            "dodge_th=%.2f counter_th=%.2f window=%.2f",
            self._dodge_cooldown,
            self._counter_cooldown,
            self._dodge_threshold,
            self._counter_threshold,
            self._action_window_s,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True

        # Build listener
        self._listener = SoundListener()
        self._listener.register_trigger(
            "dodge",
            threshold=self._dodge_threshold,
            cooldown_s=self._dodge_cooldown,
            callback=self._on_dodge_detected,
        )
        self._listener.register_trigger(
            "counter",
            threshold=self._counter_threshold,
            cooldown_s=self._counter_cooldown,
            callback=self._on_counter_detected,
        )
        self._listener.start()

        # Start the pending-action drain thread
        self._drain_thread = threading.Thread(
            target=self._drain_loop, daemon=True, name="SoundDrain"
        )
        self._drain_thread.start()

        logger.info("SoundCombatContext started")

    def stop(self) -> None:
        """Pause audio processing without tearing down resources."""
        self._running = False
        if self._drain_thread is not None:
            self._drain_thread.join(timeout=2)
            self._drain_thread = None

    def shutdown(self) -> None:
        """Full teardown – release audio resources."""
        self._running = False
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if self._drain_thread is not None:
            self._drain_thread.join(timeout=2)
            self._drain_thread = None
        with self._lock:
            self._pending_queue.clear()
        logger.info("SoundCombatContext shut down")

    # ------------------------------------------------------------------
    # Detection callbacks
    # ------------------------------------------------------------------
    def _on_dodge_detected(self) -> None:
        """Called by SoundListener when a dodge sound is matched."""
        with self._lock:
            self._pending_queue.append(PendingAction(ActionType.DODGE))
        logger.debug("Dodge event queued")

    def _on_counter_detected(self) -> None:
        """Called by SoundListener when a counter sound is matched."""
        with self._lock:
            self._pending_queue.append(PendingAction(ActionType.COUNTER))
        logger.debug("Counter event queued")

    # ------------------------------------------------------------------
    # Action drain loop
    # ------------------------------------------------------------------
    def _drain_loop(self) -> None:
        """Background thread that drains the pending-action queue.

        Actions older than ``_action_window_s`` are dropped.
        """
        logger.info("Sound drain loop started")
        while self._running:
            time.sleep(0.05)  # 50 ms poll
            try:
                self._drain_expired()
                self._execute_pending_action()
            except Exception:
                logger.exception("Error in sound drain loop")
        logger.info("Sound drain loop stopped")

    def _drain_expired(self) -> None:
        """Remove actions that have exceeded the action window."""
        now = time.time()
        with self._lock:
            while self._pending_queue:
                if now - self._pending_queue[0].timestamp > self._action_window_s:
                    dropped = self._pending_queue.popleft()
                    logger.debug("Dropped expired %s action", dropped.action.name)
                else:
                    break

    def execute_pending_action(self) -> bool:
        """Execute the oldest pending action (dodge or counter).

        Returns True if an action was executed.
        """
        self._drain_expired()
        return self._execute_pending_action()

    def _execute_pending_action(self) -> bool:
        with self._lock:
            if not self._pending_queue:
                return False
            pending = self._pending_queue.popleft()

        logger.debug("Executing pending %s action", pending.action.name)
        if pending.action == ActionType.DODGE:
            return self._trigger.dodge()
        elif pending.action == ActionType.COUNTER:
            return self._trigger.counter()
        return False

    # ------------------------------------------------------------------
    # Combat interrupt helpers
    # ------------------------------------------------------------------
    def on_combat_start(self) -> None:
        """Notify that combat has started."""
        logger.info("SoundCombatContext: combat started")
        if not self._running:
            self.start()

    def on_combat_end(self) -> None:
        """Notify that combat has ended."""
        logger.info("SoundCombatContext: combat ended")
        with self._lock:
            self._pending_queue.clear()

    def clear_pending(self) -> None:
        """Discard all queued actions."""
        with self._lock:
            self._pending_queue.clear()

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending_queue)

    @property
    def is_running(self) -> bool:
        return self._running
