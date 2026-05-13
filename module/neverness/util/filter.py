import cv2

from module.neverness import text_white_color
from module.neverness.util import image as iu

dialog_white_color = {"r": (220, 240), "g": (220, 240), "b": (220, 240)}
lv_white_color = {"r": (235, 255), "g": (235, 255), "b": (235, 255)}
lv_red_color = {"r": (235, 255), "g": (0, 1), "b": (0, 1)}


def isolate_cd_to_black(cv_image):
    return iu.create_color_mask(cv_image, text_white_color, invert=True)


def isolate_lv_to_white(cv_image):
    cv_image = iu.restore_world_brightness(cv_image)
    mw = iu.create_color_mask(cv_image, lv_white_color, to_bgr=False)
    mr = iu.create_color_mask(cv_image, lv_red_color, to_bgr=False)
    return iu.morphology_mask(cv2.bitwise_or(mw, mr), to_bgr=False)


def isolate_dialog_to_white(cv_image):
    return iu.create_color_mask(cv_image, dialog_white_color)


def current_char_filter(cv_image):
    return iu.filter_by_hsv(cv_image, iu.HSVRange((150, 180, 120), (179, 225, 255)), return_mask=True)
