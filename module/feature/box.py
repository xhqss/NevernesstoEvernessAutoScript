"""
Bounding box for detected features.
Enhanced with utilities from ok-script ok/feature/Box.py
"""


class Box:
    """
    Bounding box for detected features.

    Args:
        x: Left x coordinate.
        y: Top y coordinate.
        width: Width of box.
        height: Height of box.
        confidence: Detection confidence (0-1).
        name: Feature name.
    """

    def __init__(self, x=0, y=0, width=0, height=0, confidence=0, name=''):
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)
        self.confidence = confidence
        self.name = name

    @property
    def area(self):
        """Return (ul_x, ul_y, br_x, br_y)."""
        return (self.x, self.y,
                self.x + self.width,
                self.y + self.height)

    @property
    def center(self):
        """Return center point (cx, cy)."""
        return (self.x + self.width // 2,
                self.y + self.height // 2)

    @property
    def left(self):
        return self.x

    @property
    def top(self):
        return self.y

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    def scale(self, factor_x, factor_y=None):
        """Scale box by factors."""
        if factor_y is None:
            factor_y = factor_x
        return Box(
            x=int(self.x * factor_x),
            y=int(self.y * factor_y),
            width=int(self.width * factor_x),
            height=int(self.height * factor_y),
            confidence=self.confidence,
            name=self.name
        )

    def offset(self, dx, dy):
        """Offset box by (dx, dy)."""
        return Box(
            x=self.x + int(dx),
            y=self.y + int(dy),
            width=self.width,
            height=self.height,
            confidence=self.confidence,
            name=self.name
        )

    def intersects(self, other):
        """Check if this box intersects with another box."""
        return (self.left < other.right and self.right > other.left and
                self.top < other.bottom and self.bottom > other.top)

    def intersection_area(self, other):
        """Calculate intersection area with another box."""
        x_overlap = max(0, min(self.right, other.right) - max(self.left, other.left))
        y_overlap = max(0, min(self.bottom, other.bottom) - max(self.top, other.top))
        return x_overlap * y_overlap

    def contains_point(self, x, y):
        """Check if box contains a point."""
        return (self.left <= x <= self.right and
                self.top <= y <= self.bottom)

    def __repr__(self):
        return (f'Box(name={self.name}, x={self.x}, y={self.y}, '
                f'w={self.width}, h={self.height}, conf={self.confidence:.2f})')

    def __bool__(self):
        return self.width > 0 and self.height > 0


def find_boxes_by_name(boxes, name):
    """Filter boxes by name."""
    return [b for b in boxes if b.name == name]


def find_box_by_name(boxes, name):
    """Find first box by name."""
    for b in boxes:
        if b.name == name:
            return b
    return None


def find_highest_confidence_box(boxes):
    """Find box with highest confidence."""
    if not boxes:
        return None
    return max(boxes, key=lambda b: b.confidence)


def sort_boxes(boxes, key='x'):
    """Sort boxes by x or y coordinate."""
    if key == 'x':
        return sorted(boxes, key=lambda b: b.x)
    elif key == 'y':
        return sorted(boxes, key=lambda b: b.y)
    elif key == 'confidence':
        return sorted(boxes, key=lambda b: b.confidence, reverse=True)
    return boxes


def relative_box(x, y, to_x, to_y, screen_width, screen_height):
    """Create a box relative to screen dimensions (0-1 range)."""
    return Box(
        x=int(x * screen_width),
        y=int(y * screen_height),
        width=int((to_x - x) * screen_width),
        height=int((to_y - y) * screen_height)
    )


def crop_image(image, box):
    """Crop image using a Box."""
    if image is None or box is None:
        return None
    x1, y1, x2, y2 = box.area
    h, w = image.shape[:2]
    x1 = max(0, min(x1, w))
    y1 = max(0, min(y1, h))
    x2 = max(0, min(x2, w))
    y2 = max(0, min(y2, h))
    if x2 <= x1 or y2 <= y1:
        return None
    return image[y1:y2, x1:x2]


def average_width(boxes):
    """Calculate average width of a list of boxes."""
    if not boxes:
        return 0
    return sum(b.width for b in boxes) // len(boxes)


def average_height(boxes):
    """Calculate average height of a list of boxes."""
    if not boxes:
        return 0
    return sum(b.height for b in boxes) // len(boxes)


def find_boxes_within_boundary(boxes, boundary_box):
    """Filter boxes that are within a boundary box."""
    bx1, by1, bx2, by2 = boundary_box.area
    result = []
    for box in boxes:
        if (box.left >= bx1 and box.top >= by1 and
                box.right <= bx2 and box.bottom <= by2):
            result.append(box)
    return result


def get_bounding_box(boxes):
    """Get the bounding box that contains all given boxes."""
    if not boxes:
        return Box(0, 0, 0, 0)
    x = min(b.left for b in boxes)
    y = min(b.top for b in boxes)
    w = max(b.right for b in boxes) - x
    h = max(b.bottom for b in boxes) - y
    return Box(x, y, w, h)
