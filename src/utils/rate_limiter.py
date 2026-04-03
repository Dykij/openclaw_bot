"""Async rate limiter for MCP endpoints."""
import asyncio
import time
from typing import Dict


class AsyncRateLimiter:
    """Token bucket rate limiter per endpoint."""

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str = "default") -> bool:
        """Return True if request is allowed, False if rate-limited."""
        async with self._lock:
            now = time.monotonic()
            if key not in self._requests:
                self._requests[key] = []
            # Remove expired entries
            self._requests[key] = [t for t in self._requests[key] if now - t < self.window_seconds]
            if len(self._requests[key]) >= self.max_requests:
                return False
            self._requests[key].append(now)
            return True

    async def wait(self, key: str = "default") -> None:
        """Wait until a request is allowed."""
        while not await self.check(key):
            await asyncio.sleep(0.1)
