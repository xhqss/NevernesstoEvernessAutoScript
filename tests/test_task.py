"""
Basic test cases for al-script task framework.
Run with: python -m pytest tests/
"""

import unittest


class TestImport(unittest.TestCase):
    """Test that all core modules can be imported."""

    def test_import_button(self):
        from module.base.button import Button, ButtonGrid
        btn = Button(area=(0, 0, 100, 50), color=(255, 255, 255))
        self.assertTrue(btn)

    def test_import_template(self):
        from module.base.template import Template
        self.assertTrue(True)

    def test_import_utils(self):
        from module.base.utils import (
            crop, get_color, color_similar,
            random_rectangle_point, area_offset,
            node2location, location2node
        )
        self.assertEqual(location2node((4, 2)), 'E3')
        self.assertEqual(node2location('E3'), (4, 2))

    def test_import_decorators(self):
        from module.base.decorator import Config, cached_property, timer
        self.assertTrue(True)

    def test_import_box(self):
        from module.feature.box import Box, find_box_by_name, sort_boxes
        b1 = Box(0, 0, 100, 50, 0.9, 'test')
        b2 = Box(10, 10, 100, 50, 0.8, 'test')
        self.assertEqual(find_box_by_name([b1, b2], 'test'), b1)
        sorted_boxes = sort_boxes([b2, b1], key='x')
        self.assertEqual(sorted_boxes[0], b1)

    def test_import_feature(self):
        from module.feature.feature import Feature
        import numpy as np
        f = Feature(mat=np.zeros((50, 50, 3), dtype=np.uint8), name='test')
        self.assertEqual(f.width, 50)
        self.assertEqual(f.height, 50)

    def test_import_ocr(self):
        from module.ocr.ocr import Ocr, Digit, DigitCounter, Duration
        self.assertTrue(True)

    def test_import_device(self):
        from module.device import (
            ADBScreenshot, WindowsGraphicsScreenshot, BitBltScreenshot,
            ADBInteraction, PostMessageInteraction, PyDirectInteraction,
            DeviceManager, TARGET_WIDTH, TARGET_HEIGHT
        )
        self.assertEqual(TARGET_WIDTH, 1280)
        self.assertEqual(TARGET_HEIGHT, 720)

    def test_import_task(self):
        from module.task import (
            TaskBase, ScriptTask, StateTask,
            TaskExecutor, TaskScheduler,
            TaskError, FinishedError
        )
        self.assertTrue(True)

    def test_import_config(self):
        from module.config import AlConfig, deep_get, deep_set
        d = {'a': {'b': 1}}
        self.assertEqual(deep_get(d, 'a.b'), 1)
        deep_set(d, 'a.c', 2)
        self.assertEqual(deep_get(d, 'a.c'), 2)

    def test_import_i18n(self):
        from module.i18n import translator, tr, set_language
        self.assertEqual(tr('Start'), 'Start')

    def test_import_util(self):
        from module.util import (
            Handler, ExitEvent,
            mask_white, is_pure_black,
            check_mutex
        )
        import numpy as np
        white = np.ones((10, 10, 3), dtype=np.uint8) * 255
        self.assertTrue(mask_white(white).all())

        black = np.zeros((10, 10, 3), dtype=np.uint8)
        self.assertTrue(is_pure_black(black))


class TestBox(unittest.TestCase):
    """Test Box class functionality."""

    def test_box_properties(self):
        from module.feature.box import Box
        b = Box(10, 20, 100, 50, 0.95, 'test')
        self.assertEqual(b.center, (60, 45))
        self.assertEqual(b.area, (10, 20, 110, 70))
        self.assertEqual(b.left, 10)
        self.assertEqual(b.top, 20)
        self.assertEqual(b.right, 110)
        self.assertEqual(b.bottom, 70)

    def test_box_scale(self):
        from module.feature.box import Box
        b = Box(10, 20, 100, 50)
        b2 = b.scale(0.5)
        self.assertEqual(b2.width, 50)
        self.assertEqual(b2.height, 25)

    def test_box_intersects(self):
        from module.feature.box import Box
        b1 = Box(0, 0, 100, 100)
        b2 = Box(50, 50, 100, 100)
        b3 = Box(200, 200, 100, 100)
        self.assertTrue(b1.intersects(b2))
        self.assertFalse(b1.intersects(b3))

    def test_box_contains_point(self):
        from module.feature.box import Box
        b = Box(0, 0, 100, 100)
        self.assertTrue(b.contains_point(50, 50))
        self.assertFalse(b.contains_point(150, 50))


class TestUtilities(unittest.TestCase):
    """Test utility functions."""

    def test_color_utilities(self):
        from module.util.color import (
            find_color_rectangles, calculate_color_percentage,
            is_color_similar, color_range_to_bound
        )
        import numpy as np
        # Create a test image with a red rectangle
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[20:50, 30:70] = (255, 0, 0)

        rects = find_color_rectangles(img, (250, 0, 0), (255, 10, 10))
        self.assertGreater(len(rects), 0)

        pct = calculate_color_percentage(img, (250, 0, 0), (255, 10, 10))
        self.assertGreater(pct, 0.0)

        self.assertTrue(is_color_similar((100, 100, 100), (105, 105, 105), 10))
        self.assertFalse(is_color_similar((0, 0, 0), (100, 100, 100), 10))

        lower, upper = color_range_to_bound((100, 100, 100), 20)
        self.assertEqual(lower, (80, 80, 80))
        self.assertEqual(upper, (120, 120, 120))


if __name__ == '__main__':
    unittest.main()
