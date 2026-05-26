"""End-to-end tests for task creation, job execution and SSE log streaming."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.jobs import get_job_runner
from app.api.library import get_library_service
from app.api.logs import get_runner as get_logs_runner
from app.core.config import get_settings
from app.db.session import get_session
from app.library.rate_limit import RateLimiter
from app.main import create_app
from app.services.job_runner import JobRunner
from app.services.library_service import LibraryService
from app.services.library_session_store import LibrarySessionStore


def _no_rate_limit() -> RateLimiter:
    async def _noop(_: float) -> None:
        return None

    return RateLimiter(
        clock=lambda: 0.0,
        sleeper=_noop,
        intervals={k: 0.0 for k in ("query", "page", "submit", "login", "global")},
    )


@pytest.fixture(autouse=True)
def _default_fake_ocr(monkeypatch):
    """Install a synthetic OCR result so the fake captcha bytes routed via
    MockTransport don't hit the real ddddocr (which would error on non-image
    input). Tests can override by reassigning ``get_captcha_ocr`` later.
    """
    import app.library.captcha_ocr as ocr_mod

    class _FakeOcr:
        def recognize(self, _: bytes):
            return ocr_mod.OcrResult(answer="abcd", engine="fake")

    monkeypatch.setattr(ocr_mod, "get_captcha_ocr", lambda: _FakeOcr())


def _make_app(monkeypatch, tmp_path, *, handler, allow_mutation: bool = False):
    monkeypatch.setenv("AUTO_LIBRARY_SECRET_KEY", "unit-test")
    monkeypatch.setenv("AUTO_LIBRARY_DATABASE_URL", f"sqlite:///{tmp_path}/tasks.db")
    monkeypatch.setenv("AUTO_LIBRARY_LOGIN_URL", "http://10.1.20.7/login")
    monkeypatch.setenv("ALLOW_MUTATION_TEST", "true" if allow_mutation else "false")
    get_settings.cache_clear()
    settings = get_settings()
    app = create_app()
    transport = httpx.MockTransport(handler)
    store = LibrarySessionStore()

    def _library_override(db_session: Session = Depends(get_session)) -> LibraryService:
        return LibraryService(
            db_session,
            settings=settings,
            store=store,
            rate_limiter=_no_rate_limit(),
            transport=transport,
        )

    def _runner_override(db_session: Session = Depends(get_session)) -> JobRunner:
        return JobRunner(
            db_session,
            library_service=LibraryService(
                db_session,
                settings=settings,
                store=store,
                rate_limiter=_no_rate_limit(),
                transport=transport,
            ),
            settings=settings,
        )

    app.dependency_overrides[get_library_service] = _library_override
    app.dependency_overrides[get_job_runner] = _runner_override
    app.dependency_overrides[get_logs_runner] = _runner_override
    return app


def _create_user(client: TestClient) -> int:
    response = client.post(
        "/api/users",
        json={"username": "202404020113", "password": "library-pass"},
    )
    assert response.status_code == 201
    return response.json()["id"]


LOGIN_HTML = """
<input type="hidden" id="SYNCHRONIZER_TOKEN" name="SYNCHRONIZER_TOKEN" value="login-tok" />
<input type="hidden" id="SYNCHRONIZER_URI" name="SYNCHRONIZER_URI" value="/login" />
<input type="hidden" id="authid" name="authid" value="-1" />
""".strip()


SELF_HTML = """
<input type="hidden" id="sysUsername" value="202404020113" />
<input type="hidden" id="SYNCHRONIZER_TOKEN" name="SYNCHRONIZER_TOKEN" value="self-tok" />
<input type="hidden" id="SYNCHRONIZER_URI" name="SYNCHRONIZER_URI" value="/self" />
<input type="hidden" id="authid" name="authid" value="-1" />
""".strip()


def _auto_login_response(request: httpx.Request) -> httpx.Response | None:
    path = request.url.path
    if path == "/login":
        return httpx.Response(200, text=LOGIN_HTML)
    if path == "/auth/createCaptcha":
        return httpx.Response(
            200,
            json={"captchaId": "cap-1", "captchaImage": "data:image/png;base64,Zg=="},
            headers={"content-type": "application/json"},
        )
    if path == "/auth/signIn":
        return httpx.Response(200, json={"success": True})
    if path == "/self":
        return httpx.Response(200, text=SELF_HTML)
    return None


def test_task_crud_round_trip(monkeypatch, tmp_path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    app = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)
        create = client.post(
            "/api/tasks",
            json={
                "name": "每日预约",
                "task_type": "reserve",
                "mode": "manual",
                "library_user_id": user_id,
                "payload": {"seat_id": 5775, "start": "960", "end": "1320", "date": "2026-05-26"},
            },
        )
        assert create.status_code == 201, create.text
        task = create.json()

        listed = client.get("/api/tasks").json()
        assert len(listed) == 1
        assert listed[0]["payload"]["seat_id"] == 5775

        updated = client.put(
            f"/api/tasks/{task['id']}",
            json={"enabled": False, "name": "改名"},
        ).json()
        assert updated["enabled"] is False
        assert updated["name"] == "改名"

        assert client.delete(f"/api/tasks/{task['id']}").status_code == 204
        assert client.get("/api/tasks").json() == []


def test_scheduled_task_requires_cron(monkeypatch, tmp_path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    app = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)
        response = client.post(
            "/api/tasks",
            json={
                "name": "schedule no cron",
                "task_type": "checkin",
                "mode": "scheduled",
                "library_user_id": user_id,
            },
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_job_run_search_returns_seat_count(monkeypatch, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        auto = _auto_login_response(request)
        if auto is not None:
            return auto
        if request.url.path == "/freeBook/ajaxSearch":
            return httpx.Response(
                200,
                json={
                    "seatStr": '<li class="free" id="seat_111"><dl><dt>011A</dt><dd>三层</dd></dl></li>'
                               '<li class="free" id="seat_112"><dl><dt>011B</dt><dd>三层</dd></dl></li>',
                    "seatNum": 2,
                    "onDate": {"year": 2026, "monthOfYear": 5, "dayOfMonth": 25},
                    "offset": -1,
                },
            )
        return httpx.Response(404)

    app = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)
        task = client.post(
            "/api/tasks",
            json={
                "name": "搜座位",
                "task_type": "search",
                "mode": "manual",
                "library_user_id": user_id,
                "payload": {"building": "1"},
            },
        ).json()

        run = client.post("/api/jobs/run", json={"task_id": task["id"]})
        assert run.status_code == 200, run.text
        job = run.json()
        assert job["status"] == "success"
        assert job["summary"] == "found 2 seats"

        logs = client.get(f"/api/jobs/{job['id']}/logs").json()
        assert any("found 2 seats" in entry["message"] for entry in logs)


def test_resolve_reservation_date_prefers_explicit_value() -> None:
    from app.services.job_runner import _resolve_reservation_date

    assert _resolve_reservation_date({"date": "2026-05-26"}) == "2026-05-26"
    # Explicit beats offset so legacy tasks keep behaving like before.
    assert (
        _resolve_reservation_date({"date": "2026-05-26", "date_offset": 3})
        == "2026-05-26"
    )
    assert _resolve_reservation_date({"date": ""}) == ""
    assert _resolve_reservation_date({}) == ""


def test_resolve_reservation_date_applies_offset_from_today() -> None:
    from datetime import date, timedelta

    from app.services.job_runner import _resolve_reservation_date

    today = date.today()
    assert _resolve_reservation_date({"date_offset": 0}) == today.strftime("%Y-%m-%d")
    assert _resolve_reservation_date({"date_offset": 1}) == (
        today + timedelta(days=1)
    ).strftime("%Y-%m-%d")
    # Bad input falls back to empty string instead of raising — the
    # upstream client treats empty date as "today".
    assert _resolve_reservation_date({"date_offset": "not a number"}) == ""


def test_reserve_task_with_date_offset_targets_tomorrow(monkeypatch, tmp_path) -> None:
    """A scheduled reserve task should bind to (today + offset) at run time,
    not to the date that was current when the task was created."""
    from datetime import date, timedelta

    expected_date = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    seen_form: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        auto = _auto_login_response(request)
        if auto is not None:
            return auto
        if request.url.path == "/selfRes":
            from urllib.parse import parse_qs

            parsed = parse_qs(request.content.decode())
            seen_form.update({k: v[0] for k, v in parsed.items()})
            return httpx.Response(200, json={"success": True, "message": "ok"})
        return httpx.Response(404)

    app = _make_app(monkeypatch, tmp_path, handler=handler, allow_mutation=True)
    with TestClient(app) as client:
        user_id = _create_user(client)
        task = client.post(
            "/api/tasks",
            json={
                "name": "明天预约",
                "task_type": "reserve",
                "mode": "manual",
                "library_user_id": user_id,
                "payload": {
                    "seat_id": 5775,
                    "start": "960",
                    "end": "1320",
                    "date_offset": 1,
                },
            },
        ).json()

        run = client.post("/api/jobs/run", json={"task_id": task["id"]}).json()
        assert run["status"] == "success", run

    assert seen_form.get("date") == expected_date


def test_job_blocked_when_mutation_disabled(monkeypatch, tmp_path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    app = _make_app(monkeypatch, tmp_path, handler=handler, allow_mutation=False)
    with TestClient(app) as client:
        user_id = _create_user(client)
        task = client.post(
            "/api/tasks",
            json={
                "name": "签到",
                "task_type": "checkin",
                "mode": "manual",
                "library_user_id": user_id,
            },
        ).json()

        job = client.post("/api/jobs/run", json={"task_id": task["id"]}).json()
        assert job["status"] == "blocked_need_user_confirmation"

        logs = client.get(f"/api/jobs/{job['id']}/logs").json()
        assert any("library_mutation_disabled" in entry["message"] for entry in logs)


@pytest.mark.asyncio
async def test_log_bus_pub_sub() -> None:
    from datetime import datetime, timezone

    from app.db.models import JobLogLevel
    from app.services.job_log_bus import JobLogBus, LogEvent

    bus = JobLogBus()
    received: list[str] = []

    async def consume() -> None:
        async for event in bus.subscribe(99):
            received.append(event.message)

    import asyncio

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    await bus.publish(LogEvent(job_id=99, level=JobLogLevel.INFO, message="hello", created_at=datetime.now(timezone.utc)))
    await bus.publish(LogEvent(job_id=99, level=JobLogLevel.INFO, message="world", created_at=datetime.now(timezone.utc)))
    await asyncio.sleep(0)
    await bus.close(99)
    await asyncio.wait_for(task, timeout=1.0)

    assert received == ["hello", "world"]


def test_logs_endpoint_lists_history(monkeypatch, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        auto = _auto_login_response(request)
        if auto is not None:
            return auto
        if request.url.path == "/freeBook/ajaxSearch":
            return httpx.Response(
                200,
                json={
                    "seatStr": "",
                    "seatNum": 0,
                    "onDate": {"year": 2026, "monthOfYear": 5, "dayOfMonth": 25},
                    "offset": -1,
                },
            )
        return httpx.Response(404)

    app = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)
        task = client.post(
            "/api/tasks",
            json={
                "name": "搜",
                "task_type": "search",
                "mode": "manual",
                "library_user_id": user_id,
            },
        ).json()
        job = client.post("/api/jobs/run", json={"task_id": task["id"]}).json()

        logs = client.get(f"/api/jobs/{job['id']}/logs").json()
        assert len(logs) >= 2
        assert logs[0]["level"] == "info"
