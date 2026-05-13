"""
PaddleOCR engine wrapper.
"""

from module.ocr.ocr_base import OcrBase
from module.ocr.ocr_result import OcrResult


class PaddleOcrEngine(OcrBase):
    """PaddleOCR engine."""
    
    def __init__(self, lang=None):
        super().__init__(lang or 'ch')
        self._ocr = None
    
    def _lazy_init(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                lang=self.lang,
                use_angle_cls=True,
                show_log=False
            )
    
    def ocr(self, image):
        self._lazy_init()
        import numpy as np
        result = self._ocr.ocr(image, cls=True)
        
        outputs = []
        if result and result[0]:
            for line in result[0]:
                position = line[0]
                text, confidence = line[1]
                x = min(p[0] for p in position)
                y = min(p[1] for p in position)
                w = max(p[0] for p in position) - x
                h = max(p[1] for p in position) - y
                outputs.append(OcrResult(
                    text=text, confidence=confidence,
                    box=(int(x), int(y), int(w), int(h))
                ))
        
        return outputs
