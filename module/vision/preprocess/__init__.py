"""
Spec §11 — Image preprocessing pipeline.

Operations: grayscale, binarize, otsu, denoise, equalize_hist, sharpen.
All operations work on numpy arrays (H×W or H×W×C).
"""

import cv2
import numpy as np


class Preprocessor:
    """Image preprocessing pipeline for vision and OCR."""

    @staticmethod
    def grayscale(image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 2:
            return image
        return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    @staticmethod
    def binarize(image: np.ndarray, threshold: int = 128,
                 maxval: int = 255) -> np.ndarray:
        gray = Preprocessor.grayscale(image)
        _, binary = cv2.threshold(gray, threshold, maxval, cv2.THRESH_BINARY)
        return binary

    @staticmethod
    def otsu(image: np.ndarray) -> np.ndarray:
        gray = Preprocessor.grayscale(image)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        return binary

    @staticmethod
    def denoise(image: np.ndarray, strength: int = 3) -> np.ndarray:
        gray = Preprocessor.grayscale(image)
        return cv2.fastNlMeansDenoising(gray, h=strength)

    @staticmethod
    def equalize_hist(image: np.ndarray) -> np.ndarray:
        gray = Preprocessor.grayscale(image)
        return cv2.equalizeHist(gray)

    @staticmethod
    def sharpen(image: np.ndarray, strength: float = 1.0) -> np.ndarray:
        kernel = np.array([
            [0, -1, 0],
            [-1, 4 + strength, -1],
            [0, -1, 0],
        ], dtype=np.float32)
        gray = Preprocessor.grayscale(image).astype(np.float32)
        sharpened = cv2.filter2D(gray, -1, kernel)
        sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
        return sharpened

    def pipeline(self, image: np.ndarray,
                 ops: list[str] | None = None) -> np.ndarray:
        """Run a sequence of preprocessing ops. Default: grayscale."""
        ops = ops or ["grayscale"]
        result = image
        for op in ops:
            fn = getattr(self, op, None)
            if fn:
                result = fn(result)
        return result
