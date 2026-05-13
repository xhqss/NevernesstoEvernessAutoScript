"""
FeatureSet - loads and manages feature templates from PNG files.
Enhanced with better matching, debug support, and asset management.
"""

import glob
import os

import cv2
import numpy as np

from module.base.utils import load_image, image_size
from module.feature.box import Box
from module.feature.feature import Feature
from module.util.logger import logger


class FeatureSet:
    """
    Feature management system.
    Loads template images and provides matching capabilities.

    Features are stored as PNG files in assets directories.
    Each PNG is a template image that can be matched against screenshots.
    """

    def __init__(self, assets_dir='./assets', debug=False,
                 default_threshold=0.85,
                 feature_processor=None):
        self.assets_dir = assets_dir
        self.debug = debug
        self.default_threshold = default_threshold
        self.feature_processor = feature_processor

        self.features = {}  # name -> Feature
        self.buttons = {}   # name -> Button
        self.templates = {}  # name -> Template
        self.load_success = False
        self._processed = set()

    def load_from_assets_py(self, module_name, assets_module):
        """
        Load Button/Template objects from an auto-generated assets.py module.

        Args:
            module_name: Module/subfolder name.
            assets_module: The imported assets.py module.
        """
        for attr_name in dir(assets_module):
            attr = getattr(assets_module, attr_name)
            from module.base.button import Button
            from module.base.template import Template

            if isinstance(attr, Button):
                self.buttons[attr_name] = attr
            elif isinstance(attr, Template):
                self.templates[attr_name] = attr

        self.load_success = True
        logger.info(f'Loaded {len(self.buttons)} buttons, {len(self.templates)} templates from {module_name}')

    def load_from_directory(self, directory, recursive=True, pattern='*.png'):
        """
        Load PNG template images from directory.

        Args:
            directory: Path to assets directory.
            recursive: Search recursively.
            pattern: File pattern to match (default: *.png).
        """
        path_pattern = f'**/{pattern}' if recursive else pattern
        files = glob.glob(os.path.join(directory, path_pattern), recursive=True)

        for file in files:
            name = os.path.splitext(os.path.basename(file))[0].upper()
            try:
                img = load_image(file)
                # Skip if image is not at target resolution
                w, h = image_size(img)
                if w != 1280 and h != 720:
                    # Template images can be any size
                    pass
                self.features[name] = Feature(mat=img, name=name)
            except Exception as e:
                logger.warning(f'Failed to load {file}: {e}')

        self.load_success = True
        logger.info(f'Loaded {len(self.features)} features from {directory}')

    def add_feature(self, name, image, x=0, y=0):
        """Add a feature manually."""
        self.features[name.upper()] = Feature(mat=image, name=name.upper(), x=x, y=y)

    def get_feature(self, name):
        """Get a feature by name."""
        return self.features.get(name.upper())

    def find_feature(self, image, feature_name, threshold=None):
        """
        Find all instances of a feature in the given image.

        Args:
            image: Screenshot (numpy array).
            feature_name: Name of feature to find.
            threshold: Minimum similarity (0-1). Uses default_threshold if None.

        Returns:
            list[Box]: Found boxes sorted by confidence.
        """
        if threshold is None:
            threshold = self.default_threshold

        feature = self.features.get(feature_name.upper())
        if feature is None:
            logger.debug(f'Feature not found: {feature_name}')
            return []

        if feature.mat is None or feature.mat.size == 0:
            return []

        if image is None or image.size == 0:
            return []

        # Ensure feature is not larger than image
        fh, fw = feature.mat.shape[:2]
        ih, iw = image.shape[:2]
        if fh > ih or fw > iw:
            logger.debug(f'Feature {feature_name} is larger than image')
            return []

        result = cv2.matchTemplate(image, feature.mat, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        boxes = []
        for pt in zip(*locations[::-1]):
            box = Box(
                x=pt[0], y=pt[1],
                width=feature.width, height=feature.height,
                confidence=result[pt[1], pt[0]],
                name=feature_name
            )
            boxes.append(box)

        boxes = self._merge_nearby(boxes)
        return sorted(boxes, key=lambda b: b.confidence, reverse=True)

    def find_one(self, image, feature_name, threshold=None):
        """Find the best match for a feature."""
        boxes = self.find_feature(image, feature_name, threshold)
        if boxes:
            return boxes[0]
        return None

    def find_all_features(self, image, threshold=None):
        """
        Find all registered features in an image.

        Returns:
            dict: {feature_name: [Box, ...]}
        """
        results = {}
        for name in self.features:
            boxes = self.find_feature(image, name, threshold)
            if boxes:
                results[name] = boxes
        return results

    def count_feature(self, image, feature_name, threshold=None):
        """Count occurrences of a feature in an image."""
        return len(self.find_feature(image, feature_name, threshold))

    def has_feature(self, image, feature_name, threshold=None):
        """Check if a feature exists in an image."""
        return self.find_one(image, feature_name, threshold) is not None

    @staticmethod
    def _merge_nearby(boxes, distance=5):
        """Merge nearby boxes, keeping the one with highest confidence."""
        if not boxes:
            return []

        sorted_boxes = sorted(boxes, key=lambda b: b.confidence, reverse=True)
        merged = []

        for box in sorted_boxes:
            is_dup = False
            for m in merged:
                if (abs(box.x - m.x) < distance and
                        abs(box.y - m.y) < distance):
                    is_dup = True
                    break
            if not is_dup:
                merged.append(box)

        return merged

    def clear_cache(self):
        """Clear cached features."""
        self.features.clear()
        self.buttons.clear()
        self.templates.clear()
        self._processed.clear()

    def __len__(self):
        return len(self.features)

    def __repr__(self):
        return f'FeatureSet({len(self.features)} features, {len(self.buttons)} buttons)'
