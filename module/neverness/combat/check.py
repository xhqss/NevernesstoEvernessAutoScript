"""CombatCheck — faithful port from ok-nte. Combat detection system."""
import logging
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from module.feature.box import Box
from module.util.color import find_color_rectangles

from module.neverness.Labels import Labels
from module.neverness.task.base import BaseNTETask
from module.neverness.util import filter as gf
from module.neverness.util import image as iu

logger = logging.getLogger(__name__)


@dataclass
class CombatSettle:
    time: Optional[float] = None
    force: bool = False


class CombatCheck(BaseNTETask):
    _LV_NORM_SIZE = 32
    _TARGET_MASK_REGIONS = [(0.020, 0.017, 0.145, 0.240)]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._in_animation = False
        self._in_combat = False
        self.skip_sleep_check = False
        self.sleep_check_interval = 0.2
        self.target_enemy_time_out = 3
        self.switch_char_time_out = 5
        self.combat_end_condition = None
        self.cds = {}
        self.find_lv_future = None
        self._lv_async = None
        self._combat_settle = CombatSettle()
        self._lv_feat_L = None
        self._lv_feat_v = None
        self._lv_norm_L = None
        self._lv_norm_v = None
        self._lv_aspect_L = 0
        self._lv_aspect_v = 0
        self._lv_tpl_res = None

    @property
    def in_animation(self):
        return self._in_animation

    @in_animation.setter
    def in_animation(self, value):
        self._in_animation = value

    def reset_to_false(self, reason=""):
        self.cds = {}
        self._in_combat = False
        self._combat_settle = CombatSettle()
        self.find_lv_future = None
        self._lv_async = None
        self.openvino_clear_cache()
        if self.scene:
            self.scene.set_not_in_combat()
        return False

    def get_current_char(self):
        raise NotImplementedError

    def load_chars(self) -> bool:
        raise NotImplementedError

    def is_boss(self):
        def ffn(image):
            return iu.binarize_bgr_by_brightness(image, threshold=180)
        box = self.box_of_screen(0.3582, 0.0215, 0.4808, 0.0569)
        return bool(self.find_one(Labels.boss_lv_text, box=box, frame_processor=ffn))

    def target_enemy(self, wait=True, lv=True):
        if not wait:
            self.middle_click()
            return False
        deadline = time.time() + self.target_enemy_time_out
        while time.time() < deadline:
            if self.is_in_team():
                self.middle_click()
                self.sleep(0.25)
                if self.combat_detect(lv=lv):
                    return True
            self.next_frame()
        return False

    def has_health_bar(self):
        return self._find_red_health_bar()

    def _find_red_health_bar(self):
        min_h = self.height_of_screen(5 / 1440)
        min_w = self.width_of_screen(100 / 2560)
        max_h = min_h * 2.5
        max_w = self.width_of_screen(200 / 2560)
        _frame = iu.filter_by_hsv(self.frame, enemy_health_hsv)
        boxes = find_color_rectangles(_frame, enemy_health_color_red, min_w, min_h, max_w, max_h, box=self.main_viewport)
        return len(boxes) > 0

    def in_combat(self, target=False):
        self.in_sleep_check = True
        try:
            return self._do_check_in_combat(target)
        finally:
            self.in_sleep_check = False

    def _do_check_in_combat(self, target):
        if self._in_animation:
            return True
        if self._in_combat:
            if self.scene and self.scene.in_combat() is not None:
                return self.scene.in_combat()
            if self.is_boss():
                return self.scene.set_in_combat() if self.scene else True
            cd = self.async_combat_detect(exhaustive=(self._combat_settle.time is not None),
                                          force=self._combat_settle.force)
            self._combat_settle.force = False
            if cd is None or cd is True:
                self._combat_settle = CombatSettle()
                return self.scene.set_in_combat() if self.scene else True
            if self._combat_settle.time is None:
                self._combat_settle.time = time.time() + 0.4
            if time.time() < self._combat_settle.time:
                if self.middle_click(interval=0.35):
                    tp = self.thread_pool_executor
                    if tp:
                        def dd():
                            time.sleep(0.25)
                            self._combat_settle.force = True
                        tp.submit(dd)
                return self.scene.set_in_combat() if self.scene else True
            if self.target_enemy(wait=True):
                self._combat_settle = CombatSettle()
                self.find_lv_future = None
                self._lv_async = None
                self.openvino_clear_cache()
                return self.scene.set_in_combat() if self.scene else True
            return self.reset_to_false("target enemy failed")
        else:
            if target and not self.openvino_detect_async(mask_regions=self._TARGET_MASK_REGIONS):
                self.middle_click(after_sleep=0.1)
            in_c = (self.is_boss() or bool(self.find_lv()) or self.has_health_bar()) and (
                self.openvino_detect_async(mask_regions=self._TARGET_MASK_REGIONS))
            if in_c:
                if self.is_boss():
                    self.middle_click()
                self._in_combat = self.load_chars()
                if self._in_combat and self.scene:
                    self.scene.set_in_combat()
                return self._in_combat
        return False

    def combat_detect(self, frame=None, target=True, lv=True):
        frm = frame or self.frame
        if lv and self.find_lv(frame=frm):
            return True
        if target and self.openvino_detect_sync(frame=frm, mask_regions=self._TARGET_MASK_REGIONS):
            return True
        return False

    def async_combat_detect(self, target=True, lv=True, exhaustive=False, force=False):
        frame = self.frame
        lv_ret, target_ret = None, None
        if lv:
            lv_ret = self._find_lv_async(frame=frame, force=force)
            if lv_ret:
                return True
        if target and (exhaustive or (not lv or lv_ret is False)):
            target_ret = self.openvino_detect_async(frame=frame, force=force,
                                                    mask_regions=self._TARGET_MASK_REGIONS)
            if target_ret:
                return True
        if lv_ret is None and target_ret is None:
            return None
        return False

    def _find_lv_async(self, frame=None, force=False):
        if force or self.find_lv_future is None:
            tp = self.thread_pool_executor
            if tp is None:
                return bool(self.find_lv(frame=frame))
            frm = frame or self.frame
            self.find_lv_future = tp.submit(self.find_lv, frame=frm)

            def cb(f):
                if self.find_lv_future is not f:
                    return
                try:
                    self._lv_async = bool(f.result())
                except Exception:
                    self._lv_async = None
                if self.find_lv_future is f:
                    self.find_lv_future = None
            self.find_lv_future.add_done_callback(cb)
        return self._lv_async

    def find_lv(self, frame=None, threshold=0.7):
        if not self._init_lv_templates():
            return []
        frm = frame or self.frame
        if frm is None:
            return []
        box = self.box_of_screen(0.1543, 0, 0.9070, 0.7, name="find_lv")
        roi = box.crop_frame(frm)
        binary = gf.isolate_lv_to_white(roi)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        scale = self.width / 2560.0
        min_area, max_area = (15 * scale) ** 2 * 0.8, (20 * scale) ** 2 * 1.5
        L_cands, v_cands = [], []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if not (min_area <= w * h <= max_area):
                continue
            sol, cx, cy = _extract_fingerprint(cnt, x, y, w, h)
            ar = w / h if h > 0 else 0
            if (abs(sol - self._lv_feat_L[0]) < 0.15 and abs(cx - self._lv_feat_L[1]) < 0.15
                    and abs(cy - self._lv_feat_L[2]) < 0.15):
                iou = _match_iou(self._lv_norm_L, cnt, x, y, w, h, self._LV_NORM_SIZE)
                if self._lv_aspect_L * 0.6 < ar < self._lv_aspect_L * 1.5 and iou > 0.5:
                    L_cands.append({"x": x, "y": y, "w": w, "h": h, "score": iou})
            elif (abs(sol - self._lv_feat_v[0]) < 0.15 and abs(cx - self._lv_feat_v[1]) < 0.15
                  and abs(cy - self._lv_feat_v[2]) < 0.15):
                iou = _match_iou(self._lv_norm_v, cnt, x, y, w, h, self._LV_NORM_SIZE)
                if self._lv_aspect_v * 0.6 < ar < self._lv_aspect_v * 1.5 and iou > 0.5:
                    v_cands.append({"x": x, "y": y, "w": w, "h": h, "score": iou})
        results = []
        for L in L_cands:
            best_v, min_gap = None, float("inf")
            for v in v_cands:
                gap = v["x"] - (L["x"] + L["w"])
                if -(L["w"] * 0.5) <= gap <= (L["h"] * 1.5) and abs(v["y"] - L["y"]) <= L["h"] * 0.5:
                    if gap < min_gap:
                        min_gap, best_v = gap, v
            if best_v:
                conf = (L["score"] + best_v["score"]) / 2.0
                if conf >= threshold:
                    results.append(Box(x=int(box.x + L["x"]), y=int(box.y + min(L["y"], best_v["y"])),
                                       width=int((best_v["x"] + best_v["w"]) - L["x"]),
                                       height=int(max(L["y"] + L["h"], best_v["y"] + best_v["h"]) - min(L["y"], best_v["y"])),
                                       confidence=conf, name="lv"))
        return results

    def _init_lv_templates(self):
        if self._lv_feat_L is not None and self._lv_tpl_res == (self.width, self.height):
            return True
        feat = self.get_feature_by_name(Labels.lv)
        if feat is None:
            return False
        tpl_bin = gf.isolate_lv_to_white(feat.mat)
        contours, _ = cv2.findContours(tpl_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid = [c for c in contours if cv2.boundingRect(c)[2] > 2 and cv2.boundingRect(c)[3] > 2]
        valid.sort(key=lambda c: cv2.boundingRect(c)[0])
        if len(valid) < 2:
            return False
        self._lv_tpl_res = (self.width, self.height)
        xl, yl, wl, hl = cv2.boundingRect(valid[0])
        self._lv_aspect_L = wl / hl
        self._lv_feat_L = _extract_fingerprint(valid[0], xl, yl, wl, hl)
        self._lv_norm_L = _render_norm(valid[0], xl, yl, wl, hl, self._LV_NORM_SIZE)
        xv, yv, wv, hv = cv2.boundingRect(valid[1])
        self._lv_aspect_v = wv / hv
        self._lv_feat_v = _extract_fingerprint(valid[1], xv, yv, wv, hv)
        self._lv_norm_v = _render_norm(valid[1], xv, yv, wv, hv, self._LV_NORM_SIZE)
        return True


enemy_health_hsv = iu.HSVRange((0, 190, 175), (10, 255, 255))
enemy_health_color_red = {"r": (210, 255), "g": (20, 80), "b": (20, 100)}


def _extract_fingerprint(cnt, x, y, w, h):
    m = cv2.moments(cnt)
    if m["m00"] == 0:
        return 0.0, 0.5, 0.5
    sol = cv2.contourArea(cnt) / (w * h)
    cx = (m["m10"] / m["m00"] - x) / w
    cy = (m["m01"] / m["m00"] - y) / h
    return sol, cx, cy


def _render_norm(cnt, x, y, w, h, sz=32):
    img = np.zeros((sz, sz), dtype=np.uint8)
    s = cnt.copy().astype(np.float32)
    s[:, 0, 0] = ((cnt[:, 0, 0] - x) * (sz - 1) / max(w - 1, 1)).astype(np.float32)
    s[:, 0, 1] = ((cnt[:, 0, 1] - y) * (sz - 1) / max(h - 1, 1)).astype(np.float32)
    cv2.drawContours(img, [s.astype(np.int32)], -1, 255, cv2.FILLED)
    return img


def _match_iou(tpl, cnt, x, y, w, h, sz=32):
    cand = _render_norm(cnt, x, y, w, h, sz)
    inter = cv2.countNonZero(cv2.bitwise_and(tpl, cand))
    union = cv2.countNonZero(cv2.bitwise_or(tpl, cand))
    return inter / union if union > 0 else 0.0
