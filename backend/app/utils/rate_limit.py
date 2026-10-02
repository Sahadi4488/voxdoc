"""Per-visitor rate limit: at most `limit` requests per `window_s` seconds per key.

A sliding window: each key keeps a deque of its recent request times, and a
request is allowed while fewer than `limit` of them are newer than `window_s`.
Unlike a fixed window ("10 per clock 10-minute block"), it can't be gamed with
10 requests just before a block ends and 10 just after.

In memory, in one process: it resets on restart and wouldn't be shared by
several worker processes. Fine for one uvicorn process; with several, the
windows would live in Redis.
"""
import math
import threading
import time
from collections import deque
from collections.abc import Callable, Hashable


class RateLimited(Exception):
    """Raised by an endpoint's rate-limit dependency; main.py answers 429 + Retry-After."""

    def __init__(self, retry_after: int, message: str):
        super().__init__(message)
        self.retry_after = retry_after
        self.message = message


class SlidingWindowLimiter:
    def __init__(self, limit: int = 10, window_s: float = 600, clock: Callable[[], float] = time.monotonic):
        """clock: injectable, so tests move time forward without sleeping."""
        if limit < 1:
            raise ValueError("limit must be at least 1")
        self.limit = limit
        self.window_s = window_s
        self.clock = clock
        self._hits: dict[Hashable, deque[float]] = {}
        # def endpoints run in a threadpool: two requests can update one deque at once
        self._lock = threading.Lock()
        self._next_sweep = clock() + window_s

    def check(self, key: Hashable) -> tuple[bool, int]:
        """Counts a request for `key` if it's allowed. Returns (allowed, retry_after):
        whole seconds until the next request would be allowed, 0 when allowed now.
        A refused request isn't counted, so retrying doesn't push the wait back."""
        now = self.clock()
        with self._lock:
            if now >= self._next_sweep:
                self._sweep(now)
            hits = self._hits.setdefault(key, deque())
            self._expire(hits, now)
            if len(hits) >= self.limit:
                return False, max(1, math.ceil(hits[0] + self.window_s - now))
            hits.append(now)
            return True, 0

    def __len__(self) -> int:
        """Keys currently tracked (tests check memory doesn't grow with every visitor)."""
        with self._lock:
            return len(self._hits)

    def _expire(self, hits: deque[float], now: float) -> None:
        while hits and hits[0] <= now - self.window_s:
            hits.popleft()

    def _sweep(self, now: float) -> None:
        """Delete every key whose requests have all expired. Once per window, so a
        visitor who never comes back doesn't keep a deque forever."""
        for key, hits in list(self._hits.items()):
            self._expire(hits, now)
            if not hits:
                del self._hits[key]
        self._next_sweep = now + self.window_s
