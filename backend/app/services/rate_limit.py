"""Sliding-window rate limiting (in memory: a single API worker, D013).

Keys are always HMAC-hashed by the caller (hash_ip), never raw IPs or emails.
The client IP comes from request.client.host, already resolved by uvicorn's
trusted proxy handling: this module never reads X-Forwarded-For itself.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from typing import Protocol


class RateLimiter(Protocol):
    async def retry_after(self, key: str, limit: int, window_seconds: int) -> int | None:
        """Seconds to wait if `key` already reached `limit` in the window, else None."""
        ...

    async def record(self, key: str, window_seconds: int) -> None: ...

    async def reset(self, key: str) -> None: ...


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    def _prune(self, key: str, window_seconds: int, now: float) -> deque[float]:
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()
        return hits

    async def retry_after(self, key: str, limit: int, window_seconds: int) -> int | None:
        async with self._lock:
            now = time.monotonic()
            hits = self._prune(key, window_seconds, now)
            if len(hits) < limit:
                return None
            return max(1, math.ceil(hits[0] + window_seconds - now))

    async def record(self, key: str, window_seconds: int) -> None:
        async with self._lock:
            now = time.monotonic()
            self._prune(key, window_seconds, now).append(now)

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._hits.pop(key, None)
