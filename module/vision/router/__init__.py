"""
Spec §11 — VisionRouter.

Routes vision tasks to the appropriate subsystem:
  text       → OCR
  icon       → ORB feature matching
  button     → template matching
  auto       → heuristic-based routing
"""

from enum import Enum

from module.util.logger import logger


class VisionTaskType(str, Enum):
    TEXT = "text"
    ICON = "icon"
    BUTTON = "button"
    AUTO = "auto"


class VisionRouter:
    """Routes vision tasks to the correct subsystem."""

    def __init__(self):
        self._handlers: dict[str, callable] = {}

    def register_handler(self, task_type: str, handler: callable):
        self._handlers[task_type] = handler

    def route(self, task_type: str, screenshot, **kwargs):
        """Route a vision task to its handler.

        task_type: "text" | "icon" | "button" | custom name
        """
        handler = self._handlers.get(task_type)
        if handler is None:
            logger.warning(f'VisionRouter: no handler for "{task_type}"')
            return None
        try:
            return handler(screenshot, **kwargs)
        except Exception as e:
            logger.error(f'VisionRouter handler[{task_type}] error: {e}')
            return None

    def detect(self, screenshot) -> dict:
        """Run all registered detectors. Returns {task_type: result}."""
        results = {}
        for task_type, handler in self._handlers.items():
            try:
                result = handler(screenshot)
                if result is not None:
                    results[task_type] = result
            except Exception:
                pass
        return results

    def list_handlers(self) -> list[str]:
        return sorted(self._handlers.keys())
