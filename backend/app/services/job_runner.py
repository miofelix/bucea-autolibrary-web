"""Async job runner that maps a Task → LibraryService call.

The runner publishes log lines to :class:`JobLogBus` *and* persists them
into ``job_logs`` so reconnecting clients can replay history.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date as _date, datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import Job, JobLog, JobLogLevel, JobStatus, Task, TaskType
from app.services.job_log_bus import JobLogBus, LogEvent, get_job_log_bus
from app.services.library_service import LibraryService
from app.services.task_service import TaskService


logger = logging.getLogger("autolibrary.jobs")


def _resolve_reservation_date(payload: dict[str, Any]) -> str:
    """Resolve the YYYY-MM-DD a RESERVE task should target at run time.

    An explicit ``date`` field always wins (one-shot jobs and tasks
    saved before the relative-offset UI existed). Otherwise we read
    ``date_offset`` as "days from today" so a scheduled task that runs
    every morning targets the right day each time it fires.
    """
    explicit = str(payload.get("date") or "").strip()
    if explicit:
        return explicit
    raw_offset = payload.get("date_offset")
    if raw_offset is None:
        return ""
    try:
        offset = int(raw_offset)
    except (TypeError, ValueError):
        return ""
    return (_date.today() + timedelta(days=offset)).strftime("%Y-%m-%d")


@dataclass(frozen=True)
class JobRequest:
    task_id: int | None
    task_type: TaskType
    library_user_id: int
    payload: dict[str, Any]


class JobRunner:
    """Glue between the FastAPI request layer, persistence, and LibraryService."""

    def __init__(
        self,
        db_session: Session,
        *,
        library_service: LibraryService | None = None,
        log_bus: JobLogBus | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._db = db_session
        self._settings = settings or get_settings()
        self._library = library_service or LibraryService(db_session, settings=self._settings)
        self._log_bus = log_bus or get_job_log_bus()

    # ------------------------------------------------------------------ public

    def list_jobs(self, *, limit: int = 50) -> list[Job]:
        statement = select(Job).order_by(Job.id.desc()).limit(limit)
        return list(self._db.exec(statement).all())

    def get_job(self, job_id: int) -> Job | None:
        return self._db.get(Job, job_id)

    def get_logs(self, job_id: int) -> list[JobLog]:
        statement = select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.id)
        return list(self._db.exec(statement).all())

    async def create_and_run(self, request: JobRequest) -> Job:
        job = Job(
            task_id=request.task_id,
            task_type=request.task_type,
            library_user_id=request.library_user_id,
            status=JobStatus.PENDING,
        )
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)
        await self._run(job, request.payload)
        return job

    async def run_task(self, task_id: int) -> Job:
        task = TaskService(self._db).get_task(task_id)
        if not task.enabled:
            raise AppError("task_disabled", f"task {task_id} is disabled", status_code=409)
        request = JobRequest(
            task_id=task.id,
            task_type=task.task_type,
            library_user_id=task.library_user_id,
            payload=TaskService.payload(task),
        )
        return await self.create_and_run(request)

    # ------------------------------------------------------------------ internals

    async def _run(self, job: Job, payload: dict[str, Any]) -> None:
        await self._set_status(job, JobStatus.RUNNING, started=True)
        await self._log(job, JobLogLevel.INFO, f"job started: type={job.task_type.value}")
        try:
            summary = await self._dispatch(job, payload)
            await self._log(job, JobLogLevel.INFO, f"job done: {summary}")
            await self._set_status(job, JobStatus.SUCCESS, summary=summary, finished=True)
        except AppError as exc:
            await self._log(job, JobLogLevel.WARNING, f"{exc.code}: {exc.message}")
            final_status = (
                JobStatus.BLOCKED_NEED_USER_CONFIRMATION
                if exc.code == "library_mutation_disabled"
                else JobStatus.FAILED
            )
            await self._set_status(job, final_status, summary=exc.message, finished=True)
        except Exception as exc:  # noqa: BLE001 — runner is the last safety net
            logger.exception("job %s crashed", job.id)
            await self._log(job, JobLogLevel.ERROR, f"unhandled: {exc!s}")
            await self._set_status(job, JobStatus.FAILED, summary=str(exc), finished=True)
        finally:
            await self._log_bus.close(job.id or 0)

    async def _dispatch(self, job: Job, payload: dict[str, Any]) -> str:
        task_type = job.task_type
        user_id = job.library_user_id
        if task_type == TaskType.SEARCH:
            from app.library.client import SeatSearchFilters

            filters = SeatSearchFilters(
                on_date=payload.get("on_date"),
                building=payload.get("building"),
                room=payload.get("room"),
                hour=payload.get("hour"),
                start_min=payload.get("start_min"),
                end_min=payload.get("end_min"),
            )
            result = await self._library.search_seats(user_id, filters)
            return f"found {result.seat_num} seats"
        if task_type == TaskType.RESERVE:
            date_str = _resolve_reservation_date(payload)
            if "date_offset" in payload:
                await self._log(
                    job,
                    JobLogLevel.INFO,
                    f"reserve: resolved date={date_str} from offset={payload.get('date_offset')!r}",
                )
            mutation = await self._library.submit_reservation(
                user_id,
                seat_id=int(payload["seat_id"]),
                start=str(payload["start"]),
                end=str(payload["end"]),
                date=date_str,
            )
            return mutation.message or ("reserved" if mutation.success else "reservation failed")
        if task_type == TaskType.CANCEL:
            mutation = await self._library.cancel_reservation(
                user_id, str(payload["reservation_id"])
            )
            return mutation.message or "cancelled"
        if task_type == TaskType.CHECKIN:
            mutation = await self._library.check_in(user_id)
            return mutation.message or "checked in"
        if task_type == TaskType.RENEW:
            mutation = await self._library.renew(user_id)
            return mutation.message or "renewed"
        if task_type == TaskType.STOP_USING:
            mutation = await self._library.stop_using(user_id)
            return mutation.message or "stopped using"
        if task_type == TaskType.LEAVE:
            mutation = await self._library.leave(user_id)
            return mutation.message or "leave"
        if task_type == TaskType.RESUME:
            mutation = await self._library.resume(user_id)
            return mutation.message or "resumed"
        raise AppError("unknown_task_type", f"unsupported task type {task_type.value}", status_code=400)

    async def _set_status(
        self,
        job: Job,
        status: JobStatus,
        *,
        summary: str | None = None,
        started: bool = False,
        finished: bool = False,
    ) -> None:
        job.status = status
        now = datetime.now(timezone.utc)
        if started:
            job.started_at = now
        if finished:
            job.finished_at = now
        if summary is not None:
            job.summary = summary
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)

    async def _log(self, job: Job, level: JobLogLevel, message: str) -> None:
        entry = JobLog(job_id=job.id or 0, level=level, message=message)
        self._db.add(entry)
        self._db.commit()
        self._db.refresh(entry)
        await self._log_bus.publish(
            LogEvent(
                job_id=job.id or 0,
                level=level,
                message=message,
                created_at=entry.created_at,
            )
        )


class JobScheduler:
    """Thin APScheduler wrapper that re-loads enabled scheduled tasks at startup."""

    def __init__(
        self,
        *,
        session_factory: Any,
        library_service_factory: Any = None,
    ) -> None:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        self._scheduler = AsyncIOScheduler()
        self._session_factory = session_factory
        self._library_factory = library_service_factory
        self._started = False

    @property
    def scheduler(self):  # type: ignore[no-untyped-def]
        return self._scheduler

    def start(self) -> None:
        if self._started:
            return
        self._scheduler.start()
        self._started = True
        self.reload()

    def shutdown(self) -> None:
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False

    def reload(self) -> None:
        self._scheduler.remove_all_jobs()
        with self._session_factory() as session:
            tasks = TaskService(session).list_tasks()
        for task in tasks:
            if task.mode != "scheduled" or not task.enabled or not task.cron:
                continue
            self._schedule(task)

    def _schedule(self, task: Task) -> None:
        from apscheduler.triggers.cron import CronTrigger

        try:
            trigger = CronTrigger.from_crontab(task.cron)
        except Exception as exc:  # noqa: BLE001
            logger.warning("invalid cron %r on task %s: %s", task.cron, task.id, exc)
            return

        task_id = task.id

        async def _fire() -> None:
            if task_id is None:
                return
            with self._session_factory() as session:
                runner = JobRunner(session)
                await runner.run_task(task_id)

        self._scheduler.add_job(
            _fire,
            trigger=trigger,
            id=f"task-{task_id}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

    async def run_now(self, task_id: int) -> Job:
        with self._session_factory() as session:
            runner = JobRunner(session)
            return await runner.run_task(task_id)
