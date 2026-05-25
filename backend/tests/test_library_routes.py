"""FastAPI integration tests for /api/library/* routes.

The library upstream is faked via httpx.MockTransport injected through the
LibraryService dependency override. The mutation flag follows
ALLOW_MUTATION_TEST.
"""

from __future__ import annotations

from typing import Callable

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.library import get_library_service
from app.core.config import get_settings
from app.db.session import get_session
from app.library.rate_limit import RateLimiter
from app.library.session import LibrarySession
from app.main import create_app
from app.services.library_service import LibraryService
from app.services.library_session_store import LibrarySessionStore


SELF_HTML = """
<html><body>
<input type="hidden" id="sysUsername" value="202404020113" />
<input type="hidden" id="SYNCHRONIZER_TOKEN" name="SYNCHRONIZER_TOKEN" value="self-tok" />
<input type="hidden" id="SYNCHRONIZER_URI" name="SYNCHRONIZER_URI" value="/self" />
<input type="hidden" id="authid" name="authid" value="-1" />
<script>var userInfo = '{"userCheckedIn":false}';</script>
</body></html>
""".strip()

LOGIN_HTML = """
<input type="hidden" id="SYNCHRONIZER_TOKEN" name="SYNCHRONIZER_TOKEN" value="login-tok" />
<input type="hidden" id="SYNCHRONIZER_URI" name="SYNCHRONIZER_URI" value="/login" />
<input type="hidden" id="authid" name="authid" value="-1" />
""".strip()


def _no_rate_limit() -> RateLimiter:
    async def _noop(_: float) -> None:
        return None

    return RateLimiter(
        clock=lambda: 0.0,
        sleeper=_noop,
        intervals={k: 0.0 for k in ("query", "page", "submit", "global")},
    )


def _make_app(
    monkeypatch,
    tmp_path,
    *,
    handler: Callable[[httpx.Request], httpx.Response],
    allow_mutation: bool = False,
):
    monkeypatch.setenv("AUTO_LIBRARY_SECRET_KEY", "unit-test")
    monkeypatch.setenv("AUTO_LIBRARY_DATABASE_URL", f"sqlite:///{tmp_path}/lib.db")
    monkeypatch.setenv("AUTO_LIBRARY_LOGIN_URL", "http://10.1.20.7/login")
    monkeypatch.setenv("ALLOW_MUTATION_TEST", "true" if allow_mutation else "false")
    get_settings.cache_clear()
    settings = get_settings()
    app = create_app()
    transport = httpx.MockTransport(handler)
    store = LibrarySessionStore()

    from fastapi import Depends

    def _override(db_session: Session = Depends(get_session)) -> LibraryService:
        return LibraryService(
            db_session,
            settings=settings,
            store=store,
            rate_limiter=_no_rate_limit(),
            transport=transport,
        )

    app.dependency_overrides[get_library_service] = _override
    return app, store


def _create_user(client: TestClient, username: str = "202404020113") -> int:
    response = client.post(
        "/api/users",
        json={"username": username, "password": "library-pass"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


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


def test_bootstrap_returns_csrf_metadata(monkeypatch, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/login"
        return httpx.Response(200, text=LOGIN_HTML)

    app, store = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)
        response = client.post(f"/api/library/{user_id}/bootstrap")

    assert response.status_code == 200
    assert response.json()["synchronizer_uri"] == "/login"


def test_login_round_trip_persists_session(monkeypatch, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        auto = _auto_login_response(request)
        if auto is not None:
            if request.url.path == "/auth/signIn":
                assert b"username=202404020113" in request.content
            return auto
        return httpx.Response(404)

    app, store = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)
        login_resp = client.post(f"/api/library/{user_id}/login")
        status_resp = client.get(f"/api/library/{user_id}/session")

    assert login_resp.status_code == 200
    assert login_resp.json()["success"] is True
    body = status_resp.json()
    assert body["logged_in"] is True
    assert body["sys_username"] == "202404020113"
    assert body["has_csrf"] is True


def test_auto_login_retries_on_captcha_failure(monkeypatch, tmp_path) -> None:
    """Auto login: OCR is wrong twice, third try is accepted."""
    sign_in_attempts: list[str] = []
    captcha_serial = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/login":
            return httpx.Response(200, text=LOGIN_HTML)
        if path == "/auth/createCaptcha":
            captcha_serial["n"] += 1
            return httpx.Response(
                200,
                json={"captchaId": f"cap-{captcha_serial['n']}", "captchaImage": "data:image/png;base64,Zg=="},
                headers={"content-type": "application/json"},
            )
        if path == "/auth/signIn":
            sign_in_attempts.append(request.content.decode())
            if len(sign_in_attempts) < 3:
                return httpx.Response(
                    200,
                    json={"success": False, "captcha": True, "message": "captcha mismatch"},
                )
            return httpx.Response(200, json={"success": True})
        if path == "/self":
            return httpx.Response(200, text=SELF_HTML)
        return httpx.Response(404)

    class FakeOcr:
        def __init__(self) -> None:
            self.calls = 0

        def recognize(self, _: bytes):
            from app.library.captcha_ocr import OcrResult

            self.calls += 1
            return OcrResult(answer=f"abc{self.calls}", engine="ddddocr")

    fake = FakeOcr()

    import app.library.captcha_ocr as ocr_mod

    monkeypatch.setattr(ocr_mod, "get_captcha_ocr", lambda: fake)

    app, _ = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)
        response = client.post(f"/api/library/{user_id}/login", json={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert len(sign_in_attempts) == 3
    assert fake.calls == 3


def test_auto_login_gives_up_after_max_retries(monkeypatch, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/login":
            return httpx.Response(200, text=LOGIN_HTML)
        if path == "/auth/createCaptcha":
            return httpx.Response(
                200,
                json={"captchaId": "x", "captchaImage": "data:image/png;base64,Zg=="},
                headers={"content-type": "application/json"},
            )
        if path == "/auth/signIn":
            return httpx.Response(
                200, json={"success": False, "captcha": True, "message": "still wrong"}
            )
        return httpx.Response(404)

    class FakeOcr:
        def recognize(self, _: bytes):
            from app.library.captcha_ocr import OcrResult

            return OcrResult(answer="wrong", engine="ddddocr")

    import app.library.captcha_ocr as ocr_mod

    monkeypatch.setattr(ocr_mod, "get_captcha_ocr", lambda: FakeOcr())
    monkeypatch.setenv("AUTO_LIBRARY_MAX_LOGIN_RETRIES", "2")

    app, _ = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)
        response = client.post(f"/api/library/{user_id}/login", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["captcha_required"] is True


def test_search_seats_route(monkeypatch, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        auto = _auto_login_response(request)
        if auto is not None:
            return auto
        assert request.url.path == "/freeBook/ajaxSearch"
        assert request.url.params.get("building") == "1"
        return httpx.Response(
            200,
            json={
                "seatStr": '<li class="free" id="seat_111"><dl><dt>011A</dt><dd>三层</dd></dl></li>',
                "seatNum": 1,
                "onDate": {"year": 2026, "monthOfYear": 5, "dayOfMonth": 25},
                "offset": -1,
            },
        )

    app, _ = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)
        response = client.get(f"/api/library/{user_id}/seats", params={"building": "1"})

    assert response.status_code == 200
    body = response.json()
    assert body["seat_num"] == 1
    assert body["seats"][0]["seat_id"] == 111
    assert body["on_date"] == "2026-05-25"


def test_reservation_blocked_without_mutation_flag(monkeypatch, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    app, store = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)
        response = client.post(
            f"/api/library/{user_id}/reservations",
            json={"seat_id": 5775, "start": "960", "end": "1320", "date": "2026-05-26"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "library_mutation_disabled"


def test_reservation_with_mutation_flag_succeeds(monkeypatch, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/selfRes":
            return httpx.Response(200, json={"success": True, "message": "ok"})
        return httpx.Response(404)

    app, store = _make_app(monkeypatch, tmp_path, handler=handler, allow_mutation=True)
    with TestClient(app) as client:
        user_id = _create_user(client)
        # Prime the per-user session with logged_in=True + CSRF
        import asyncio
        from app.library.csrf import CsrfBundle

        async def prime() -> None:
            await store.set(
                LibrarySession(
                    library_user_id=user_id,
                    logged_in=True,
                    sys_username="202404020113",
                    csrf=CsrfBundle(token="tok", uri="/self", authid="-1"),
                )
            )

        asyncio.run(prime())

        response = client.post(
            f"/api/library/{user_id}/reservations",
            json={"seat_id": 5775, "start": "960", "end": "1320", "date": "2026-05-26"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True


def test_reservation_auto_logs_in_before_mutation(monkeypatch, tmp_path) -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        auto = _auto_login_response(request)
        if auto is not None:
            return auto
        if request.url.path == "/selfRes":
            return httpx.Response(200, json={"success": True, "message": "ok"})
        return httpx.Response(404)

    app, _ = _make_app(monkeypatch, tmp_path, handler=handler, allow_mutation=True)
    with TestClient(app) as client:
        user_id = _create_user(client)
        response = client.post(
            f"/api/library/{user_id}/reservations",
            json={"seat_id": 5775, "start": "960", "end": "1320", "date": "2026-05-26"},
        )

    assert response.status_code == 200, response.text
    assert paths[:4] == ["/auth/createCaptcha", "/login", "/auth/signIn", "/self"]
    assert paths[-1] == "/selfRes"


def test_missing_user_returns_404(monkeypatch, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    app, _ = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        response = client.post("/api/library/9999/login")
    assert response.status_code == 404


def test_stop_using_leave_resume_routes_gated(monkeypatch, tmp_path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    app, _ = _make_app(monkeypatch, tmp_path, handler=handler, allow_mutation=False)
    with TestClient(app) as client:
        user_id = _create_user(client)
        for path in ("stop-using", "leave", "resume"):
            response = client.post(f"/api/library/{user_id}/{path}")
            assert response.status_code == 409
            assert response.json()["error"]["code"] == "library_mutation_disabled"


def test_reservation_detail_route(monkeypatch, tmp_path) -> None:
    detail_html = (
        '<html><body>'
        '<input type="hidden" id="reservationId" value="1230935" />'
        '凭证号 0113-935-2 日期 2026-05-26 时间 07:30 -- 15:30 '
        '位置 图书馆2层二层西区 座位 001C 状态 已预约'
        '</body></html>'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        auto = _auto_login_response(request)
        if auto is not None:
            return auto
        assert request.url.path == "/view"
        assert request.url.params.get("id") == "1230935"
        assert request.url.params.get("type") == "SEAT"
        return httpx.Response(200, text=detail_html)

    app, _ = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)
        body = client.get(f"/api/library/{user_id}/reservations/1230935").json()

    assert body["reservation_id"] == "1230935"
    assert body["credential_no"] == "0113-935-2"
    assert body["status"] == "已预约"


def test_history_and_announcement_routes(monkeypatch, tmp_path) -> None:
    history_html = (
        '<div class="myReserveList">'
        '<dl><dt>明天 16:00 -- 22:30</dt>'
        '<a href="/view?id=1230935&type=SEAT">已预约</a>'
        '<a>图书馆2层二层西区 001C</a></dl>'
        '</div>'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        auto = _auto_login_response(request)
        if auto is not None:
            return auto
        path = request.url.path
        if path == "/history":
            return httpx.Response(200, text=history_html)
        if path == "/user/getRollText":
            return httpx.Response(200, json={"rollText": "提前一天可预约第二日的座位"})
        return httpx.Response(404)

    app, _ = _make_app(monkeypatch, tmp_path, handler=handler)
    with TestClient(app) as client:
        user_id = _create_user(client)

        history = client.get(f"/api/library/{user_id}/reservations").json()
        assert history[0]["reservation_id"] == "1230935"
        assert history[0]["status"] == "已预约"
        assert history[0]["raw_date_label"] == "明天"

        announcement = client.get(f"/api/library/{user_id}/announcement").json()
        assert announcement["roll_text"] == "提前一天可预约第二日的座位"
