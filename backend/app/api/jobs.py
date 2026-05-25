from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.errors import ValidationAppError
from app.db.session import get_session
from app.schemas.task import JobRead, JobRunRequest
from app.services.job_runner import JobRequest, JobRunner

router = APIRouter()


def get_job_runner(session: Session = Depends(get_session)) -> JobRunner:
    return JobRunner(session)


@router.get("", response_model=list[JobRead])
def list_jobs(runner: JobRunner = Depends(get_job_runner)) -> list[JobRead]:
    return [JobRead.model_validate(job) for job in runner.list_jobs()]


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: int, runner: JobRunner = Depends(get_job_runner)) -> JobRead:
    job = runner.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return JobRead.model_validate(job)


@router.post("/run", response_model=JobRead)
async def run_job(
    payload: JobRunRequest,
    runner: JobRunner = Depends(get_job_runner),
) -> JobRead:
    if payload.task_id is not None:
        job = await runner.run_task(payload.task_id)
        return JobRead.model_validate(job)
    if payload.task_type is None or payload.library_user_id is None:
        raise ValidationAppError("either task_id or (task_type, library_user_id) is required")
    job = await runner.create_and_run(
        JobRequest(
            task_id=None,
            task_type=payload.task_type,
            library_user_id=payload.library_user_id,
            payload=payload.payload or {},
        )
    )
    return JobRead.model_validate(job)
