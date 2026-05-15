"""Game configuration for Neverness to Everness."""
import os

from module.neverness.device.interaction import NTEInteraction
from module.neverness.process_feature import process_feature

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")


def _get_config():
    """Lazy-load AlConfig for reading game settings from user JSON."""
    try:
        from module.config.config import AlConfig
        return AlConfig('template')
    except Exception:
        return None


def get_key_config():
    """Read key binding config from user JSON, with hardcoded fallback."""
    config = _get_config()
    if config:
        try:
            return {
                "Skill Key": config.DefaultTask_NTEKeyBinding_SkillKey,
                "Ultimate Key": config.DefaultTask_NTEKeyBinding_UltimateKey,
                "Arc Key": config.DefaultTask_NTEKeyBinding_ArcKey,
            }
        except Exception:
            pass
    return {"Skill Key": "e", "Ultimate Key": "q", "Arc Key": "r"}


def get_monthly_card_config():
    """Read monthly card config from user JSON, with hardcoded fallback."""
    config = _get_config()
    if config:
        try:
            return {
                "Check Monthly Card": config.DefaultTask_NTEMonthlyCard_CheckMonthlyCard,
                "Monthly Card Time": config.DefaultTask_NTEMonthlyCard_MonthlyCardTime,
            }
        except Exception:
            pass
    return {"Check Monthly Card": True, "Monthly Card Time": 5}


def get_sound_trigger_config():
    """Read sound trigger config from user JSON, with hardcoded fallback."""
    config = _get_config()
    if config:
        try:
            return {
                "Enable Sound Trigger": config.DefaultTask_NTESoundTrigger_EnableSoundTrigger,
                "Dodge All Attacks": config.DefaultTask_NTESoundTrigger_DodgeAllAttacks,
                "Dodge Threshold": config.DefaultTask_NTESoundTrigger_DodgeThreshold,
                "Counter Attack Threshold": config.DefaultTask_NTESoundTrigger_CounterAttackThreshold,
            }
        except Exception:
            pass
    return {
        "Enable Sound Trigger": True,
        "Dodge All Attacks": True,
        "Dodge Threshold": 0.13,
        "Counter Attack Threshold": 0.12,
    }


# Backward-compatible aliases (lazy, reads from user JSON config)
KEY_CONFIG = get_key_config()
MONTHLY_CARD_CONFIG = get_monthly_card_config()
SOUND_TRIGGER_CONFIG = get_sound_trigger_config()


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
