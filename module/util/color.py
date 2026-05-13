"""
Color utilities for image analysis.
Adapted from ok-script ok/util/color.py
"""

import cv2
import numpy as np


def mask_white(image):
    """Create a mask where white pixels (R>200, G>200, B>200) are True."""
    if len(image.shape) == 3:
        return np.all(image > 200, axis=2)
    return image > 200


def is_pure_black(image, threshold=5):
    """Check if an image is almost pure black."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image
    return np.max(gray) <= threshold


def find_color_rectangles(image, lower_color, upper_color):
    """
    Find rectangles of a specific color range in the image.

    Args:
        image: numpy array (RGB).
        lower_color: (r, g, b) lower bound.
        upper_color: (r, g, b) upper bound.

    Returns:
        list: [(x, y, w, h), ...] bounding rectangles.
    """
    lower = np.array(lower_color, dtype=np.uint8)
    upper = np.array(upper_color, dtype=np.uint8)
    mask = cv2.inRange(image, lower, upper)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rectangles = []
    for cnt in contours:
        if cv2.contourArea(cnt) > 4:
            x, y, w, h = cv2.boundingRect(cnt)
            rectangles.append((x, y, w, h))
    return rectangles


def get_mask_in_color_range(image, lower_color, upper_color):
    """Get binary mask for pixels within a color range."""
    lower = np.array(lower_color, dtype=np.uint8)
    upper = np.array(upper_color, dtype=np.uint8)
    return cv2.inRange(image, lower, upper)


def color_range_to_bound(color, range_val=10):
    """Convert a center color to lower/upper bounds with tolerance."""
    color = np.array(color, dtype=np.uint8)
    lower = np.clip(color - range_val, 0, 255)
    upper = np.clip(color + range_val, 0, 255)
    return tuple(lower), tuple(upper)


def calculate_color_percentage(image, lower_color, upper_color):
    """Calculate what percentage of image pixels are in the given color range."""
    mask = get_mask_in_color_range(image, lower_color, upper_color)
    total = mask.size
    if total == 0:
        return 0.0
    return np.count_nonzero(mask) / total


def count_pixels_in_color_range(image, lower_color, upper_color):
    """Count pixels within a color range."""
    mask = get_mask_in_color_range(image, lower_color, upper_color)
    return int(np.count_nonzero(mask))


def get_pixel_color(image, x, y):
    """Get the color of a single pixel."""
    return tuple(image[y, x])


def average_color(image, area=None):
    """Get average color of the entire image or a region."""
    if area is not None:
        x1, y1, x2, y2 = area
        roi = image[y1:y2, x1:x2]
    else:
        roi = image
    if roi.size == 0:
        return 0, 0, 0
    mean = np.mean(roi, axis=(0, 1))
    return tuple(np.rint(mean).astype(int))


def is_color_similar(c1, c2, tolerance=10):
    """Check if two RGB colors are similar."""
    return all(abs(int(a) - int(b)) <= tolerance for a, b in zip(c1, c2))
