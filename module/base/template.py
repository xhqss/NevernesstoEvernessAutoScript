import os

import cv2
import imageio
import numpy as np

from module.base.decorator import cached_property
from module.base.utils import load_image, rgb2luma, image_size


class Template:
    """Template image for matching. Supports PNG and GIF."""
    
    def __init__(self, file):
        self._file = file if isinstance(file, dict) else {'default': file}
        self._server = 'default'
        self._image = None
        self._image_binary = None
        self._image_luma = None
    
    def set_server(self, server):
        self._server = server
        self._image = None
        self._image_binary = None
        self._image_luma = None
        return self
    
    @property
    def file(self):
        return self._file.get(self._server, self._file.get('default', ''))
    
    @property
    def name(self):
        return os.path.splitext(os.path.basename(self.file))[0].upper()
    
    @cached_property
    def is_gif(self):
        return os.path.splitext(self.file)[1] == '.gif'
    
    @property
    def image(self):
        if self._image is None:
            if self.is_gif:
                self._image = []
                for img in imageio.mimread(self.file):
                    if len(img.shape) == 3:
                        img = img[:, :, :3].copy()
                    else:
                        img = img.copy()
                    img = self.pre_process(img)
                    self._image.extend([img, cv2.flip(img, 1)])
            else:
                self._image = self.pre_process(load_image(self.file))
        return self._image
    
    @property
    def image_binary(self):
        if self._image_binary is None:
            if self.is_gif:
                self._image_binary = []
                for img in self.image:
                    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                    self._image_binary.append(binary)
            else:
                gray = cv2.cvtColor(self.image, cv2.COLOR_RGB2GRAY)
                _, self._image_binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        return self._image_binary
    
    @property
    def image_luma(self):
        if self._image_luma is None:
            if self.is_gif:
                self._image_luma = [rgb2luma(img) for img in self.image]
            else:
                self._image_luma = rgb2luma(self.image)
        return self._image_luma
    
    @image.setter
    def image(self, value):
        self._image = value
    
    def pre_process(self, image):
        """Override in subclass for custom preprocessing."""
        return image
    
    @cached_property
    def size(self):
        if self.is_gif:
            return self.image[0].shape[1], self.image[0].shape[0]
        else:
            return self.image.shape[1], self.image.shape[0]
    
    def match(self, image, similarity=0.85):
        """
        Template match, returns Button if found.
        
        Args:
            image: Screenshot.
            similarity: Minimum similarity (0-1).
            
        Returns:
            Button or None.
        """
        from module.base.button import Button
        
        result = self.match_result(image)
        if result is None:
            return None
        
        similarity_val, (x, y) = result
        if similarity_val < similarity:
            return None
        
        h, w = self.image.shape[:2] if not self.is_gif else self.image[0].shape[:2]
        button = (x, y, x + w, y + h)
        return Button(
            area=button, color=(0, 0, 0), button=button,
            file=self.file, name=self.name
        )
    
    def match_result(self, image):
        """
        Template match, returns (similarity, position).
        
        Args:
            image: Screenshot.
            
        Returns:
            tuple: (similarity, (x, y)) or None.
        """
        if self.is_gif:
            best_sim = -1
            best_pt = None
            for img in self.image:
                res = cv2.matchTemplate(image, img, cv2.TM_CCOEFF_NORMED)
                _, sim, _, pt = cv2.minMaxLoc(res)
                if sim > best_sim:
                    best_sim = sim
                    best_pt = pt
            if best_sim < 0:
                return None
            return best_sim, best_pt
        else:
            res = cv2.matchTemplate(image, self.image, cv2.TM_CCOEFF_NORMED)
            _, sim, _, pt = cv2.minMaxLoc(res)
            return sim, pt
    
    def match_multi(self, image, similarity=0.85):
        """
        Multi-point matching, auto-merge nearby points.
        
        Args:
            image: Screenshot.
            similarity: Minimum similarity (0-1).
            
        Returns:
            list[Button]: List of matched buttons.
        """
        from module.base.button import Button
        
        if self.is_gif:
            results = []
            for img in self.image:
                res = cv2.matchTemplate(image, img, cv2.TM_CCOEFF_NORMED)
                loc = np.where(res >= similarity)
                h, w = img.shape[:2]
                for pt in zip(*loc[::-1]):
                    btn = Button(
                        area=(pt[0], pt[1], pt[0] + w, pt[1] + h),
                        color=(0, 0, 0),
                        button=(pt[0], pt[1], pt[0] + w, pt[1] + h),
                        file=self.file, name=self.name
                    )
                    results.append(btn)
            # Deduplicate nearby matches
            return self._merge_nearby(results)
        else:
            res = cv2.matchTemplate(image, self.image, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= similarity)
            h, w = self.image.shape[:2]
            results = []
            for pt in zip(*loc[::-1]):
                btn = Button(
                    area=(pt[0], pt[1], pt[0] + w, pt[1] + h),
                    color=(0, 0, 0),
                    button=(pt[0], pt[1], pt[0] + w, pt[1] + h),
                    file=self.file, name=self.name
                )
                results.append(btn)
            return self._merge_nearby(results)
    
    @staticmethod
    def _merge_nearby(buttons, distance=5):
        """Merge nearby buttons."""
        if not buttons:
            return []
        merged = [buttons[0]]
        for btn in buttons[1:]:
            last = merged[-1]
            btn_area = btn.area
            last_area = last.area
            if (abs(btn_area[0] - last_area[0]) < distance and 
                abs(btn_area[1] - last_area[1]) < distance):
                continue
            merged.append(btn)
        return merged
    
    def __repr__(self):
        return f'Template({self.name})'
