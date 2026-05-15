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


def deep_iter(d, depth=3, min_depth=None, path=None):
    """Iterate nested dict yielding key paths and values at target depths.

    Args:
        d: Nested dict to iterate
        depth (int): Maximum depth to traverse
        min_depth (int): Minimum depth to yield at (defaults to depth)

    Yields:
        Tuple[List[str], Any]: Key path and value at target depth
    """
    if min_depth is None:
        min_depth = depth
    if path is None:
        path = []

    if not hasattr(d, 'items'):
        return

    if depth == 1:
        for k, v in d.items():
            yield path + [k], v
        return

    # Process current level
    if min_depth <= 1:
        for k, v in d.items():
            yield path + [k], v

    # Recurse into dict values
    for k, v in d.items():
        if isinstance(v, dict):
            yield from deep_iter(v, depth=depth - 1, min_depth=min_depth - 1,
                                 path=path + [k])
        elif min_depth - 1 <= 0 and depth > 1:
            # Non-dict value at a level we should yield
            pass  # Already yielded above if min_depth <= 1
