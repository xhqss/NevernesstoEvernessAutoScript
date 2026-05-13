"""
Task exceptions - generic exceptions for automation tasks.
"""


class TaskError(Exception):
    """Base exception for all task errors."""
    pass


class WaitTimeoutError(TaskError):
    """Timeout while waiting for a condition."""
    pass


class CaptureError(TaskError):
    """Screenshot capture failed."""
    pass


class FeatureNotFoundError(TaskError):
    """Feature/template not found in image."""
    pass


class TaskDisabledError(TaskError):
    """Task is disabled."""
    pass


class FinishedError(TaskError):
    """Task finished successfully (control flow)."""
    pass
