from taskflow.errors import PermanentError
from taskflow.events import EventLog
from taskflow.models import Task
from taskflow.worker import Worker


def test_successful_task_completes_once():
    events = EventLog()
    worker = Worker(events)
    task = Task("t-success", lambda: 42)
    worker.run(task)
    assert task.status == "completed"
    assert task.result == 42
    assert task.attempts == 1
    assert [event["type"] for event in events.events] == ["completed"]


def test_permanent_error_is_not_retried():
    events = EventLog()
    worker = Worker(events)
    task = Task("t-permanent", lambda: (_ for _ in ()).throw(PermanentError("invalid input")))
    worker.run(task)
    assert task.status == "failed"
    assert task.attempts == 1
    assert [event["type"] for event in events.events] == ["failed"]
