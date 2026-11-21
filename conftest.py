"""Algorithm-only pytest fixtures.

AICB-9/benchmark tests do not need Torch or NumPy. Avoid importing the
algorithm-specific pytest plugin when those optional dependencies are absent.
The full algorithm environment still imports the identical plugin as before.
"""
from importlib.util import find_spec

if find_spec("torch") is not None and find_spec("numpy") is not None:
    from paperleet.judge.pytest_plugin import *  # noqa: F401,F403
