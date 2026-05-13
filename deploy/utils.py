"""Deploy utilities - YAML helpers, constants, cached_property."""

import os
from typing import Callable, Generic, TypeVar

T = TypeVar("T")

DEPLOY_CONFIG = './config/deploy.yaml'
DEPLOY_TEMPLATE = os.path.join(os.path.dirname(__file__), 'template')


class cached_property(Generic[T]):
    """A property that is only computed once per instance and then replaces itself."""

    def __init__(self, func: Callable[..., T]):
        self.func = func

    def __get__(self, obj, cls) -> T:
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


def poor_yaml_read(file, directory=None):
    """
    Read a simple YAML-like file without pyyaml dependency.
    Returns a dict of top-level key-value pairs.
    """
    if directory and not os.path.isabs(file):
        file = os.path.join(directory, file)
    result = {}
    if not os.path.exists(file):
        return result
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' in line:
                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip()
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                elif value.lower() == 'null' or value == '':
                    value = None
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                elif value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                result[key] = value
    return result


def poor_yaml_write(config, file):
    """Write a dict to a simple YAML file."""
    with open(file, 'w', encoding='utf-8') as f:
        for key, value in config.items():
            if value is None:
                f.write(f'{key}: null\n')
            elif value is True:
                f.write(f'{key}: true\n')
            elif value is False:
                f.write(f'{key}: false\n')
            elif isinstance(value, int):
                f.write(f'{key}: {value}\n')
            elif isinstance(value, str):
                if value.startswith('./'):
                    f.write(f"{key}: '{value}'\n")
                else:
                    f.write(f'{key}: {value}\n')
            else:
                f.write(f'{key}: {value}\n')
