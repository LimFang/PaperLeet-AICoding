"""Teaching fixture for A01: fixed-TTL LRU cache with an injectable clock."""
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class Entry:
    value: object
    expires_at: float


class TinyCache:
    def __init__(self, capacity=2, ttl=5):
        if capacity < 1 or ttl < 0:
            raise ValueError("capacity must be positive and ttl non-negative")
        self.capacity = capacity
        self.ttl = ttl
        self._entries = OrderedDict()
        self.last_expired = []
        self.last_evicted = []

    def _expire(self, now):
        expired = [key for key, entry in self._entries.items() if now >= entry.expires_at]
        for key in expired:
            del self._entries[key]
        self.last_expired = expired

    def set(self, key, value, now):
        self.last_expired = []
        self.last_evicted = []
        self._expire(now)
        self._entries.pop(key, None)
        self._entries[key] = Entry(value=value, expires_at=now + self.ttl)
        while len(self._entries) > self.capacity:
            evicted, _ = self._entries.popitem(last=False)
            self.last_evicted.append(evicted)

    def get(self, key, now):
        self.last_evicted = []
        self._expire(now)
        entry = self._entries.get(key)
        if entry is None:
            return None
        self._entries.move_to_end(key)
        return entry.value

    def lru_order(self):
        return list(self._entries.keys())
