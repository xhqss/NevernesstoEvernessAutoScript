"""
Spec §3 — RuntimeManager.

Creates all runtime components, injects Device/OCR callbacks,
registers L1-L9 recovery actions into RecoveryRuntime.
"""

import time

from module.runtime.event_bus import bus
from module.runtime import RuntimeContext
from module.runtime.base_module import BaseModule
from module.runtime.tick_loop import TickLoop
from module.runtime.state_machine import StateMachine, Transition
from module.runtime.recovery import RecoveryRuntime, RECOVERY_CHAIN
from module.runtime.watchdog import Watchdog
from module.runtime.metrics import MetricsRuntime
from module.runtime.security import SecurityRuntime
from module.runtime.resource import ResourceRuntime
from module.runtime.update import UpdateRuntime
from module.runtime.debug import DebugRuntime
from module.runtime.instances import InstanceManager
from module.util.logger import logger


class RuntimeManager(BaseModule):
    """Orchestrates all runtime subsystems.

    Creates the full runtime topology and wires them together
    through EventBus + RuntimeContext.
    """

    def __init__(self, ctx: RuntimeContext):
        super().__init__()
        self.ctx = ctx
        self._device_manager = None

        # ── Instantiate all runtime components (§3 topology) ──
        self.tick_loop = TickLoop(ctx)
        self.state_machine = StateMachine(ctx)
        self.recovery = RecoveryRuntime(ctx)
        self.watchdog = Watchdog(ctx)
        self.metrics = MetricsRuntime(ctx)
        self.security = SecurityRuntime(ctx)
        self.resource = ResourceRuntime(ctx)
        self.update = UpdateRuntime(ctx)
        self.debug = DebugRuntime(ctx)
        self.instances = InstanceManager(ctx)

        # ── Register recovery actions (L1-L9) ──
        self._register_recovery_actions()

        # ── Register default state transitions ──
        self._register_default_transitions()

        # ── Wire watchdog alerts → recovery ──
        bus.subscribe("WATCHDOG_ALERT", self._on_watchdog_alert)

        logger.info('RuntimeManager initialized')

    def set_device_manager(self, device_manager):
        """Inject device manager for recovery actions."""
        self._device_manager = device_manager

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self):
        logger.info('RuntimeManager starting all subsystems...')
        self.tick_loop.start()
        self.watchdog.start()
        self.metrics.start() if hasattr(self.metrics, 'start') else None
        self.security.start()
        self.resource.start()
        self.update.start()
        self.debug.start()
        self.instances.start()
        logger.info('RuntimeManager: all subsystems started')

    def stop(self):
        logger.info('RuntimeManager stopping all subsystems...')
        self.update.stop()
        self.debug.stop()
        self.resource.stop()
        self.security.stop()
        self.watchdog.stop()
        self.tick_loop.stop()
        self.instances.stop()
        logger.info('RuntimeManager: all subsystems stopped')

    def pause(self):
        pass

    def tick(self):
        self.resource.tick()

    def recover(self) -> bool:
        return True

    def healthcheck(self) -> dict:
        return {
            "tick_loop": self.tick_loop.is_running,
            "state": self.ctx.state,
            "recovery_rate": self.recovery.success_rate,
            "watchdog": self.watchdog.stats() if hasattr(self.watchdog, 'stats') else {},
        }

    # ── Recovery action registration ──────────────────────────────

    def _register_recovery_actions(self):
        rec = self.recovery

        rec.register_handler("L1_RETRY", lambda: self._recovery_retry())
        rec.register_handler("L2_REFOCUS_WINDOW", lambda: self._recovery_refocus())
        rec.register_handler("L3_REDETECT", lambda: self._recovery_redetect())
        rec.register_handler("L4_INJECT_ESC", lambda: self._recovery_inject_esc())
        rec.register_handler("L5_RECONNECT_DEVICE", lambda: self._recovery_reconnect())
        rec.register_handler("L6_RESTART_MODULE", lambda: self._recovery_restart_module())
        rec.register_handler("L7_RESTART_GAME", lambda: self._recovery_restart_game())
        rec.register_handler("L8_RESTART_EMULATOR", lambda: self._recovery_restart_emulator())
        rec.register_handler("L9_RESTART_RUNTIME", lambda: self._recovery_restart_runtime())

        logger.info(f'Registered {len(RECOVERY_CHAIN)} recovery actions (L1-L9)')

    def _recovery_retry(self) -> bool:
        time.sleep(0.5)
        return True

    def _recovery_refocus(self) -> bool:
        if self._device_manager and hasattr(self._device_manager, 'hwnd_window'):
            hwnd = self._device_manager.hwnd_window
            if hwnd:
                try:
                    from module.util.process import find_window_by_title
                    import ctypes
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    return True
                except Exception:
                    pass
        return False

    def _recovery_redetect(self) -> bool:
        bus.emit("RECOVERY_REDETECT", {})
        return True

    def _recovery_inject_esc(self) -> bool:
        if self._device_manager:
            self._device_manager.send_key("esc")
            return True
        return False

    def _recovery_reconnect(self) -> bool:
        if self._device_manager and hasattr(self._device_manager, 'reconnect'):
            return self._device_manager.reconnect()
        return False

    def _recovery_restart_module(self) -> bool:
        logger.warning('L6_RESTART_MODULE — restarting tick loop')
        self.tick_loop.stop()
        time.sleep(1)
        self.tick_loop.start()
        return True

    def _recovery_restart_game(self) -> bool:
        logger.warning('L7_RESTART_GAME — placeholder')
        bus.emit("RECOVERY_RESTART_GAME_REQUEST", {})
        return True

    def _recovery_restart_emulator(self) -> bool:
        logger.warning('L8_RESTART_EMULATOR — placeholder')
        bus.emit("RECOVERY_RESTART_EMULATOR_REQUEST", {})
        return True

    def _recovery_restart_runtime(self) -> bool:
        logger.warning('L9_RESTART_RUNTIME — full runtime restart')
        self.stop()
        time.sleep(2)
        self.start()
        return True

    # ── State machine setup ───────────────────────────────────────

    def _register_default_transitions(self):
        sm = self.state_machine
        sm.register(Transition(source="INIT", target="READY", trigger="init"))
        sm.register(Transition(source="READY", target="RUNNING", trigger="start"))
        sm.register(Transition(source="RUNNING", target="PAUSED", trigger="pause"))
        sm.register(Transition(source="PAUSED", target="RUNNING", trigger="resume"))
        sm.register(Transition(source="RUNNING", target="STOPPED", trigger="stop"))
        sm.register(Transition(source="PAUSED", target="STOPPED", trigger="stop"))
        sm.register(Transition(source="RUNNING", target="RECOVERING", trigger="recover_enter"))
        sm.register(Transition(source="RECOVERING", target="RUNNING", trigger="recover_exit"))
        sm.register(Transition(source="ERROR", target="INIT", trigger="reset"))
        sm.register(Transition(source="ERROR", target="STOPPED", trigger="stop"))

    # ── Watchdog → Recovery bridge ────────────────────────────────

    def _on_watchdog_alert(self, event_type: str, payload: dict):
        alert_type = payload.get("type", "UNKNOWN")
        reason = f"Watchdog: {alert_type}"
        level = "L1_RETRY"
        if alert_type in ("FROZEN_SCREEN", "STALE_STATE", "OCR_LOOP"):
            level = "L3_REDETECT"
        elif alert_type == "TICK_STARVATION":
            level = "L6_RESTART_MODULE"
        elif alert_type in ("MEMORY_GROWTH", "CPU_SPIKE"):
            level = "L2_REFOCUS_WINDOW"
        bus.emit("RECOVERY_TRIGGER", {"reason": reason, "level": level})

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "tick": self.ctx.current_tick,
            "state": self.ctx.state,
            "uptime_s": time.time() - self.ctx.runtime_start_ts,
            "metrics": self.metrics.snapshot() if hasattr(self.metrics, 'snapshot') else {},
            "recovery": self.recovery.stats(),
            "watchdog": self.watchdog.stats() if hasattr(self.watchdog, 'stats') else {},
            "resource": self.resource.stats() if hasattr(self.resource, 'stats') else {},
        }
