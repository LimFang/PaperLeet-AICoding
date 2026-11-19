class EventLog:
    def __init__(self):
        self.events = []

    def append(self, event_type, task_id, attempt=None):
        self.events.append({"type": event_type, "task_id": task_id, "attempt": attempt})
