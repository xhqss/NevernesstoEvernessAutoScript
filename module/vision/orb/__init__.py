"""
Spec §11 — ORB feature matcher for icon matching.

Full pipeline: detect → describe → match → homography.
Used for icon recognition when template matching is insufficient.
"""

import cv2
import numpy as np

from module.util.logger import logger


class ORBMatcher:
    """ORB feature detection + matching + homography for icon recognition."""

    def __init__(self, n_features: int = 500, match_threshold: float = 0.70):
        self.n_features = n_features
        self.match_threshold = match_threshold
        self._orb = cv2.ORB_create(nfeatures=n_features)
        self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self._templates: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def load_icon(self, name: str, image: np.ndarray):
        """Register an icon template for matching."""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        kp, des = self._orb.detectAndCompute(gray, None)
        if des is None:
            logger.warning(f'ORBMatcher: no features found for "{name}"')
            return
        self._templates[name] = (kp, des, gray)

    def remove_icon(self, name: str):
        self._templates.pop(name, None)

    def match(self, name: str, screenshot) -> tuple | None:
        """Match icon in screenshot. Returns (confidence, rect) or None."""
        entry = self._templates.get(name)
        if entry is None:
            return None
        kp1, des1, _ = entry

        if len(screenshot.shape) == 3:
            gray = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
        else:
            gray = screenshot

        kp2, des2 = self._orb.detectAndCompute(gray, None)
        if des2 is None or len(kp2) < 4:
            return None

        matches = self._matcher.match(des1, des2)
        if len(matches) < 4:
            return None

        matches = sorted(matches, key=lambda m: m.distance)

        # Good matches: distance < 2 * min_distance
        min_dist = matches[0].distance
        good = [m for m in matches if m.distance < max(2 * min_dist, 30)]

        if len(good) < 4:
            return None

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if H is None:
            return None

        inliers = int(mask.sum())
        confidence = inliers / len(good)

        if confidence < self.match_threshold:
            return None

        # Get bounding box
        h_t, w_t = entry[2].shape
        corners = np.float32([[0, 0], [0, h_t], [w_t, h_t], [w_t, 0]]).reshape(-1, 1, 2)
        dst = cv2.perspectiveTransform(corners, H)
        x_min = int(min(dst[:, 0, 0]))
        y_min = int(min(dst[:, 0, 1]))
        x_max = int(max(dst[:, 0, 0]))
        y_max = int(max(dst[:, 0, 1]))

        return (confidence, (x_min, y_min, x_max, y_max))

    def list_icons(self) -> list[str]:
        return sorted(self._templates.keys())

    @property
    def icon_count(self) -> int:
        return len(self._templates)
