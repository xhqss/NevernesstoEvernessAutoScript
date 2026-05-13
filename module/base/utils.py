import random
import re

import cv2
import numpy as np
from PIL import Image

REGEX_NODE = re.compile(r'(-?[A-Za-z]+)(-?\d+)')


def random_normal_distribution_int(a, b, n=3):
    """Generate a normal distribution int within the interval."""
    a = round(a)
    b = round(b)
    if a < b:
        total = 0
        for _ in range(n):
            total += random.randint(a, b)
        return round(total / n)
    else:
        return b


def random_rectangle_point(area, n=3):
    """Choose a random point in an area. (ul_x, ul_y, br_x, br_y)"""
    x = random_normal_distribution_int(area[0], area[2], n=n)
    y = random_normal_distribution_int(area[1], area[3], n=n)
    return x, y


def random_rectangle_vector(vector, box, random_range=(0, 0, 0, 0), padding=15):
    """Place a vector in a box randomly."""
    vector = np.array(vector) + random_rectangle_point(random_range)
    vector = np.round(vector).astype(int)
    half_vector = np.round(vector / 2).astype(int)
    box = np.array(box) + np.append(np.abs(half_vector) + padding, -np.abs(half_vector) - padding)
    center = random_rectangle_point(box)
    start_point = center - half_vector
    end_point = start_point + vector
    return tuple(start_point), tuple(end_point)


def random_line_segments(p1, p2, n, random_range=(0, 0, 0, 0)):
    """Cut a line into multiple segments."""
    return [tuple((((n - index) * p1 + index * p2) / n).astype(int) + random_rectangle_point(random_range))
            for index in range(0, n + 1)]


def ensure_time(second, n=3, precision=3):
    """Ensure to be time. Supports int, tuple, string '10, 30'"""
    if isinstance(second, tuple):
        multiply = 10 ** precision
        result = random_normal_distribution_int(second[0] * multiply, second[1] * multiply, n) / multiply
        return round(result, precision)
    elif isinstance(second, str):
        if ',' in second:
            lower, upper = second.replace(' ', '').split(',')
            return ensure_time((int(lower), int(upper)), n=n, precision=precision)
        if '-' in second:
            lower, upper = second.replace(' ', '').split('-')
            return ensure_time((int(lower), int(upper)), n=n, precision=precision)
        else:
            return int(second)
    else:
        return second


def area_offset(area, offset):
    """Move an area by offset. (ul_x, ul_y, br_x, br_y) + (x, y)"""
    ul_x, ul_y, br_x, br_y = area
    x, y = offset
    return ul_x + x, ul_y + y, br_x + x, br_y + y


def area_pad(area, pad=10):
    """Inner offset an area."""
    ul_x, ul_y, br_x, br_y = area
    return ul_x + pad, ul_y + pad, br_x - pad, br_y - pad


def limit_in(x, lower, upper):
    """Limit x within range (lower, upper)"""
    return max(min(x, upper), lower)


def area_limit(area1, area2):
    """Limit area1 inside area2."""
    return (
        limit_in(area1[0], area2[0], area2[2]),
        limit_in(area1[1], area2[1], area2[3]),
        limit_in(area1[2], area2[0], area2[2]),
        limit_in(area1[3], area2[1], area2[3]),
    )


def area_size(area):
    """Return (width, height) of area."""
    return area[2] - area[0], area[3] - area[1]


def point_in_area(point, area, threshold=0):
    """Check if point is within area (with threshold padding)."""
    x, y = point
    ul_x, ul_y, br_x, br_y = area
    return (ul_x - threshold < x < br_x + threshold) and (ul_y - threshold < y < br_y + threshold)


def area_in_area(area1, area2):
    """Check if area1 is completely inside area2."""
    return (area2[0] <= area1[0] and area2[1] <= area1[1]
            and area1[2] <= area2[2] and area1[3] <= area2[3])


def area_cross_area(area1, area2):
    """Check if area1 and area2 intersect."""
    return (area1[0] <= area2[2] and area1[2] >= area2[0]
            and area1[1] <= area2[3] and area1[3] >= area2[1])


def node2location(node):
    """Convert node string to location tuple. 'E3' -> (4, 2)"""
    match = REGEX_NODE.match(node.upper())
    if match:
        x = ord(match.group(1)) - ord('A')
        y = int(match.group(2)) - 1
        return x, y
    return 0, 0


def location2node(location):
    """Convert location tuple to node string. (4, 2) -> 'E3'"""
    x, y = location
    return f'{chr(65 + x)}{y + 1}'


def image_size(image):
    """Return (width, height) of image."""
    if isinstance(image, np.ndarray):
        return image.shape[1], image.shape[0]
    elif isinstance(image, Image.Image):
        return image.size


def load_image(file):
    """Load image from file, return as np.ndarray (RGB)."""
    if isinstance(file, np.ndarray):
        return file
    if isinstance(file, Image.Image):
        return np.array(file.convert('RGB'))
    image = cv2.imread(file)
    if image is None:
        raise FileNotFoundError(f'Cannot load image: {file}')
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def save_image(image, file):
    """Save image to file."""
    if isinstance(image, np.ndarray):
        if len(image.shape) == 3 and image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        cv2.imwrite(file, image)
    elif isinstance(image, Image.Image):
        image.save(file)


def crop(image, area):
    """Crop image to area. Returns black pixels if out of bounds."""
    if isinstance(image, Image.Image):
        image = np.array(image.convert('RGB'))
    h, w = image.shape[:2]
    x1, y1, x2, y2 = area
    x1 = max(0, min(x1, w))
    y1 = max(0, min(y1, h))
    x2 = max(0, min(x2, w))
    y2 = max(0, min(y2, h))
    if y2 <= y1 or x2 <= x1:
        return np.zeros((1, 1, 3), dtype=np.uint8)
    return image[y1:y2, x1:x2]


def get_color(image, area):
    """Get average color of an area."""
    area_image = crop(image, area)
    if area_image.size == 0:
        return np.array([0, 0, 0], dtype=np.uint8)
    return np.mean(area_image, axis=(0, 1))


def color_similar(color1, color2, threshold=10):
    """Check if two colors are similar (Photoshop magic wand algorithm)."""
    diff = np.array(color1, dtype=int) - np.array(color2, dtype=int)
    return bool(np.max(np.abs(diff)) <= threshold)


def color_similarity(color1, color2):
    """Calculate color difference (Photoshop magic wand). Max of absolute differences."""
    diff = np.array(color1, dtype=int) - np.array(color2, dtype=int)
    return int(np.max(np.abs(diff)))


def color_similarity_2d(image, color):
    """2D color similarity map. OpenCV implementation, ~3x faster than numpy."""
    color = np.array(color, dtype=np.uint8)
    diff = cv2.absdiff(image, color.reshape(1, 1, 3))
    max_diff = np.max(diff, axis=2)
    return 255 - max_diff


def extract_letters(image, letter, threshold=128):
    """Extract letters from image (white text on dark background)."""
    if isinstance(image, Image.Image):
        image = np.array(image)
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY)
    return binary


def extract_white_letters(image, threshold=128):
    """Extract white letters from image."""
    return extract_letters(image, letter=(255, 255, 255), threshold=threshold)


def rgb2luma(image):
    """Convert RGB to luma (grayscale)."""
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    return image


def color_bar_percentage(image, area, prev_color, difference=30):
    """Calculate color bar percentage."""
    bar = crop(image, area)
    h, w = bar.shape[:2]
    count = 0
    for x in range(w):
        col = bar[:, x, :]
        avg = np.mean(col, axis=0)
        if color_similar(avg, prev_color, threshold=difference):
            count += 1
    return count / w


def get_bbox(image):
    """Get bounding box of non-zero pixels in image."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(binary)
    if coords is None:
        return 0, 0, *image_size(image)
    x, y, w, h = cv2.boundingRect(coords)
    return x, y, x + w, y + h
