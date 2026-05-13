"""
Debug overlay window - semi-transparent overlay on game window.
Shows detected boxes, labels, and debug info in real-time.
Adapted from ok-script ok/gui/overlay/OverlayWindow.py
"""

import cv2
import numpy as np
from PySide6.QtCore import Qt, QRect, QPoint, Signal, Slot
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QImage, QPixmap
from PySide6.QtWidgets import QWidget, QLabel

from module.util.logger import logger


class OverlayWindow(QWidget):
    """
    Semi-transparent overlay window for debugging.
    Renders detected boxes and text on top of the game window.
    """

    def __init__(self, hwnd=0, parent=None):
        super().__init__(parent)
        self._hwnd = hwnd
        self._boxes = []
        self._texts = []
        self._visible = False
        self._opacity = 0.6

        self._init_ui()

    def _init_ui(self):
        """Initialize the overlay window."""
        self.setWindowTitle('al-script Overlay')
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self._label = QLabel(self)
        self._label.setGeometry(self.rect())

    def update_overlay(self, visible, x, y,
                       window_width, window_height,
                       width, height, scaling=1.0):
        """Update overlay position and visibility."""
        self._visible = visible
        if visible:
            self.setGeometry(int(x * scaling), int(y * scaling),
                             int(width * scaling), int(height * scaling))
            self._label.setGeometry(0, 0,
                                    int(width * scaling), int(height * scaling))
            self.show()
            self.raise_()
        else:
            self.hide()

    def set_boxes(self, boxes):
        """Set the list of boxes to display."""
        self._boxes = boxes
        self.update()

    def add_box(self, box, label='', color=(74, 108, 247)):
        """Add a box to display."""
        self._boxes.append((box, label, color))
        self.update()

    def add_text(self, text, x, y, color=(255, 255, 255)):
        """Add text to display."""
        self._texts.append((text, x, y, color))
        self.update()

    def clear(self):
        """Clear all overlays."""
        self._boxes.clear()
        self._texts.clear()
        self.update()

    def paintEvent(self, event):
        """Paint the overlay."""
        if not self._visible:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw boxes
        for item in self._boxes:
            if isinstance(item, tuple):
                box, label, color = item
            else:
                box = item
                label = box.name if hasattr(box, 'name') else ''
                color = (74, 108, 247)

            pen = QPen(QColor(*color), 2)
            painter.setPen(pen)

            if hasattr(box, 'area'):
                x, y, x2, y2 = box.area
            elif isinstance(box, (tuple, list)) and len(box) == 4:
                x, y, x2, y2 = box
            else:
                continue

            painter.drawRect(int(x), int(y), int(x2 - x), int(y2 - y))

            if label:
                painter.setFont(QFont('Consolas', 10))
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(int(x) + 2, int(y) + 14, str(label))

        # Draw texts
        for text, x, y, color in self._texts:
            painter.setFont(QFont('Consolas', 10))
            painter.setPen(QColor(*color))
            painter.drawText(int(x), int(y), str(text))

        # Draw confidence values on boxes
        for item in self._boxes:
            if isinstance(item, tuple):
                box, _, _ = item
            else:
                box = item

            if hasattr(box, 'confidence') and hasattr(box, 'area'):
                x, y, _, _ = box.area
                painter.setFont(QFont('Consolas', 9))
                painter.setPen(QColor(0, 255, 0))
                painter.drawText(int(x) + 2, int(y) - 4,
                                 f'{box.confidence:.2f}')

        painter.end()

    def show_overlay(self):
        """Show the overlay."""
        self._visible = True
        self.show()
        self.raise_()

    def hide_overlay(self):
        """Hide the overlay."""
        self._visible = False
        self.hide()


class ScreenshotViewer(QWidget):
    """Widget that displays the current screenshot with overlay boxes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = None
        self._boxes = []
        self._set_default_image()

    def _set_default_image(self):
        """Set a default empty image."""
        self._image = QPixmap(640, 360)
        self._image.fill(Qt.black)

    def set_image(self, np_image):
        """Set the image from a numpy array."""
        if np_image is None:
            return
        h, w = np_image.shape[:2]
        if len(np_image.shape) == 3:
            if np_image.shape[2] == 3:
                rgb = cv2.cvtColor(np_image, cv2.COLOR_BGR2RGB)
            else:
                rgb = np_image
        else:
            rgb = cv2.cvtColor(np_image, cv2.COLOR_GRAY2RGB)

        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        self._image = QPixmap.fromImage(qimg).scaled(
            640, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.update()

    def set_boxes(self, boxes):
        """Set boxes to draw on the screenshot."""
        self._boxes = boxes
        self.update()

    def paintEvent(self, event):
        """Paint the screenshot with overlay boxes."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        if self._image:
            painter.drawPixmap(self.rect(), self._image)

        # Draw boxes scaled to widget
        if self._boxes and self._image:
            scale_x = self.width() / 640
            scale_y = self.height() / 360

            for box in self._boxes:
                if hasattr(box, 'area'):
                    x, y, x2, y2 = box.area
                    pen = QPen(QColor(74, 108, 247), 2)
                    painter.setPen(pen)
                    painter.drawRect(
                        int(x * scale_x), int(y * scale_y),
                        int((x2 - x) * scale_x), int((y2 - y) * scale_y)
                    )
                    if hasattr(box, 'name'):
                        painter.setFont(QFont('Consolas', 9))
                        painter.setPen(QColor(255, 255, 255))
                        painter.drawText(
                            int(x * scale_x) + 2, int(y * scale_y) + 14,
                            box.name
                        )

        painter.end()

    def clear(self):
        """Clear the display."""
        self._boxes.clear()
        self._set_default_image()
        self.update()
