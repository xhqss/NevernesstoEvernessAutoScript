import functools


def retry(tries=3, delay=1):
    """Retry decorator with delay."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            last_error = None
            for i in range(tries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if i < tries - 1:
                        time.sleep(delay)
            raise last_error
        return wrapper
    return decorator
