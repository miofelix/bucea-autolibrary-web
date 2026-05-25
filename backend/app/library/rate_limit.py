"""Per-endpoint minimum interval rate limiter.

The library system aggressively rate-limits AJAX search; the helper doc
recommends ≥ 3 seconds between queries and ≥ 1 second between paging
requests. We model this as a per-key monotonic timestamp gate with an
injectable clock and sleeper, so tests stay deterministic.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable


DEFAULT_QUERY_INTERVAL = 3.0
DEFAULT_PAGE_INTERVAL = 1.0
DEFAULT_SUBMIT_INTERVAL = 60.0
DEFAULT_GLOBAL_INTERVAL = 0.5


@dataclass
class RateLimiter:
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep
    intervals: dict[str, float] = field(
        default_factory=lambda: {
            "query": DEFAULT_QUERY_INTERVAL,
            "page": DEFAULT_PAGE_INTERVAL,
            "submit": DEFAULT_SUBMIT_INTERVAL,
            "global": DEFAULT_GLOBAL_INTERVAL,
        }
    )
    _last_call: dict[str, float] = field(default_factory=dict, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def acquire(self, key: str = "global") -> float:
        """Wait until ``key`` is allowed to run again. Returns the wait time."""
        interval = self.intervals.get(key, self.intervals.get("global", 0.0))
        async with self._lock:
            now = self.clock()
            last = self._last_call.get(key)
            wait = 0.0
            if last is not None:
                elapsed = now - last
                if elapsed < interval:
                    wait = interval - elapsed
            if wait > 0:
                await self.sleeper(wait)
                now = self.clock()
            self._last_call[key] = now
            return wait

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._last_call.clear()
        else:
            self._last_call.pop(key, None)
