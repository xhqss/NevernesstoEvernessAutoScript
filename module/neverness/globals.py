"""Globals singleton for NevernesstoEvernessAutoScript.

Manages ThreadPoolExecutor, OpenVINO model lazy-loading, and sound-context
initialization across the process lifetime.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class _Globals:
    """Process-level singleton holding shared resources."""

    _instance: _Globals | None = None
    _lock = threading.Lock()

    def __new__(cls) -> _Globals:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        # --- Thread pool ---
        self.max_workers: int = 4
        self._executor: ThreadPoolExecutor | None = None

        # --- OpenVINO ---
        self._openvino_model = None
        self._openvino_compiled = None
        self._openvino_loaded: bool = False
        self._openvino_lock = threading.Lock()
        self._openvino_input_size: tuple[int, int] = (640, 640)

        # --- Sound ---
        self._sound_context = None
        self._sound_context_lock = threading.Lock()

        # --- Assets root ---
        self.assets_dir: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets"
        )

    # ------------------------------------------------------------------
    # Thread pool helpers
    # ------------------------------------------------------------------
    @property
    def executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="nte-worker",
            )
        return self._executor

    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        """Submit a callable to the shared thread pool."""
        return self.executor.submit(fn, *args, **kwargs)

    def submit_periodic_task(self, fn: Callable, interval: float) -> None:
        """Submit a task that repeats on the given interval (seconds).

        The callable receives no arguments.  It is rescheduled automatically
        after each invocation completes.
        """
        import time

        def _loop() -> None:
            while True:
                try:
                    fn()
                except Exception:
                    logger.exception("Periodic task %s failed", fn.__name__)
                time.sleep(interval)

        self.executor.submit(_loop)

    def shutdown_executor(self, wait: bool = True) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None

    # ------------------------------------------------------------------
    # OpenVINO lazy loading
    # ------------------------------------------------------------------
    def _ensure_openvino(self) -> None:
        if self._openvino_loaded:
            return
        with self._openvino_lock:
            if self._openvino_loaded:
                return
            try:
                import openvino as ov
            except ImportError:
                logger.warning("OpenVINO not installed – detection unavailable")
                self._openvino_loaded = True
                return

            model_xml = os.path.join(
                self.assets_dir, "openvino", "best.xml"
            )
            model_bin = os.path.join(
                self.assets_dir, "openvino", "best.bin"
            )
            if not os.path.isfile(model_xml) or not os.path.isfile(model_bin):
                logger.warning("OpenVINO model files not found – skipping")
                self._openvino_loaded = True
                return

            try:
                core = ov.Core()
                self._openvino_model = core.read_model(model=model_xml)
                self._openvino_compiled = core.compile_model(
                    self._openvino_model, device_name="CPU"
                )
                logger.info("OpenVINO model loaded from %s", model_xml)
            except Exception:
                logger.exception("Failed to load OpenVINO model")
            finally:
                self._openvino_loaded = True

    def openvino_detect_async(self, image: np.ndarray) -> Future | None:
        """Submit an asynchronous detection request."""
        self._ensure_openvino()
        if self._openvino_compiled is None:
            return None
        return self.submit(self._openvino_detect_sync, image)

    def openvino_detect_sync(self, image: np.ndarray) -> list[dict]:
        """Run synchronous detection.  Blocking call."""
        self._ensure_openvino()
        if self._openvino_compiled is None:
            return []
        return self._openvino_detect_sync(image)

    def _openvino_detect_sync(self, image: np.ndarray) -> list[dict]:
        """Internal synchronous detection worker."""
        ih, iw = image.shape[:2]
        tw, th = self._openvino_input_size

        # Preprocess
        blob = cv2.resize(image, (tw, th))
        blob = blob.transpose((2, 0, 1))  # HWC → CHW
        blob = np.expand_dims(blob, axis=0).astype(np.float32) / 255.0

        infer_request = self._openvino_compiled.create_infer_request()
        output = infer_request.infer({0: blob})
        # Assume first output is detections [N, 6] – x1, y1, x2, y2, conf, cls
        detections = next(iter(output.values()))
        if isinstance(detections, list):
            detections = np.array(detections)

        results: list[dict] = []
        for det in detections:
            x1, y1, x2, y2 = det[:4]
            conf = float(det[4]) if len(det) > 4 else 1.0
            cls_id = int(det[5]) if len(det) > 5 else 0
            # Scale back to image coordinates
            results.append({
                "box": [
                    int(x1 * iw / tw),
                    int(y1 * ih / th),
                    int(x2 * iw / tw),
                    int(y2 * ih / th),
                ],
                "confidence": conf,
                "class_id": cls_id,
            })
        return results

    def openvino_clear_cache(self) -> None:
        """Drop the compiled model to free memory."""
        self._openvino_compiled = None
        self._openvino_model = None
        self._openvino_loaded = False

    # ------------------------------------------------------------------
    # Sound context
    # ------------------------------------------------------------------
    def get_sound_context(self):
        """Lazy-initialise and return the SoundCombatContext singleton."""
        if self._sound_context is not None:
            return self._sound_context
        with self._sound_context_lock:
            if self._sound_context is not None:
                return self._sound_context
            from module.neverness.sound.context import SoundCombatContext
            self._sound_context = SoundCombatContext()
            return self._sound_context

    def shutdown(self) -> None:
        """Graceful shutdown of all subsystems."""
        if self._sound_context is not None:
            try:
                self._sound_context.shutdown()
            except Exception:
                logger.exception("Error shutting down sound context")
        self.shutdown_executor(wait=False)


# Module-level convenience alias
GLOBALS = _Globals()
