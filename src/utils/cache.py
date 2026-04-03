"""Shared caching utilities for OpenClaw Bot.

Provides a simple TTL (Time-To-Live) cache with LRU eviction,
used across intent classifier, websearch MCP, and other modules.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Generic, Optional, TypeVar

V = TypeVar("V")


class TTLCache(Generic[V]):
    """LRU cache with per-entry TTL expiration.

    Args:
        maxsize: Maximum number of entries before LRU eviction.
        ttl: Time-to-live in seconds for each entry.
    """

    def __init__(self, maxsize: int = 500, ttl: float = 300.0) -> None:
        self._data: OrderedDict[str, tuple[V, float]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: str) -> Optional[V]:
        """Get value if present and not expired, else None."""
        if key not in self._data:
            return None
        value, ts = self._data[key]
        if time.monotonic() - ts > self._ttl:
            del self._data[key]
            return None
        # Move to end (most recently used)
        self._data.move_to_end(key)
        return value

    def put(self, key: str, value: V) -> None:
        """Insert or update a value, evicting LRU entries if needed."""
        self._data[key] = (value, time.monotonic())
        self._data.move_to_end(key)
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def clear(self) -> None:
        """Remove all entries."""
        self._data.clear()
