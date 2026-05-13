import os

import numpy as np

from module.base.decorator import cached_property
from module.base.utils import (
    area_offset, color_similar, color_similarity_2d, crop, get_color,
    image_size, load_image, point_in_area, random_rectangle_point,
    get_bbox
)


class Button:
    """
    UI button recognized by area + color.
    
    Args:
        area: Color recognition area (ul_x, ul_y, br_x, br_y) or dict per server.
        color: Average color of area (r, g, b) or dict per server.
        button: Click area (ul_x, ul_y, br_x, br_y) or dict per server.
        file: Asset image path or dict per server.
        name: Button name.
    """
    
    def __init__(self, area, color, button=None, file=None, name=None):
        self._area = area if isinstance(area, dict) else {'default': area}
        self._color = color if isinstance(color, dict) else {'default': color}
        self._button = (button if isinstance(button, dict) 
                       else {'default': button or area})
        self._file = (file if isinstance(file, dict) 
                     else {'default': file or ''})
        self._name = name
        
        self._button_offset = None
        self._server = 'default'
        
        self.image = None
    
    def set_server(self, server):
        """Set server for multi-server Button."""
        self._server = server
        return self
    
    @property
    def area(self):
        return self._area.get(self._server, self._area.get('default'))
    
    @property
    def color(self):
        return self._color.get(self._server, self._color.get('default'))
    
    @property
    def _button_raw(self):
        return self._button.get(self._server, self._button.get('default'))
    
    @property
    def button(self):
        if self._button_offset is None:
            return self._button_raw
        else:
            return self._button_offset
    
    @property
    def file(self):
        return self._file.get(self._server, self._file.get('default', ''))
    
    @property
    def name(self):
        if self._name:
            return self._name
        elif self.file:
            return os.path.splitext(os.path.basename(self.file))[0]
        else:
            return 'BUTTON'
    
    def appear_on(self, image, threshold=10):
        """Check if button appears on image via color similarity."""
        image_color = get_color(image, self.area)
        return color_similar(self.color, image_color, threshold=threshold)
    
    def match(self, image, offset=30, threshold=0.85):
        """Template match this button's image on screenshot."""
        from module.base.template import Template
        return Template(self.file).match(image, offset=offset, threshold=threshold)
    
    def match_any(self, image, offset=30, threshold=0.85):
        """Match multiple times and return all results."""
        from module.base.template import Template
        return Template(self.file).match_multi(image, offset=offset, threshold=threshold)
    
    def load_color(self, image):
        """Reload color from screenshot."""
        color = get_color(image, self.area)
        self._color[self._server] = tuple(np.rint(color).astype(int))
    
    def __str__(self):
        return self.name
    
    __repr__ = __str__
    
    def __eq__(self, other):
        return str(self) == str(other)
    
    def __hash__(self):
        return hash(self.name)
    
    def __bool__(self):
        return True


class ButtonGrid:
    """Generate a 2D array of Buttons."""
    
    def __init__(self, origin, delta, button_shape, grid_shape, name=None):
        """
        Args:
            origin: Top-left button coordinates (x, y).
            delta: Spacing between buttons (x, y).
            button_shape: Button size (width, height).
            grid_shape: Grid dimensions (columns, rows).
            name: Template for button names.
        """
        self.origin = origin
        self.delta = delta
        self.button_shape = button_shape
        self.grid_shape = grid_shape
        self.name = name
    
    def __getitem__(self, item):
        """Get button at grid position."""
        from module.base.utils import area_offset
        
        if isinstance(item, tuple):
            x, y = item
        else:
            x, y = item % self.grid_shape[0], item // self.grid_shape[0]
        
        ox, oy = self.origin
        dx, dy = self.delta
        bw, bh = self.button_shape
        area = (ox + x * dx, oy + y * dy, ox + x * dx + bw, oy + y * dy + bh)
        
        if self.name:
            name = f'{self.name}_{x}_{y}'
        else:
            name = f'GRID_{x}_{y}'
        
        return Button(
            area=area,
            color=(0, 0, 0),
            button=area,
            name=name
        )
    
    def __iter__(self):
        for y in range(self.grid_shape[1]):
            for x in range(self.grid_shape[0]):
                yield self[x, y]
    
    def __len__(self):
        return self.grid_shape[0] * self.grid_shape[1]
