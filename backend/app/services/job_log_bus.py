"""In-process pub/sub for job logs (used by the SSE endpoint).

This is intentionally simple: each subscriber gets its own
``asyncio.Queue`` and the publisher fan-outs every entry to every
subscriber for a job. Subscribers that stop reading are dropped on the
next publish via a non-blocking put attempt.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator

from app.db.models import JobLogLevel


@dataclass(frozen=True)
class LogEvent:
    job_id: int
    level: JobLogLevel
    message: str
    created_at: datetime


@dataclass
class JobLogBus:
    _subscribers: dict[int, set[asyncio.Queue[LogEvent | None]]] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def publish(self, event: LogEvent) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(event.job_id, ()))
        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def close(self, job_id: int) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(job_id, ()))
        for queue in queues:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

    async def subscribe(self, job_id: int) -> AsyncIterator[LogEvent]:
        queue: asyncio.Queue[LogEvent | None] = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.setdefault(job_id, set()).add(queue)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            async with self._lock:
                subscribers = self._subscribers.get(job_id)
                if subscribers is not None:
                    subscribers.discard(queue)
                    if not subscribers:
                        self._subscribers.pop(job_id, None)


_global_bus = JobLogBus()


def get_job_log_bus() -> JobLogBus:
    return _global_bus
