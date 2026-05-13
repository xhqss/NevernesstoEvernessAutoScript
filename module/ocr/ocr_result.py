"""OCR result data class."""


class OcrResult:
    """Result of a single OCR recognition."""
    
    def __init__(self, text='', confidence=0.0, box=None):
        """
        Args:
            text: Recognized text.
            confidence: Recognition confidence (0-1).
            box: Bounding box (x, y, w, h) or (x1,y1,x2,y2,x3,y3,x4,y4).
        """
        self.text = text
        self.confidence = confidence
        self.box = box
    
    def __repr__(self):
        return f'OcrResult(text={self.text!r}, conf={self.confidence:.2f})'
    
    def __str__(self):
        return self.text
