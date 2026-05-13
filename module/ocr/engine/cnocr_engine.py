"""
cnocr engine wrapper.
"""

from module.ocr.ocr_base import OcrBase
from module.ocr.ocr_result import OcrResult


class CnOcrEngine(OcrBase):
    """cnocr OCR engine."""
    
    def __init__(self, lang=None):
        super().__init__(lang)
        self._ocr = None
    
    def _lazy_init(self):
        if self._ocr is None:
            from cnocr import CnOcr
            self._ocr = CnOcr()
    
    def ocr(self, image):
        self._lazy_init()
        import numpy as np
        if isinstance(image, np.ndarray):
            result = self._ocr.ocr(image)
        else:
            result = self._ocr.ocr(np.array(image))
        
        outputs = []
        for item in result:
            text = item.get('text', '')
            confidence = item.get('score', 0)
            position = item.get('position', None)
            if position is not None:
                x = min(p[0] for p in position)
                y = min(p[1] for p in position)
                w = max(p[0] for p in position) - x
                h = max(p[1] for p in position) - y
                box = (x, y, w, h)
            else:
                box = None
            outputs.append(OcrResult(text=text, confidence=confidence, box=box))
        
        return outputs
