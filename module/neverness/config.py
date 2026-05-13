"""Game configuration for Neverness to Everness."""
import os

from module.neverness.device.interaction import NTEInteraction
from module.neverness.process_feature import process_feature

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")

KEY_CONFIG = {"Skill Key": "e", "Ultimate Key": "q", "Arc Key": "r"}
MONTHLY_CARD_CONFIG = {"Check Monthly Card": True, "Monthly Card Time": 5}
SOUND_TRIGGER_CONFIG = {"Enable Sound Trigger": True, "Dodge All Attacks": True,
                        "Dodge Threshold": 0.13, "Counter Attack Threshold": 0.12}


def make_config():
    from module.neverness.scene.scene import NTEScene
    return {
        "custom_tasks": True, "debug": False, "use_gui": True,
        "config_folder": "config", "gui_title": "NevernesstoEvernessAutoScript",
        "gui_icon": "icons/icon.png",
        "window_size": {"width": 1200, "height": 800, "min_width": 600, "min_height": 450},
        "start_timeout": 120, "screenshots_folder": "screenshots",
        "global_configs": [KEY_CONFIG, MONTHLY_CARD_CONFIG, SOUND_TRIGGER_CONFIG],
        "ocr": {"default": {"lib": "onnxocr", "auto_simplify": True, "params": {"use_openvino": True}}},
        "windows": {"exe": "HTGame.exe", "hwnd_class": "UnrealWindow",
                     "interaction": [NTEInteraction],
                     "capture_method": ["WGC", "BitBlt_RenderFull"],
                     "check_hdr": False, "force_no_hdr": False, "require_bg": True, "start_exe": False},
        "supported_resolution": {"ratio": "16:9", "min_size": (1280, 720)},
        "template_matching": {"coco_feature_json": os.path.join(_ASSETS_DIR, "coco_annotations.json"),
                              "default_horizontal_variance": 0.002, "default_vertical_variance": 0.002,
                              "default_threshold": 0.7, "feature_processor": process_feature},
        "template_tab": {"generate_label_enum": True, "label_enum_relative_path": "module/neverness/Labels"},
        "scene": [NTEScene],
        "onetime_tasks": [["module.neverness.task.launcher", "LauncherTask"],
                          ["module.neverness.task.daily", "DailyTask"],
                          ["module.neverness.task.fishing", "FishingTask"],
                          ["module.neverness.task.anomaly", "AnomalyTask"],
                          ["module.neverness.task.rhythm", "RhythmTask"]],
        "trigger_tasks": [["module.neverness.task.trigger.combat", "AutoCombatTask"],
                          ["module.neverness.task.trigger.dialog", "SkipDialogTask"],
                          ["module.neverness.task.trigger.travel", "FastTravelTask"],
                          ["module.neverness.task.trigger.heist", "HeistTask"]],
        "custom_tabs": [["module.neverness.ui.hub", "CharHubTab"]],
        "my_app": ["module.neverness.globals", "Globals"],
        "version": "dev",
        "links": {"github": "https://github.com/example/NevernesstoEvernessAutoScript"},
        "about": "<p>NevernesstoEvernessAutoScript - built on al-script</p>",
    }
