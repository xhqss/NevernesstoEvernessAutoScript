import os


class Resource:
    """Base class for resource management (file loading, caching)."""
    
    def __init__(self):
        self._resources = []
    
    def resource_add(self, key):
        if isinstance(key, dict):
            for k, v in key.items():
                if v and os.path.exists(v):
                    self._resources.append(v)
        elif key and os.path.exists(key):
            self._resources.append(key)
    
    def resource_release(self):
        self._resources.clear()
    
    @staticmethod
    def parse_property(prop):
        """Parse property - if dict, return first value; else return as-is."""
        if isinstance(prop, dict):
            for k, v in prop.items():
                return v
        return prop
