class TransientError(Exception):
    """An error that may succeed when retried."""


class PermanentError(Exception):
    """An error that should not be retried."""
