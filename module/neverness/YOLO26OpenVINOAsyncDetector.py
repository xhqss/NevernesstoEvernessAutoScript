import logging
import threading
import time

import cv2
import numpy as np
from module.feature.box import Box

logger = logging.getLogger(__name__)


class YOLO26OpenVINOAsyncDetector:
    def __init__(self, xml_path):
        self.xml_path = xml_path
        self._model = None
        self._lock = threading.Lock()
        self._infer_request = None
        self._latest_result = None
        self._processing = False
        self._input_size = (1536, 896)
        self.latency = 0.0
        self._load_model()

    def _load_model(self):
        try:
            import openvino as ov
            core = ov.Core()
            self._model = core.read_model(self.xml_path)
            self._compiled_model = core.compile_model(self._model, "AUTO")
            self._infer_request = self._compiled_model.create_infer_request()
            logger.info("OpenVINO model loaded: %s", self.xml_path)
        except Exception as e:
            logger.warning("Failed to load OpenVINO model: %s", e)
            self._model = None

    def _preprocess(self, image, box=None):
        if box is not None:
            x1, y1, x2, y2 = box.left, box.top, box.right, box.bottom
            h_img, w_img = image.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_img, x2), min(h_img, y2)
            if x2 <= x1 or y2 <= y1:
                return None
            roi = image[y1:y2, x1:x2]
            offset = (box.x, box.y)
        else:
            roi = image
            offset = (0, 0)
        tw, th = self._input_size
        h, w = roi.shape[:2]
        scale = min(tw / max(w, 1), th / max(h, 1))
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        resized = cv2.resize(roi, (nw, nh))
        canvas = np.full((th, tw, 3), 114, dtype=np.uint8)
        px, py = (tw - nw) // 2, (th - nh) // 2
        canvas[py:py + nh, px:px + nw] = resized
        blob = np.transpose(canvas.astype(np.float32) / 255.0, (2, 0, 1))[np.newaxis, ...]
        return blob, scale, (px, py), offset

    def _postprocess(self, output, scale, paste, offset, threshold, orig_shape):
        if output is None:
            return []
        h_img, w_img = orig_shape[:2]
        px, py = paste
        ox, oy = offset
        results = []
        for det in output[0]:
            if len(det) < 6:
                continue
            x1, y1, x2, y2, conf = det[0], det[1], det[2], det[3], det[4]
            if conf < threshold:
                continue
            x1 = (x1 - px) / scale + ox
            y1 = (y1 - py) / scale + oy
            x2 = (x2 - px) / scale + ox
            y2 = (y2 - py) / scale + oy
            x1, y1 = max(0, min(x1, w_img)), max(0, min(y1, h_img))
            x2, y2 = max(0, min(x2, w_img)), max(0, min(y2, h_img))
            results.append(Box(x=int(x1), y=int(y1), width=int(x2 - x1), height=int(y2 - y1),
                               confidence=float(conf), name="target"))
        return results

    def detect(self, image, box=None, threshold=0.5, label="target", force=False, mask_regions=None):
        if self._model is None:
            return []
        if not force and self._latest_result is not None:
            return self._latest_result
        with self._lock:
            if self._processing:
                return self._latest_result or []
            self._processing = True
        try:
            start = time.time()
            pre = self._preprocess(image, box)
            if pre is None:
                return []
            blob, scale, paste, offset = pre
            result = self._infer_request.infer({0: blob})
            output = list(result.values())[0]
            boxes = self._postprocess(output, scale, paste, offset, threshold, image.shape)
            self._latest_result = boxes
            self.latency = time.time() - start
            return boxes
        except Exception as e:
            logger.debug("OpenVINO detect error: %s", e)
            return self._latest_result or []
        finally:
            self._processing = False

    def detect_sync(self, image, box=None, threshold=0.5, label="target", mask_regions=None):
        return self.detect(image, box=box, threshold=threshold, label=label, force=True)

    def clear_cache(self):
        self._latest_result = None
