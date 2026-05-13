def function_drop(rate=0.5, default=None):
    """Randomly execute/skip a function for testing."""
    import random
    def decorator(func):
        def wrapper(*args, **kwargs):
            if random.random() < rate:
                return func(*args, **kwargs)
            else:
                return default
        return wrapper
    return decorator
