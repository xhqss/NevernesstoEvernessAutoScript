"""
OCR (Optical Character Recognition) module.
Provides unified interface for various OCR engines.
"""

import numpy as np

from module.base.utils import crop, load_image
from module.ocr.engine import OcrEngine
from module.ocr.ocr_result import OcrResult
from module.util.logger import logger


class Ocr:
    """
    OCR class for text recognition on game screenshots.
    Supports multiple OCR engines.
    
    Args:
        buttons: Area(s) to perform OCR on.
        name: Name for this OCR instance.
        letter: Expected letter color (for preprocessing).
        threshold: Binarization threshold.
        alphabet: Valid characters string.
        engine: OCR engine name ('default', 'cnocr', 'paddle', etc.)
        lang: Language for OCR engine.
    """
    
    def __init__(self, buttons, name=None, letter=(255, 255, 255),
                 threshold=128, alphabet=None, engine='default', lang=None):
        self.buttons = buttons if isinstance(buttons, (list, tuple)) else [buttons]
        self.name = name or 'ocr'
        self.letter = letter
        self.threshold = threshold
        self.alphabet = alphabet
        self._engine_name = engine
        self._lang = lang
        self._engine = None
    
    @property
    def engine(self):
        if self._engine is None:
            try:
                self._engine = OcrEngine.create(self._engine_name, self._lang)
            except ValueError as e:
                logger.warning(f'{e} Using fallback OCR.')
                self._engine = None
        return self._engine
    
    def ocr(self, image):
        """
        Perform OCR on the given image.
        
        Args:
            image: Screenshot (numpy array).
            
        Returns:
            list: OCR results, each as (text, confidence, box).
        """
        if self.engine is None:
            logger.error('No OCR engine available')
            return []
        
        results = []
        for btn in self.buttons:
            if hasattr(btn, 'area'):
                area = btn.area
            else:
                area = btn
            cropped = crop(image, area)
            
            # Preprocess
            processed = self._pre_process(cropped)
            
            # Run OCR
            ocr_results = self.engine.ocr(processed)
            
            # Filter by alphabet
            if self.alphabet and ocr_results:
                ocr_results = self._filter_by_alphabet(ocr_results)
            
            if ocr_results:
                results.append(ocr_results[0].text)
        
        return results
    
    def _pre_process(self, image):
        """Preprocess image for better OCR."""
        if image.size == 0 or image.shape[0] < 5 or image.shape[1] < 5:
            return image
        
        import cv2
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        # Apply threshold
        _, binary = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)
        
        # Convert back to 3-channel for OCR engines that expect it
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
    
    def _filter_by_alphabet(self, results):
        """Filter OCR results to only include allowed characters."""
        if not self.alphabet:
            return results
        filtered = []
        for r in results:
            text = ''.join(c for c in r.text if c in self.alphabet)
            if text:
                filtered.append(OcrResult(
                    text=text, confidence=r.confidence, box=r.box
                ))
        return filtered
    
    def __repr__(self):
        return f'Ocr(name={self.name}, engine={self._engine_name})'


class Digit(Ocr):
    """Digit recognition, returns int (0 on failure)."""
    
    def ocr(self, image):
        results = super().ocr(image)
        if results:
            try:
                return int(''.join(c for c in results[0] if c.isdigit()))
            except ValueError:
                return 0
        return 0


class DigitCounter(Ocr):
    """Count recognition, '14/15' -> (14, 1, 15)."""
    
    def ocr(self, image):
        results = super().ocr(image)
        if results:
            import re
            match = re.search(r'(\d+)\s*/\s*(\d+)', results[0])
            if match:
                current = int(match.group(1))
                total = int(match.group(2))
                remaining = total - current
                return current, remaining, total
        return 0, 0, 0


class Duration(Ocr):
    """Duration recognition, '08:00:00' -> timedelta."""
    
    def ocr(self, image):
        results = super().ocr(image)
        if results:
            from datetime import timedelta
            import re
            match = re.search(r'(\d+):(\d+):(\d+)', results[0])
            if match:
                return timedelta(
                    hours=int(match.group(1)),
                    minutes=int(match.group(2)),
                    seconds=int(match.group(3))
                )
        return None
