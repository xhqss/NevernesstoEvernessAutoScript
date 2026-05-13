"""
Feature wrapper - wraps a numpy image array with metadata.
"""

import numpy as np


class Feature:
    """
    Image feature wrapper.
    
    Args:
        mat: Image as numpy array.
        name: Feature name.
        x: X offset on screen.
        y: Y offset on screen.
    """
    
    def __init__(self, mat, name='', x=0, y=0):
        self.mat = mat
        self.name = name
        self.x = x
        self.y = y
    
    @property
    def width(self):
        return self.mat.shape[1]
    
    @property
    def height(self):
        return self.mat.shape[0]
    
    def __repr__(self):
        return f'Feature(name={self.name}, {self.width}x{self.height})'
