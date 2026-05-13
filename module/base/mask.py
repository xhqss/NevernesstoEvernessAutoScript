import cv2
import numpy as np


def mask_area(image, area):
    """Mask (black out) an area in the image."""
    result = image.copy()
    x1, y1, x2, y2 = area
    result[y1:y2, x1:x2] = 0
    return result


def mask_keep_area(image, area):
    """Keep only the specified area, mask everything else."""
    result = np.zeros_like(image)
    x1, y1, x2, y2 = area
    result[y1:y2, x1:x2] = image[y1:y2, x1:x2]
    return result


def overlay_mask(image, mask, color=(0, 0, 0)):
    """Overlay mask on image with given color."""
    result = image.copy()
    result[mask > 0] = color
    return result
