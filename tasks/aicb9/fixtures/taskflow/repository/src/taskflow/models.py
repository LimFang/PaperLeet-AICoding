from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Task:
    task_id: str
    handler: Callable[[], Any]
    max_retries: int = 2
    attempts: int = 0
    status: str = "queued"
    result: Any = None
    error: str | None = None
    next_delay_s: float | None = None
