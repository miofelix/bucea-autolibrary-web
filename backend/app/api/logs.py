from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from sse_starlette.sse import EventSourceResponse

from app.db.session import get_session
from app.schemas.task import JobLogRead
from app.services.job_log_bus import JobLogBus, get_job_log_bus
from app.services.job_runner import JobRunner


router = APIRouter()


def get_runner(session: Session = Depends(get_session)) -> JobRunner:
    return JobRunner(session)


def get_bus() -> JobLogBus:
    return get_job_log_bus()


@router.get("/{job_id}/logs", response_model=list[JobLogRead])
def list_logs(job_id: int, runner: JobRunner = Depends(get_runner)) -> list[JobLogRead]:
    if runner.get_job(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return [JobLogRead.model_validate(log) for log in runner.get_logs(job_id)]


@router.get("/{job_id}/logs/stream")
async def stream_logs(
    job_id: int,
    runner: JobRunner = Depends(get_runner),
    bus: JobLogBus = Depends(get_bus),
) -> EventSourceResponse:
    if runner.get_job(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    history = runner.get_logs(job_id)

    async def event_source() -> AsyncIterator[dict[str, str]]:
        for log in history:
            yield {
                "event": "log",
                "data": json.dumps(
                    {
                        "id": log.id,
                        "level": log.level.value if hasattr(log.level, "value") else str(log.level),
                        "message": log.message,
                        "created_at": log.created_at.isoformat(),
                    }
                ),
            }
        async for event in bus.subscribe(job_id):
            yield {
                "event": "log",
                "data": json.dumps(
                    {
                        "id": None,
                        "level": event.level.value if hasattr(event.level, "value") else str(event.level),
                        "message": event.message,
                        "created_at": event.created_at.isoformat(),
                    }
                ),
            }

    return EventSourceResponse(event_source())
