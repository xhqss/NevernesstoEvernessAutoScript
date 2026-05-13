from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np
from module.util.color import color_range_to_bound


def binarize_bgr_by_brightness(image, threshold=180, to_bgr=True):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary_mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    if not to_bgr:
        return binary_mask
    return cv2.cvtColor(binary_mask, cv2.COLOR_GRAY2BGR)


def binarize_bgr_by_adaptive_center(image, to_bgr=True):
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    roi = gray[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
    ret, _ = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, binary_mask = cv2.threshold(gray, ret, 255, cv2.THRESH_BINARY)
    if not to_bgr:
        return binary_mask
    return cv2.cvtColor(binary_mask, cv2.COLOR_GRAY2BGR)


def blackout_corners_by_circle(image):
    h, w = image.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (w // 2, h // 2), min(w, h) // 2, 255, thickness=-1)
    return cv2.bitwise_and(image, image, mask=mask)


def binarize_bgr_by_adaptive_brightness(image, ratio_threshold=0.05, offset=20, min_threshold=100, to_bgr=True):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    avg = np.mean(gray)
    candidate = np.clip(avg + offset, min_threshold, 255)
    ratio = np.sum(gray > candidate) / gray.size
    final = candidate if ratio >= ratio_threshold else 255
    _, binary_mask = cv2.threshold(gray, int(final), 255, cv2.THRESH_BINARY)
    if not to_bgr:
        return binary_mask
    return cv2.cvtColor(binary_mask, cv2.COLOR_GRAY2BGR)


def mask_corners(image, ratio_w=0.5555, ratio_h=0.8571, corners=None, to_bgr=True):
    h, w = image.shape[:2]
    aliases = {"top_left": "top_left", "tl": "top_left", "top_right": "top_right", "tr": "top_right",
               "bottom_left": "bottom_left", "bl": "bottom_left", "bottom_right": "bottom_right", "br": "bottom_right"}
    all_c = ("top_left", "top_right", "bottom_left", "bottom_right")
    if corners is None:
        corners = ("top_left", "bottom_right")
    elif isinstance(corners, str) and corners.lower() in ("all", "diamond"):
        corners = all_c
    selected = {aliases[c.lower()] if isinstance(c, str) else c for c in corners}
    xl, xr = int(w * ratio_w), int(w * (1 - ratio_w))
    yt, yb = int(h * ratio_h), int(h * (1 - ratio_h))
    pts = {"top_left": [[0, 0], [xl, 0], [0, yt]], "top_right": [[w, 0], [xr, 0], [w, yt]],
           "bottom_left": [[0, h], [xl, h], [0, yb]], "bottom_right": [[w, h], [xr, h], [w, yb]]}
    contours = [np.array(pts[c], dtype=np.int32) for c in selected]
    white = np.ones(image.shape if to_bgr else image.shape[:2], dtype=np.uint8) * 255
    if not contours:
        return white
    return cv2.fillPoly(white, contours, (0, 0, 0) if to_bgr else 0)


def mask_outside_white_rect(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    x, y, w, h = cv2.boundingRect(gray)
    mask = np.zeros_like(image)
    if w > 0 and h > 0:
        mask[y: y + h, x: x + w] = 255
    return mask


def create_color_mask(cv_image, color_range, invert=False, to_bgr=True):
    lower, upper = color_range_to_bound(color_range)
    mask = cv2.inRange(cv_image, lower, upper)
    if invert:
        mask = cv2.bitwise_not(mask)
    if not to_bgr:
        return mask
    return cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)


@dataclass
class HSVRange:
    lower: np.ndarray
    upper: np.ndarray

    def __init__(self, lower: Tuple[int, int, int], upper: Tuple[int, int, int]):
        self.lower = np.array(np.clip(lower, [0, 0, 0], [179, 255, 255]), dtype=np.uint8)
        self.upper = np.array(np.clip(upper, [0, 0, 0], [179, 255, 255]), dtype=np.uint8)


def filter_by_hsv(image, hsv_range, return_mask=False):
    match_mask = cv2.inRange(cv2.cvtColor(image, cv2.COLOR_BGR2HSV),
                             hsv_range.lower, hsv_range.upper)
    if return_mask:
        return match_mask
    return cv2.bitwise_and(image, image, mask=match_mask)


def adjust_lightness_contrast_lab(img, brightness=0, contrast=0):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2Lab)
    l_ch, a, b = cv2.split(lab)
    factor = 1.0 + (contrast / 100.0) * (2.0 if contrast >= 0 else 1.0)
    lut = np.clip((np.arange(256).astype(np.float32) - 128) * factor + 128 + brightness * 1.28, 0, 255)
    return cv2.cvtColor(cv2.merge((cv2.LUT(l_ch, lut.astype(np.uint8)), a, b)), cv2.COLOR_Lab2BGR)


def morphology_mask(mask, kernel_size=3, closing=False, to_bgr=True):
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    result = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel) if closing else cv2.dilate(mask, kernel, iterations=1)
    if to_bgr and len(result.shape) == 2:
        result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
    return result


def restore_world_brightness(image, percentile=0.99):
    if image is None:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    target = image.shape[0] * image.shape[1] * (1.0 - percentile)
    cnt, robust_max = 0, 255
    for i in range(255, 0, -1):
        cnt += hist[i]
        if cnt >= target:
            robust_max = i
            break
    if 100 < robust_max < 254:
        return cv2.convertScaleAbs(image, alpha=255.0 / robust_max, beta=0)
    return image
