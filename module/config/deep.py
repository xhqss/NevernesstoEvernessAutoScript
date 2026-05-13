"""Deep dictionary operations - adapted from Alas module/config/deep.py"""


def deep_get(d, keys, default=None):
    """Get value from nested dict by dot-separated keys."""
    if isinstance(keys, str):
        keys = keys.split('.')
    try:
        for k in keys:
            d = d[k]
        if d is None:
            return default
        return d
    except (KeyError, IndexError, TypeError):
        return default


def deep_set(d, keys, value):
    """Set value in nested dict by keys."""
    if isinstance(keys, str):
        keys = keys.split('.')
    for k in keys[:-1]:
        if k not in d:
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value


def deep_default(d, keys, value):
    """Set default value if key doesn't exist."""
    if deep_get(d, keys) is None:
        deep_set(d, keys, value)


def deep_pop(d, keys, default=None):
    """Pop value from nested dict."""
    if isinstance(keys, str):
        keys = keys.split('.')
    try:
        for k in keys[:-1]:
            d = d[k]
        return d.pop(keys[-1], default)
    except (KeyError, TypeError):
        return default


def deep_iter(d, depth=1, min_depth=1, path=None):
    """Iterate nested dict with path tracking."""
    if path is None:
        path = []
    if depth <= 0:
        yield path, d
        return
    if hasattr(d, 'items'):
        for k, v in d.items():
            new_path = path + [k]
            if min_depth <= len(new_path):
                yield new_path, v
            if depth > 1:
                yield from deep_iter(v, depth - 1, min_depth - 1 if min_depth > 1 else 0, new_path)
