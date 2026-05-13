"""
al-script - Universal game automation framework.
Built from Alas (AzurLaneAutoScript) architecture with ok-script multi-platform design.
"""

__version__ = "0.1.0"

from module.base.button import Button, ButtonGrid
from module.base.template import Template
from module.base.utils import (
    crop, get_color, color_similar, color_similarity,
    random_rectangle_point, area_offset, area_pad,
    image_size, load_image, save_image,
    point_in_area, area_limit,
    color_similarity_2d, extract_letters, rgb2luma,
    random_normal_distribution_int, random_rectangle_vector,
    random_line_segments, ensure_time, node2location, location2node,
    area_size, area_in_area, area_cross_area,
    extract_white_letters, color_bar_percentage, get_bbox
)
from module.ocr.ocr import Ocr, Digit, DigitCounter, Duration
from module.task.base_task import TaskBase, ScriptTask, StateTask
from module.task.executor import TaskExecutor
from module.task.scheduler import TaskScheduler
from module.task.exceptions import (
    TaskError, WaitTimeoutError, CaptureError,
    FeatureNotFoundError, TaskDisabledError, FinishedError
)
from module.feature.box import Box
from module.feature.feature import Feature
from module.feature.feature_set import FeatureSet
from module.device.device_manager import DeviceManager, TARGET_WIDTH, TARGET_HEIGHT, TARGET_RESOLUTION
from module.i18n import translator, tr, set_language
from module.util.file import (
    get_root_path, get_toolkit_path, get_python_exe,
    get_git_exe, get_adb_exe, get_path_relative_to_exe
)

__all__ = [
    'Button', 'ButtonGrid', 'Template',
    'crop', 'get_color', 'color_similar', 'color_similarity',
    'random_rectangle_point', 'area_offset', 'area_pad',
    'image_size', 'load_image', 'save_image',
    'point_in_area', 'area_limit',
    'color_similarity_2d', 'extract_letters', 'rgb2luma',
    'random_normal_distribution_int', 'random_rectangle_vector',
    'random_line_segments', 'ensure_time', 'node2location', 'location2node',
    'area_size', 'area_in_area', 'area_cross_area',
    'extract_white_letters', 'color_bar_percentage', 'get_bbox',
    'Ocr', 'Digit', 'DigitCounter', 'Duration',
    'TaskBase', 'ScriptTask', 'StateTask',
    'TaskExecutor', 'TaskScheduler',
    'TaskError', 'WaitTimeoutError', 'CaptureError',
    'FeatureNotFoundError', 'TaskDisabledError', 'FinishedError',
    'Box', 'Feature', 'FeatureSet',
    'DeviceManager', 'TARGET_WIDTH', 'TARGET_HEIGHT', 'TARGET_RESOLUTION',
    'translator', 'tr', 'set_language',
    'get_root_path', 'get_toolkit_path', 'get_python_exe',
    'get_git_exe', 'get_adb_exe', 'get_path_relative_to_exe',
]
