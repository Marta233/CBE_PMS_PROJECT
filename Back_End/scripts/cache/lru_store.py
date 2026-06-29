"""Bounded in-memory LRU store with per-entry TTL."""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Any


class LRUMemoryStore:
    def __init__(self, max_size: int):
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max_size = max(1, max_size)
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, payload = entry
            if time.time() > expires_at:
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
            return payload

    def set(self, key: str, payload: Any, ttl: int) -> None:
        with self._lock:
            self._store[key] = (time.time() + ttl, payload)
            self._store.move_to_end(key)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def clear(self) -> int:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def size(self) -> int:
        with self._lock:
            return len(self._store)
