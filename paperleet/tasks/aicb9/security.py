"""Minimize accidental credential forwarding to local task subprocesses.

This is defense in depth, NOT a sandbox: submitted Python code still executes with
the user's operating-system privileges and can access files/network independently.
"""
import os
from typing import Mapping

_SAFE_KEYS = frozenset({
    "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMP", "TEMP", "TMPDIR",
    "SYSTEMROOT", "WINDIR", "PYTHONUTF8", "PYTHONIOENCODING",
    "PYTHONHASHSEED",
})


def task_subprocess_env(
    *,
    pythonpath: str | None = None,
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a small environment without inherited API/cloud credentials.

    Explicitly set only controlled values needed by task testing. In particular,
    never forward the parent's PYTHONPATH, HOME, provider keys, or CI secrets.
    """
    original = os.environ if source is None else source
    env = {key: value for key, value in original.items() if key in _SAFE_KEYS}
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if pythonpath is not None:
        env["PYTHONPATH"] = str(pythonpath)
    return env
