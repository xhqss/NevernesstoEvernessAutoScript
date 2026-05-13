"""
Configuration utilities - adapted from Alas module/config/utils.py
"""

import json
import os
import yaml
from datetime import datetime, timedelta


DEFAULT_TIME = datetime(2020, 1, 1, 0, 0)


def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)


def filepath_argument(filename):
    """Path to argument YAML files."""
    return os.path.join(os.path.dirname(__file__), 'argument', f'{filename}.yaml')


def filepath_args(filename='args'):
    """Path to generated args JSON."""
    return os.path.join(os.path.dirname(__file__), 'argument', f'{filename}.json')


def filepath_config(filename):
    """Path to user config JSON files."""
    from module.util.file import get_path_relative_to_exe
    return get_path_relative_to_exe(f'./config/{filename}.json')


def filepath_i18n(lang):
    """Path to i18n JSON files."""
    return os.path.join(os.path.dirname(__file__), 'i18n', f'{lang}.json')


def read_file(file):
    """Read YAML or JSON file."""
    if not os.path.exists(file):
        return {}
    with open(file, 'r', encoding='utf-8') as f:
        if file.endswith('.yaml'):
            return yaml.safe_load(f) or {}
        else:
            return json.load(f)


def write_file(file, data):
    """Write JSON file."""
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def data_to_type(value, arg=''):
    """Determine HTML input type from value."""
    v = value.get('value')
    if isinstance(v, bool):
        return 'checkbox'
    elif isinstance(v, datetime):
        return 'datetime'
    elif isinstance(v, int):
        return 'input'
    elif isinstance(v, float):
        return 'input'
    elif 'option' in value:
        return 'select'
    elif isinstance(v, str):
        if len(v) > 50:
            return 'textarea'
        return 'input'
    else:
        return 'input'


def dict_to_kv(d, prefix=''):
    """Convert nested dict to flat key=value list."""
    result = []
    for k, v in d.items():
        path = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            result.extend(dict_to_kv(v, path))
        else:
            result.append(f'{path}={v}')
    return result
