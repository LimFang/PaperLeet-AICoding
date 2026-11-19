"""Filesystem registry for AICB-9 tasks; independent of the algorithm catalog."""
from pathlib import Path
import os
import re
import yaml


def repo_root() -> Path:
    return Path(os.environ.get("PAPERLEET_ROOT", Path(__file__).resolve().parents[3])).resolve()


def task_root() -> Path:
    return Path(os.environ.get("AICB9_TASK_ROOT", repo_root() / "tasks" / "aicb9")).resolve()


def load_registry(root: Path | None = None) -> list[dict]:
    base = Path(root or task_root()).resolve()
    path = base / "registry.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"AICB-9 registry not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tasks = raw.get("tasks", [])
    seen = set()
    result = []
    for item in tasks:
        identifier = item.get("id", "")
        if not re.fullmatch(r"[A-Z][0-9]{2}", identifier):
            raise ValueError(f"Invalid AICB-9 task id: {identifier!r}")
        if identifier in seen:
            raise ValueError(f"Duplicate AICB-9 task id: {identifier}")
        seen.add(identifier)
        task_file = base / identifier / "task.yaml"
        if not task_file.is_file():
            raise ValueError(f"Missing task specification: {task_file}")
        spec = yaml.safe_load(task_file.read_text(encoding="utf-8")) or {}
        if spec.get("id") != identifier:
            raise ValueError(f"Task id mismatch in {task_file}")
        result.append({**item, **spec, "directory": base / identifier})
    return result


def get_task(identifier: str, root: Path | None = None) -> dict:
    for task in load_registry(root):
        if identifier in (task["id"], task.get("slug"), task.get("number")):
            return task
    raise ValueError(f"Unknown AICB-9 task {identifier!r}")
