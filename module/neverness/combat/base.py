"""BaseCombatTask — faithful port from ok-nte. Combat automation engine."""
import logging
import random
import time
from typing import List

import cv2
import numpy as np
from module.feature.box import Box
from module.util.color import color_range_to_bound

from module.neverness import text_white_color
from module.neverness.char.base import BaseChar, Element, Priority
from module.neverness.char.factory import get_char_by_name, get_char_by_pos
from module.neverness.char.custom.manager import CustomCharManager
from module.neverness.combat.check import CombatCheck, CombatSettle
from module.neverness.Labels import Labels
from module.neverness.sound.context import SoundCombatContext
from module.neverness.util import filter as gf
from module.neverness.util import image as iu

logger = logging.getLogger(__name__)


class NotInCombatException(Exception):
    pass


class CharDeadException(NotInCombatException):
    pass


class BaseCombatTask(CombatCheck):
    element_ring = (Element.WHITE, Element.GREEN, Element.RED, Element.PURPLE, Element.BLUE, Element.YELLOW)
    _element_template_cache = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chars: list[BaseChar] = []
        self.combat_start = 0
        self.use_ultimate = True
        self.element_ring_reaction_counts = {}
        self.element_ring_index = {e: i for i, e in enumerate(self.element_ring)}
        self.clear_element_ring_reactions()

    @property
    def team_size(self):
        return len(self.chars)

    def clear_element_ring_reactions(self):
        self.element_ring_reaction_counts = {(self.element_ring[i], self.element_ring[(i + 1) % 6]): 0 for i in range(6)}

    def add_freeze_duration(self, start, duration=-1.0, freeze_time=0.1):
        if duration < 0:
            duration = time.time() - start
        if start > 0 and duration > freeze_time:
            now = time.time()
            self.freeze_durations = [i for i in getattr(self, 'freeze_durations', []) if i[0] > now - 60]
            self.freeze_durations = getattr(self, 'freeze_durations', [])
            self.freeze_durations.append((start, duration, freeze_time))

    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        if start < 0:
            return 10000
        to_minus = 0
        for fs, dur, ft in getattr(self, 'freeze_durations', []):
            if start < fs:
                if intro_motion_freeze and ft == -100:
                    ft = 0
                elif ft == -100:
                    continue
                to_minus += dur - ft
        return time.time() - start - to_minus

    def get_current_char(self, raise_exception=False):
        for c in self.chars:
            if c and c.is_current_char:
                return c
        if raise_exception and not self.in_team()[0]:
            self.raise_not_in_combat("cannot find current char")
        return None

    def get_longest_idle_char_index(self):
        if not self.chars:
            return -1
        mt, mi = float("inf"), -1
        for c in self.chars:
            if c.last_switch_time < mt:
                mt, mi = c.last_switch_time, c.index
        return mi

    def raise_not_in_combat(self, message, exception_type=None):
        logger.error(message)
        self.reset_to_false(reason=message)
        raise (exception_type or NotInCombatException)(message)

    def check_combat(self):
        if self._in_combat and not self.in_combat():
            self.raise_not_in_combat("combat check not in combat")

    def combat_once(self, wait_combat_time=200, raise_if_not_found=True):
        self.wait_until(self.in_combat, time_out=wait_combat_time, raise_if_not_found=raise_if_not_found)
        self.load_chars()
        self.switch_to_combat_start_char()
        self.info_set("Combat Count", self.info_get("Combat Count", 0) + 1)
        try:
            while self.in_combat():
                self.get_current_char().perform()
        except CharDeadException:
            raise
        except NotInCombatException as e:
            logger.info("combat_once out of combat: %s", e)
        self.combat_end()

    def combat_end(self):
        SoundCombatContext().update_task(None)
        cc = self.get_current_char(raise_exception=False)
        if cc:
            cc.on_combat_end(self.chars)

    def available(self, name, check_color=True, check_cd=True):
        if check_color:
            box = self.get_box_by_name(f"box_{name}")
            current = 1 if box and box.width and self.calculate_color_percentage(text_white_color, box) > 0 else 0
        else:
            current = 1
        return current > 0 and (not check_cd or not self.has_cd(name))

    def has_cd(self, box_name, char_index=None):
        return False

    def get_ultimate_key(self):
        return self.key_config.get("Ultimate Key", "q") if isinstance(self.key_config, dict) else "q"

    def get_skill_key(self):
        return self.key_config.get("Skill Key", "e") if isinstance(self.key_config, dict) else "e"

    def get_arc_key(self):
        return self.key_config.get("Arc Key", "r") if isinstance(self.key_config, dict) else "r"

    def switch_next_char(self, current_char, post_action=None, free_intro=False):
        if self.team_size <= 1:
            self.click(action_name="switch_char_click", interval=0.1)
            return
        current_char.wait_switch_cd()
        st, hi = self._find_switch_target(current_char, free_intro)
        if st is None or st == current_char:
            return
        self._switch_to_char(st, current_char=current_char, has_intro=hi, post_action=post_action,
                             free_intro=free_intro, retry_intro=True)

    def _find_switch_target(self, current_char, free_intro=False):
        sc = 0
        while True:
            st, hi = self._decide_switch_to(current_char, free_intro)
            if st != current_char:
                return st, hi
            sc += 1
            if sc > 5:
                st = self.chars[self.get_longest_idle_char_index()] if self.chars else None
                if st and st != current_char:
                    return st, hi
            current_char.continues_normal_attack(0.2)

    def _decide_switch_to(self, current_char, free_intro=False, require_intro=False):
        hi = free_intro or current_char.is_cycle_full()
        st = current_char
        if require_intro and not hi:
            return st, hi
        mp = Priority.MIN
        for c in self.chars:
            if c is None:
                continue
            p = Priority.CURRENT_CHAR if c == current_char else c.get_switch_priority(current_char, hi)
            if p > mp or (p == mp and c.last_perform < st.last_perform):
                mp, st = p, c
        return st, hi

    def _switch_to_char(self, switch_to, current_char=None, has_intro=False, post_action=None,
                        free_intro=False, retry_intro=False, time_out=10):
        switch_to.has_intro = has_intro
        ldt = 0.0
        st = time.time()
        while True:
            self.check_combat()
            ct = time.time()
            if self.is_char_at_index(switch_to.index):
                if current_char:
                    current_char.switch_out()
                    if has_intro:
                        current_char.last_outro_time = ct
                switch_to.is_current_char = True
                switch_to.has_intro = has_intro
                break
            if retry_intro and not has_intro and ct - ldt > 0.12:
                ldt = ct
                ns, nh = self._decide_switch_to(current_char, free_intro, require_intro=True)
                if nh and ns != current_char:
                    switch_to, has_intro = ns, nh
                    switch_to.has_intro = True
            if not self.is_in_team():
                if ct - st > self.switch_char_time_out:
                    self.raise_not_in_combat(f"switch too long {current_char} -> {switch_to}")
                self.sleep(0.01)
                continue
            self.click(action_name="switch_char_click", interval=0.25)
            self.sleep(0.001)
            self.send_key(str(switch_to.index + 1), action_name="switch_char_send", interval=0.25)
            if ct - st > time_out:
                self.raise_not_in_combat(f"switch failed {switch_to.char_name}")
            self.sleep(0.01)
        if has_intro and current_char:
            self.record_element_ring_reaction(current_char, switch_to)
        if post_action:
            post_action(switch_to, has_intro)

    def switch_to_combat_start_char(self):
        sc = [c for c in self.chars if c and getattr(c, 'start_combat', False)]
        if not sc:
            return
        st = random.choice(sc)
        cc = self.get_current_char(raise_exception=False)
        if cc == st:
            return
        self._switch_to_char(st, current_char=cc, time_out=self.switch_char_time_out)

    def load_chars(self) -> bool:
        ret = False
        self.load_hotkey()
        it, ci, count = self.in_team()
        if not it or ci == -1:
            return ret
        if count > 4:
            count = 4
        self.clear_element_ring_reactions()
        ft = CustomCharManager().get_fixed_team()
        fs = ft.get("slots", []) if ft.get("enabled", False) else []
        nc = []
        itd = []
        for i in range(count):
            c = self._do_load_char(i, count, fs)
            nc.append(c)
            if c.element is Element.DEFAULT:
                itd.append(i)
        if itd:
            de = self._load_chars_element(itd)
            for i in itd:
                nc[i].element = de.get(i, Element.DEFAULT)
        self.chars = nc
        for c in self.chars:
            if c:
                c.reset_state()
                if c.index == ci:
                    c.is_current_char = True
        if self.team_size > 0:
            self.combat_start = time.time()
            ret = True
            self._apply_sound_config()
        return ret

    def _do_load_char(self, index, count, fixed_slots):
        fs = fixed_slots[index] if index < len(fixed_slots) else {}
        fcn = str(fs.get("char_name", "") or "").strip()
        fcr = str(fs.get("combo_ref", "") or "").strip()
        if fcn:
            return get_char_by_name(self, index, fcn, confidence=1, combo_ref=fcr)
        box = self.get_char_box(index)
        if count == 1 and box:
            box = self._shift_char_ui_box(box, expend=True)
        if box:
            box = box.scale(1.1, 1.1)
        oc = self.chars[index] if index < len(self.chars) else None
        return get_char_by_pos(self, box, index, oc)

    def _load_chars_element(self, indices):
        results = {}
        tes = [Element.BLUE, Element.GREEN, Element.RED, Element.PURPLE, Element.YELLOW, Element.WHITE]
        bb = self.get_box_by_name(Labels.box_char_1)
        if bb is None or not bb.width:
            return results
        if not self._element_template_cache:
            for el in tes:
                img = cv2.imread(f"assets/esper_icons/{el.value}.png", cv2.IMREAD_UNCHANGED)
                if img is not None:
                    if img.shape[2] == 4:
                        b, g, r, a = cv2.split(img)
                        af = a.astype(float)[:, :, np.newaxis] / 255.0
                        img = (cv2.merge([b, g, r]).astype(float) * af).astype(np.uint8)
                    h, w = img.shape[:2]
                    img = cv2.resize(img, (int(w * 0.5), int(h * 0.5)), interpolation=cv2.INTER_NEAREST)
                    tb = iu.binarize_bgr_by_adaptive_center(img)
                    _, mask = cv2.threshold(tb, 127, 255, cv2.THRESH_BINARY)
                    mask = cv2.dilate(mask, np.ones((30, 30), np.uint8), iterations=1)
                    self._element_template_cache[el] = (img, mask)
        for i in indices:
            yo = i * int(self.height * 176 / 1440)
            box = Box(x=bb.x, y=bb.y + yo, width=bb.width, height=bb.height)
            crop = box.crop_frame(self.frame)
            s = 8 * 1440 / self.height
            cr = cv2.resize(crop, (int(crop.shape[1] * s), int(crop.shape[0] * s)), interpolation=cv2.INTER_NEAREST)
            be, ms = Element.DEFAULT, -1.0
            for el in tes:
                td = self._element_template_cache.get(el)
                if td is None:
                    continue
                ti, tm = td
                res = cv2.matchTemplate(cr, ti, cv2.TM_CCOEFF_NORMED, mask=tm)
                res[np.isinf(res)] = 0
                _, mv, _, _ = cv2.minMaxLoc(res)
                if mv > ms:
                    ms, be = mv, el
            results[i] = be
        return results

    def is_cycle_full(self):
        box = self.box_of_screen_scaled(2560, 1440, 944, 1316, width_original=66, height_original=66)
        img = box.crop_frame(self.frame)
        if img is None:
            return False
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        mask = np.zeros((h, w), dtype=np.uint8)
        ct = (w // 2, h // 2)
        or_ = h // 2
        ir = int(or_ * 0.85)
        cv2.circle(mask, ct, or_, 255, -1)
        cv2.circle(mask, ct, ir, 0, -1)
        ring = cv2.bitwise_and(thresh, thresh, mask=mask)
        rs = int(h * 0.1)
        mg = int(h * 0.02)
        tr = ring[mg:mg + rs, (w // 2 - rs // 2):(w // 2 + rs // 2)]
        br = ring[(h - mg - rs):(h - mg), (w // 2 - rs // 2):(w // 2 + rs // 2)]
        td = np.sum(tr == 255)
        bd = np.sum(br == 255)
        return bd > 0 and (td / bd) > 0.9

    def load_hotkey(self):
        for k, v in self.key_config.items():
            self.info_set(k, v)

    def record_element_ring_reaction(self, a, b):
        if a is None or b is None:
            return False
        p = self._get_element_ring_pair(a.element, b.element)
        if p is None:
            return False
        self.element_ring_reaction_counts[p] = self.element_ring_reaction_counts.get(p, 0) + 1
        return True

    def _get_element_ring_pair(self, ea, eb):
        ia, ib = self.element_ring_index.get(ea), self.element_ring_index.get(eb)
        if ia is None or ib is None or ia == ib:
            return None
        sz = len(self.element_ring)
        if (ia + 1) % sz == ib:
            return ea, eb
        if (ib + 1) % sz == ia:
            return eb, ea
        return None

    def _apply_sound_config(self):
        if self.sound_config:
            en = self.sound_config.get("Enable Sound Trigger", True)
            da = self.sound_config.get("Dodge All Attacks", True)
            dt = np.clip(self.sound_config.get("Dodge Threshold", 0.13), 0.0, 1.0)
            ct = np.clip(self.sound_config.get("Counter Attack Threshold", 0.12), 0.0, 1.0)
            SoundCombatContext().update_config(en, da, dt, ct)
        SoundCombatContext().update_task(self)
