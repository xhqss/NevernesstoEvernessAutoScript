from functools import wraps
from typing import Generic, TypeVar

T = TypeVar("T")


class Config:
    """
    Decorator that dispatches different function implementations
    based on configuration values.
    
    Similar to Alas @Config.when() but without AzurLaneConfig dependency.
    """
    func_list = {}

    @classmethod
    def when(cls, **kwargs):
        """
        Args:
            **kwargs: Configuration key-value pairs to match.
            
        Examples:
            @Config.when(PLATFORM='pc')
            def click(self):
                pass
                
            @Config.when(PLATFORM='adb')
            def click(self):
                pass
        """
        options = kwargs

        def decorate(func):
            name = func.__name__
            data = {'options': options, 'func': func}
            if name not in cls.func_list:
                cls.func_list[name] = [data]
            else:
                override = False
                for record in cls.func_list[name]:
                    if record['options'] == data['options']:
                        record['func'] = data['func']
                        override = True
                if not override:
                    cls.func_list[name].append(data)

            @wraps(func)
            def wrapper(self, *args, **kwargs):
                for record in cls.func_list[name]:
                    flag = [value is None or getattr(self.config, key, None) == value
                            for key, value in record['options'].items()]
                    if not all(flag):
                        continue
                    return record['func'](self, *args, **kwargs)
                return func(self, *args, **kwargs)

            return wrapper

        return decorate


class cached_property(Generic[T]):
    """
    Decorator that converts a method into a cached property.
    Delete self.__dict__['attr'] to recalculate.
    """
    def __init__(self, func):
        self.func = func
        self.attrname = func.__name__

    def __set_name__(self, owner, name):
        self.attrname = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        try:
            return instance.__dict__[self.attrname]
        except KeyError:
            result = self.func(instance)
            instance.__dict__[self.attrname] = result
            return result


def timer(func):
    """Decorator that prints function execution time."""
    from module.util.logger import logger
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        import time
        start = time.time()
        result = func(*args, **kwargs)
        cost = (time.time() - start) * 1000
        logger.info(f'{func.__name__} took {cost:.1f}ms')
        return result
    
    return wrapper
