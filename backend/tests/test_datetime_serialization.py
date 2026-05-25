"""Ensure datetimes are always serialized with a UTC offset.

SQLite drops ``tzinfo`` on read, so a naive serializer would emit
``"2026-05-25T11:00:18"`` and the JS client would parse it as local
time. We reattach ``timezone.utc`` so the wire format is unambiguous.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.serializers import serialize_utc
from app.schemas.task import JobLogRead, JobRead, TaskRead
from app.schemas.user import LibraryUserRead


def test_serialize_utc_attaches_offset_for_naive() -> None:
    out = serialize_utc(datetime(2026, 5, 25, 11, 0, 18))
    assert out is not None and out.endswith("+00:00")


def test_serialize_utc_preserves_aware_value() -> None:
    aware = datetime(2026, 5, 25, 11, 0, 18, tzinfo=timezone.utc)
    out = serialize_utc(aware)
    assert out == "2026-05-25T11:00:18+00:00"


def test_serialize_utc_passes_through_none() -> None:
    assert serialize_utc(None) is None


def test_job_read_dumps_with_tz() -> None:
    job = JobRead(
        id=1,
        task_id=None,
        task_type="search",
        library_user_id=1,
        status="success",
        summary="found 0 seats",
        started_at=datetime(2026, 5, 25, 11, 0, 18),
        finished_at=datetime(2026, 5, 25, 11, 0, 19),
        created_at=datetime(2026, 5, 25, 11, 0, 17),
    )
    body = job.model_dump(mode="json")
    assert body["started_at"].endswith("+00:00")
    assert body["finished_at"].endswith("+00:00")
    assert body["created_at"].endswith("+00:00")


def test_task_read_dumps_with_tz() -> None:
    task = TaskRead(
        id=1,
        name="t",
        task_type="search",
        mode="manual",
        enabled=True,
        cron=None,
        library_user_id=1,
        payload=None,
        created_at=datetime(2026, 5, 25, 11, 0, 0),
        updated_at=datetime(2026, 5, 25, 11, 0, 0),
    )
    body = task.model_dump(mode="json")
    assert body["created_at"].endswith("+00:00")
    assert body["updated_at"].endswith("+00:00")


def test_job_log_and_user_read_dump_with_tz() -> None:
    log = JobLogRead(
        id=1,
        job_id=1,
        level="info",
        message="hi",
        created_at=datetime(2026, 5, 25, 11, 0, 0),
    )
    assert log.model_dump(mode="json")["created_at"].endswith("+00:00")

    user = LibraryUserRead(
        id=1,
        username="x",
        display_name=None,
        enabled=True,
        notes=None,
        created_at=datetime(2026, 5, 25, 11, 0, 0),
        updated_at=datetime(2026, 5, 25, 11, 0, 0),
    )
    body = user.model_dump(mode="json")
    assert body["created_at"].endswith("+00:00")
    assert body["updated_at"].endswith("+00:00")
