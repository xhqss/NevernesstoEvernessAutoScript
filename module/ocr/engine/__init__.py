"""
OCR module - multi-engine support.
Provides unified OCR interface with pluggable engines.
"""

from module.ocr.ocr_base import OcrBase
from module.ocr.ocr_result import OcrResult
from module.util.logger import logger


class OcrEngine:
    """OCR engine wrapper - lazy loads and manages OCR engines."""
    
    ENGINES = {}
    
    @classmethod
    def register(cls, name, engine_class):
        """Register an OCR engine."""
        cls.ENGINES[name] = engine_class
    
    @classmethod
    def create(cls, name='default', lang=None):
        """
        Create an OCR engine by name.
        
        Args:
            name: Engine name ('default', 'cnocr', 'paddle', 'rapid', 'dgocr', 'onnx')
            lang: Language code for the engine.
            
        Returns:
            OcrBase instance.
        """
        if name == 'default' or name not in cls.ENGINES:
            # Try cnocr first, fall back to paddle
            if 'cnocr' in cls.ENGINES:
                name = 'cnocr'
            elif 'paddle' in cls.ENGINES:
                name = 'paddle'
            else:
                raise ValueError(f'No OCR engines available. Install cnocr or paddleocr.')
        
        engine_cls = cls.ENGINES[name]
        logger.info(f'Creating OCR engine: {name}')
        return engine_cls(lang=lang)
    
    @classmethod
    def available_engines(cls):
        """Get list of available engine names."""
        return list(cls.ENGINES.keys())
    
    @classmethod
    def auto_register(cls):
        """Auto-detect and register available OCR engines."""
        # Try cnocr
        try:
            from module.ocr.engine.cnocr_engine import CnOcrEngine
            cls.register('cnocr', CnOcrEngine)
            logger.debug('Registered OCR engine: cnocr')
        except ImportError:
            logger.debug('cnocr not available')
        
        # Try paddleocr
        try:
            from module.ocr.engine.paddle_ocr_engine import PaddleOcrEngine
            cls.register('paddle', PaddleOcrEngine)
            logger.debug('Registered OCR engine: paddle')
        except ImportError:
            logger.debug('paddleocr not available')
        
        # Try rapidocr
        try:
            from module.ocr.engine.rapid_ocr_engine import RapidOcrEngine
            cls.register('rapid', RapidOcrEngine)
            logger.debug('Registered OCR engine: rapid')
        except ImportError:
            logger.debug('rapidocr not available')


# Auto-register on import
OcrEngine.auto_register()
