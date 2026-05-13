"""Base OCR engine interface."""


class OcrBase:
    """Abstract base class for OCR engines."""
    
    def __init__(self, lang=None):
        self.lang = lang
    
    def ocr(self, image):
        """
        Perform OCR on an image.
        
        Args:
            image: numpy array (RGB) or PIL Image.
            
        Returns:
            list of OcrResult: Recognized text results.
        """
        raise NotImplementedError
    
    def ocr_single(self, image):
        """
        Perform OCR and return single text string.
        
        Args:
            image: numpy array (RGB) or PIL Image.
            
        Returns:
            str: Recognized text, or empty string.
        """
        results = self.ocr(image)
        if results:
            return results[0].text
        return ''
    
    @property
    def name(self):
        return self.__class__.__name__
