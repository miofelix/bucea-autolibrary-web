"""LibraryClient integration tests against an httpx MockTransport."""

from __future__ import annotations

import base64
import json
from typing import Callable

import httpx
import pytest

from app.core.config import Settings
from app.library.client import (
    LibraryClient,
    SeatSearchFilters,
)
from app.library.errors import (
    MutationDisabledError,
    NotLoggedInError,
)
from app.library.rate_limit import RateLimiter
from app.library.session import LibrarySession


def _no_rate_limit() -> RateLimiter:
    async def _noop_sleep(_: float) -> None:
        return None

    return RateLimiter(
        clock=lambda: 0.0,
        sleeper=_noop_sleep,
        intervals={"query": 0.0, "page": 0.0, "submit": 0.0, "global": 0.0},
    )


def _settings(*, allow_mutation: bool = False) -> Settings:
    return Settings(
        AUTO_LIBRARY_SECRET_KEY="unit-test",
        AUTO_LIBRARY_LOGIN_URL="http://10.1.20.7/login",
        ALLOW_MUTATION_TEST=allow_mutation,
    )


def _make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    session: LibrarySession | None = None,
    allow_mutation: bool = False,
) -> LibraryClient:
    transport = httpx.MockTransport(handler)
    return LibraryClient(
        session=session or LibrarySession(library_user_id=42),
        settings=_settings(allow_mutation=allow_mutation),
        transport=transport,
        rate_limiter=_no_rate_limit(),
    )


LOGIN_HTML = """
<html><body>
<input type="hidden" id="SYNCHRONIZER_TOKEN" name="SYNCHRONIZER_TOKEN" value="login-tok" />
<input type="hidden" id="SYNCHRONIZER_URI" name="SYNCHRONIZER_URI" value="/login" />
<input type="hidden" id="authid" name="authid" value="-1" />
</body></html>
""".strip()


SELF_HTML = """
<html><body>
<input type="hidden" id="sysUsername" value="202404020113" />
<input type="hidden" id="sysToken" value="sess-token" />
<input type="hidden" id="SYNCHRONIZER_TOKEN" name="SYNCHRONIZER_TOKEN" value="self-tok" />
<input type="hidden" id="SYNCHRONIZER_URI" name="SYNCHRONIZER_URI" value="/self" />
<input type="hidden" id="authid" name="authid" value="-1" />
<script>
  var userInfo = '{"currentReservationStatus":"NO_RESERVATION","userCheckedIn":false}';
</script>
</body></html>
""".strip()


async def test_bootstrap_captures_login_page_csrf() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/login"
        return httpx.Response(200, text=LOGIN_HTML)

    async with _make_client(handler) as client:
        ctx = await client.bootstrap_session()

    assert ctx.synchronizer_token == "login-tok"
    assert client.session.csrf is not None
    assert client.session.csrf.token == "login-tok"


async def test_login_success_via_json_refreshes_self_csrf() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/login":
            return httpx.Response(200, text=LOGIN_HTML)
        if request.url.path == "/auth/signIn":
            assert b"username=202404020113" in request.content
            assert b"SYNCHRONIZER_TOKEN=login-tok" in request.content
            return httpx.Response(
                200,
                json={"success": True, "message": "ok"},
                headers={"set-cookie": "JSESSIONID=sess-xyz; Path=/"},
            )
        if request.url.path == "/self":
            return httpx.Response(200, text=SELF_HTML)
        return httpx.Response(404)

    async with _make_client(handler) as client:
        outcome = await client.login(
            username="202404020113",
            password="library-password",
            captcha_answer="1234",
        )

    assert outcome.success is True
    assert outcome.session.logged_in is True
    assert outcome.session.csrf is not None
    assert outcome.session.csrf.token == "self-tok"
    assert outcome.session.csrf.uri == "/self"
    assert outcome.session.cookies.get("JSESSIONID") == "sess-xyz"
    assert calls == ["GET /login", "POST /auth/signIn", "GET /self"]


async def test_login_failure_marks_session_not_logged_in() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login":
            return httpx.Response(200, text=LOGIN_HTML)
        if request.url.path == "/auth/signIn":
            return httpx.Response(200, json={"success": False, "message": "captcha required", "captcha": True})
        return httpx.Response(404)

    async with _make_client(handler) as client:
        outcome = await client.login(
            username="x", password="y", captcha_answer="bad"
        )

    assert outcome.success is False
    assert outcome.captcha_required is True
    assert outcome.session.logged_in is False


async def test_get_captcha_returns_base64_for_image_response() -> None:
    image_bytes = b"\x89PNG\r\n\x1a\nfakepng"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/createCaptcha"
        return httpx.Response(
            200,
            content=image_bytes,
            headers={"content-type": "image/png", "X-Captcha-Id": "cap-1"},
        )

    async with _make_client(handler) as client:
        captcha = await client.get_captcha()

    assert base64.b64decode(captcha.image_base64) == image_bytes
    assert captcha.captcha_id == "cap-1"


async def test_get_captcha_handles_json_data_url_payload() -> None:
    """Matches the real 10.1.20.7 response: captchaImage="data:image/png;base64,..."."""

    image_bytes = b"\x89PNG\r\n\x1a\nrealpng"
    inline_b64 = base64.b64encode(image_bytes).decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"captchaId": "abc123", "captchaImage": f"data:image/png;base64,{inline_b64}"},
            headers={"content-type": "application/json;charset=UTF-8"},
        )

    async with _make_client(handler) as client:
        captcha = await client.get_captcha()
        session_after = client.session

    assert base64.b64decode(captcha.image_base64) == image_bytes
    assert captcha.content_type == "image/png"
    assert captcha.captcha_id == "abc123"
    assert session_after.captcha_id == "abc123"


async def test_search_seats_decodes_seatstr() -> None:
    payload = {
        "seatStr": '<li class="free" id="seat_777"><dl><dt>007A</dt><dd>三层内环区</dd></dl></li>',
        "seatNum": 1,
        "onDate": {"year": 2026, "monthOfYear": 5, "dayOfMonth": 25},
        "offset": -1,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/freeBook/ajaxSearch"
        assert request.url.params.get("building") == "1"
        assert request.url.params.get("offset") is None  # first page omits offset
        assert request.url.params.get("room") == "null"
        return httpx.Response(200, json=payload)

    async with _make_client(handler) as client:
        result = await client.search_seats(SeatSearchFilters(building="1"))

    assert result.seat_num == 1
    assert result.seats[0].seat_id == 777
    assert result.on_date == "2026-05-25"


async def test_get_end_times_parses_options() -> None:
    html = """
        <li><a href="#" time="990">16:30</a></li>
        <li><a href="#" time="1020">17:00</a></li>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/freeBook/ajaxGetEndTime"
        assert request.url.params.get("start") == "960"
        assert request.url.params.get("seat") == "5775"
        return httpx.Response(200, text=html)

    async with _make_client(handler) as client:
        options = await client.get_end_times(start="960", seat_id=5775)

    assert [opt.raw_value for opt in options] == ["990", "1020"]


async def test_submit_reservation_is_blocked_without_mutation_flag() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    session = LibrarySession(library_user_id=1, logged_in=True)
    async with _make_client(handler, session=session) as client:
        with pytest.raises(MutationDisabledError):
            await client.submit_reservation(seat_id=5775, start="960", end="1320")


async def test_submit_reservation_requires_login_even_with_flag() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    async with _make_client(handler, allow_mutation=True) as client:
        with pytest.raises(NotLoggedInError):
            await client.submit_reservation(seat_id=5775, start="960", end="1320")


async def test_submit_reservation_with_flag_and_login_posts_form() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/selfRes":
            captured.update(dict(httpx.QueryParams(request.content.decode())))
            return httpx.Response(200, json={"success": True, "message": "reserved"})
        return httpx.Response(404)

    from app.library.csrf import CsrfBundle

    session = LibrarySession(
        library_user_id=1,
        logged_in=True,
        csrf=CsrfBundle(token="tok", uri="/self", authid="-1"),
        sys_username="202404020113",
    )
    async with _make_client(handler, session=session, allow_mutation=True) as client:
        result = await client.submit_reservation(
            seat_id=5775, start="960", end="1320", date="2026-05-26"
        )

    assert result.success is True
    assert captured["seat"] == "5775"
    assert captured["start"] == "960"
    assert captured["end"] == "1320"
    assert captured["SYNCHRONIZER_TOKEN"] == "tok"
    assert captured["authid"] == "-1"


async def test_logout_clears_session() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="bye")

    from app.library.csrf import CsrfBundle

    session = LibrarySession(
        library_user_id=1,
        logged_in=True,
        csrf=CsrfBundle(token="t", uri="/self", authid="-1"),
        sys_username="x",
    )
    async with _make_client(handler, session=session) as client:
        await client.logout()

    assert client.session.logged_in is False
    assert client.session.csrf is None
    assert client.session.cookies == {}
    assert client.session.sys_username is None
