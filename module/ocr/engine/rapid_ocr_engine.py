"""
RapidOCR engine wrapper.
"""

from module.ocr.ocr_base import OcrBase
from module.ocr.ocr_result import OcrResult


class RapidOcrEngine(OcrBase):
    """RapidOCR (onxruntime) engine."""
    
    def __init__(self, lang=None):
        super().__init__(lang)
        self._ocr = None
    
    def _lazy_init(self):
        if self._ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR()
    
    def ocr(self, image):
        self._lazy_init()
        import numpy as np
        result, elapse = self._ocr(image)
        
        outputs = []
        if result:
            for line in result:
                position = line[0]
                text = line[1]
                confidence = line[2] if len(line) > 2 else 0
                x = min(p[0] for p in position)
                y = min(p[1] for p in position)
                w = max(p[0] for p in position) - x
                h = max(p[1] for p in position) - y
                outputs.append(OcrResult(
                    text=text, confidence=confidence,
                    box=(int(x), int(y), int(w), int(h))
                ))
        
        return outputs
