from module.device.app_control import PostMessageInteraction
from module.device.method.pynput import PynputInteraction


class NTEOneTimeTask:
    """Mixin that brings window to front before running a one-time task."""

    def run(self):
        if hasattr(self, 'executor') and self.executor is not None:
            if isinstance(self.executor.interaction, PostMessageInteraction):
                self.executor.interaction.activate()
            elif isinstance(self.executor.interaction, PynputInteraction):
                self.bring_to_front()
        self.sleep(0.5)
