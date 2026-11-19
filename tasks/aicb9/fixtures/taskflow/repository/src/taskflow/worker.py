"""Intentionally buggy Worker for AICB-9 C01: transient failures are not retried."""
from .errors import PermanentError


class Worker:
    def __init__(self, event_log=None, base_delay=1.0, max_delay=8.0):
        from .events import EventLog
        self.events = event_log or EventLog()
        self.base_delay = base_delay
        self.max_delay = max_delay

    def run(self, task):
        if task.status not in ("queued", "retry_wait"):
            return task
        task.attempts += 1
        try:
            task.result = task.handler()
            task.status = "completed"
            task.error = None
            task.next_delay_s = None
            self.events.append("completed", task.task_id, task.attempts)
        except PermanentError as exc:
            task.status = "failed"
            task.error = str(exc)
            task.next_delay_s = None
            self.events.append("failed", task.task_id, task.attempts)
        except Exception as exc:
            # BUG: TransientError should enter retry_wait while attempts remain.
            task.status = "failed"
            task.error = str(exc)
            task.next_delay_s = None
            self.events.append("failed", task.task_id, task.attempts)
        return task
