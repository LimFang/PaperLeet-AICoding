"""Retry policy helpers; the Worker currently fails to apply this policy."""
from .errors import TransientError


def is_retryable(error):
    return isinstance(error, TransientError)


def backoff_delay(attempt, base_delay=1.0, max_delay=8.0):
    if attempt < 1:
        raise ValueError("attempt must be positive")
    return min(base_delay * (2 ** (attempt - 1)), max_delay)
