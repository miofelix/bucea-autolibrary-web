"""HTTP-only client for the Lion library reservation system.

Endpoint shapes are taken from ``docs/图书馆自动化工具开发辅助文档.md`` (v1.0).
The client never opens a browser, never solves a captcha automatically, and
refuses mutation endpoints unless
:class:`app.core.config.Settings.allow_mutation_test` is on.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, replace
from typing import Any, Mapping

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import redact_mapping
from app.library.csrf import CsrfBundle
from app.library.errors import (
    LibraryUpstreamError,
    MutationDisabledError,
    NotLoggedInError,
)
from app.library.html_parsers import (
    HistoryEntry,
    PageContext,
    ReservationDetail,
    RoomOption,
    SearchResult,
    StartTimesResult,
    TimeOption,
    parse_history,
    parse_page_context,
    parse_reservation_detail,
    parse_rooms,
    parse_search_response,
    parse_start_times,
    parse_time_options,
)
from app.library.rate_limit import RateLimiter
from app.library.session import LibrarySession
from app.library.time_utils import normalize_time_value


logger = logging.getLogger("autolibrary.library")

DEFAULT_USER_AGENT = "AutoLibrary/0.2 HTTP client"


@dataclass
class SeatSearchFilters:
    on_date: str | None = None
    building: str | None = None
    room: str | None = None
    hour: str | None = None
    start_min: str | None = None
    end_min: str | None = None
    power: str | None = None
    window: str | None = None
    offset: int = 1

    def to_query(self) -> dict[str, str]:
        # Must match the official library website's parameter format exactly.
        # The site sends ALL fields as strings, with unset values as "null",
        # and omits "offset" on the first page.
        params: dict[str, str] = {
            "onDate": self.on_date or "",
            "building": self.building or "null",
            "room": self.room or "null",
            "hour": self.hour or "null",
            "startMin": self.start_min or "null",
            "endMin": self.end_min or "null",
            "power": self.power or "null",
            "window": self.window or "null",
        }
        if self.offset > 1:
            params["offset"] = str(self.offset)
        return params


@dataclass(frozen=True)
class LoginOutcome:
    success: bool
    message: str
    session: LibrarySession
    captcha_required: bool = False


@dataclass(frozen=True)
class CaptchaImage:
    image_base64: str
    content_type: str
    captcha_id: str | None
    suggested_answer: str | None = None
    ocr_engine: str | None = None


@dataclass(frozen=True)
class MutationResult:
    success: bool
    message: str
    raw: Any


def _redacted(data: Mapping[str, Any]) -> dict[str, Any]:
    return redact_mapping(dict(data))


class LibraryClient:
    """One client per library account."""

    def __init__(
        self,
        *,
        session: LibrarySession,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        rate_limiter: RateLimiter | None = None,
        base_url: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._session = session
        self._base_url = (base_url or self._derive_base_url()).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            follow_redirects=True,
            timeout=httpx.Timeout(15.0),
            headers={"User-Agent": DEFAULT_USER_AGENT},
            transport=transport,
            cookies=session.cookies,
        )
        self._rate_limiter = rate_limiter or RateLimiter()

    def _derive_base_url(self) -> str:
        login_url = self._settings.library_login_url
        if login_url.endswith("/login"):
            return login_url[: -len("/login")]
        return login_url

    @property
    def session(self) -> LibrarySession:
        return self._session

    @property
    def base_url(self) -> str:
        return self._base_url

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "LibraryClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    # ------------------------------------------------------------------ helpers

    def _sync_cookies(self) -> None:
        cookies = {cookie.name: cookie.value for cookie in self._client.cookies.jar if cookie.value}
        self._session = replace(self._session, cookies=cookies)

    def _update_context(self, html: str) -> PageContext:
        context = parse_page_context(html)
        csrf = CsrfBundle.from_page(context) or self._session.csrf
        self._session = replace(
            self._session,
            csrf=csrf,
            sys_username=context.sys_username or self._session.sys_username,
            sys_token=context.sys_token or self._session.sys_token,
            user_info=context.user_info or self._session.user_info,
        )
        return context

    def _require_csrf(self) -> CsrfBundle:
        if not self._session.logged_in:
            raise NotLoggedInError()
        if self._session.csrf is None:
            raise NotLoggedInError("missing CSRF token; call bootstrap_session()/login() first")
        return self._session.csrf

    def _require_mutation_allowed(self, action: str) -> None:
        if not self._settings.allow_mutation_test:
            raise MutationDisabledError(action)

    async def _get(self, path: str, *, params: dict[str, str] | None = None, rate_key: str = "query") -> httpx.Response:
        await self._rate_limiter.acquire(rate_key)
        try:
            response = await self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise LibraryUpstreamError(f"GET {path} failed: {exc!s}") from exc
        self._sync_cookies()
        logger.debug("GET %s %s", path, _redacted(params or {}))
        if response.status_code >= 500:
            raise LibraryUpstreamError(f"GET {path} -> {response.status_code}", status_code=502)
        return response

    async def _post(
        self,
        path: str,
        *,
        data: dict[str, str] | None = None,
        rate_key: str = "submit",
    ) -> httpx.Response:
        await self._rate_limiter.acquire(rate_key)
        try:
            response = await self._client.post(path, data=data)
        except httpx.HTTPError as exc:
            raise LibraryUpstreamError(f"POST {path} failed: {exc!s}") from exc
        self._sync_cookies()
        logger.debug("POST %s %s", path, _redacted(data or {}))
        if response.status_code >= 500:
            raise LibraryUpstreamError(f"POST {path} -> {response.status_code}", status_code=502)
        return response

    @staticmethod
    def _detect_success(payload: Any) -> tuple[bool, str]:
        if isinstance(payload, dict):
            for key in ("success", "result", "status"):
                value = payload.get(key)
                if isinstance(value, bool):
                    return value, str(payload.get("message") or payload.get("msg") or "")
                if isinstance(value, str):
                    return value.lower() in {"ok", "success", "true", "1"}, str(
                        payload.get("message") or value
                    )
            message = str(payload.get("message") or payload.get("msg") or "")
            if message:
                return True, message
        return True, ""

    @staticmethod
    def _safe_json(response: httpx.Response, *, default_key: str | None = None) -> Any:
        try:
            return response.json()
        except ValueError:
            if default_key is None:
                return response.text
            return {default_key: response.text}

    # ------------------------------------------------------------------ session

    async def bootstrap_session(self) -> PageContext:
        response = await self._get("/login", rate_key="global")
        return self._update_context(response.text)

    async def get_captcha(self) -> CaptchaImage:
        response = await self._get("/auth/createCaptcha", rate_key="global")
        content_type = response.headers.get("content-type", "")
        if "image" in content_type:
            captcha = CaptchaImage(
                image_base64=base64.b64encode(response.content).decode("ascii"),
                content_type=content_type,
                captcha_id=response.headers.get("X-Captcha-Id"),
            )
        elif "application/json" in content_type:
            payload = response.json()
            image = payload.get("captchaImage") or payload.get("image") or payload.get("data")
            captcha_id = payload.get("captchaId") or payload.get("id")
            if image is None:
                raise LibraryUpstreamError("captcha JSON missing image field")
            image_str = str(image)
            if image_str.startswith("data:"):
                head, _, body = image_str.partition(",")
                mime = head[5:].split(";", 1)[0] or "image/png"
                captcha = CaptchaImage(
                    image_base64=body,
                    content_type=mime,
                    captcha_id=str(captcha_id) if captcha_id is not None else None,
                )
            else:
                captcha = CaptchaImage(
                    image_base64=image_str,
                    content_type="image/png",
                    captcha_id=str(captcha_id) if captcha_id is not None else None,
                )
        else:
            raise LibraryUpstreamError(f"unexpected captcha content-type: {content_type}")

        if captcha.captcha_id:
            self._session = replace(self._session, captcha_id=captcha.captcha_id)
        return captcha

    async def login(
        self,
        *,
        username: str,
        password: str,
        captcha_answer: str,
        captcha_id: str | None = None,
    ) -> LoginOutcome:
        if not self._session.csrf:
            await self.bootstrap_session()
        csrf = self._session.csrf
        form = {
            "SYNCHRONIZER_TOKEN": csrf.token if csrf else "",
            "SYNCHRONIZER_URI": csrf.uri if csrf else "/login",
            "username": username,
            "password": password,
            "answer": captcha_answer,
            "captchaId": captcha_id or self._session.captcha_id or "",
            "authid": csrf.authid if csrf else "-1",
        }
        response = await self._post("/auth/signIn", data=form, rate_key="submit")
        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:
            payload = response.json()
            success, message = self._detect_success(payload)
            captcha_required = bool(payload.get("captcha")) or "captcha" in (message or "").lower()
            if success:
                self._session = replace(self._session, sys_username=username, logged_in=True)
                await self._refresh_after_login()
            return LoginOutcome(
                success=success,
                message=message or ("login ok" if success else "login failed"),
                session=self._session,
                captcha_required=captcha_required,
            )

        html = response.text
        context = self._update_context(html)
        success = context.sys_username is not None
        if success:
            self._session = replace(self._session, logged_in=True)
            return LoginOutcome(success=True, message="login ok", session=self._session)
        return LoginOutcome(
            success=False,
            message="login failed (still on login page)",
            session=self._session,
            captcha_required="验证码" in html or "captcha" in html.lower(),
        )

    async def _refresh_after_login(self) -> None:
        try:
            response = await self._get("/self", rate_key="global")
        except LibraryUpstreamError:
            return
        self._update_context(response.text)

    async def logout(self) -> None:
        await self._get("/logout", rate_key="global")
        self._session = self._session.cleared()

    # ------------------------------------------------------------------ rooms / seats / times

    async def get_rooms(self, building_id: str) -> list[RoomOption]:
        response = await self._get(
            "/freeBook/ajaxGetRooms",
            params={"id": str(building_id)},
            rate_key="query",
        )
        return parse_rooms(response.text)

    async def search_seats(self, filters: SeatSearchFilters) -> SearchResult:
        response = await self._get(
            "/freeBook/ajaxSearch",
            params=filters.to_query(),
            rate_key="query",
        )
        payload = self._safe_json(response, default_key="seatStr")
        return parse_search_response(payload)

    async def get_start_times(self, seat_id: int | str, *, date: str = "") -> StartTimesResult:
        response = await self._get(
            "/freeBook/ajaxGetTime",
            params={"id": str(seat_id), "date": date or ""},
            rate_key="query",
        )
        return parse_start_times(response.text)

    async def get_end_times(
        self,
        *,
        start: str,
        seat_id: int | str,
        date: str = "",
    ) -> list[TimeOption]:
        response = await self._get(
            "/freeBook/ajaxGetEndTime",
            params={
                "start": normalize_time_value(start),
                "seat": str(seat_id),
                "date": date or "",
            },
            rate_key="query",
        )
        return parse_time_options(response.text)

    # ------------------------------------------------------------------ mutations

    async def submit_reservation(
        self,
        *,
        seat_id: int | str,
        start: str,
        end: str,
        date: str = "",
    ) -> MutationResult:
        self._require_mutation_allowed("submit_reservation")
        csrf = self._require_csrf()
        data = {
            "SYNCHRONIZER_TOKEN": csrf.token,
            "SYNCHRONIZER_URI": csrf.uri,
            "date": date or "",
            "seat": str(seat_id),
            "start": normalize_time_value(start),
            "end": normalize_time_value(end),
            "authid": csrf.authid,
        }
        response = await self._post("/selfRes", data=data, rate_key="submit")
        payload = self._safe_json(response)
        success, message = self._detect_success(payload if isinstance(payload, dict) else {})
        return MutationResult(success=success, message=message, raw=payload)

    async def cancel_reservation(self, reservation_id: str) -> MutationResult:
        self._require_mutation_allowed("cancel_reservation")
        csrf = self._require_csrf()
        data = {
            "SYNCHRONIZER_TOKEN": csrf.token,
            "SYNCHRONIZER_URI": csrf.uri,
            "id": str(reservation_id),
        }
        response = await self._post("/reservation/cancel", data=data, rate_key="submit")
        payload = self._safe_json(response)
        success, message = self._detect_success(payload if isinstance(payload, dict) else {})
        return MutationResult(success=success, message=message, raw=payload)

    async def check_in(self) -> MutationResult:
        self._require_mutation_allowed("check_in")
        csrf = self._require_csrf()
        response = await self._post(
            "/user/checkIn",
            data={"SYNCHRONIZER_TOKEN": csrf.token, "SYNCHRONIZER_URI": csrf.uri},
            rate_key="submit",
        )
        payload = self._safe_json(response)
        success, message = self._detect_success(payload if isinstance(payload, dict) else {})
        return MutationResult(success=success, message=message, raw=payload)

    async def renew(self) -> MutationResult:
        self._require_mutation_allowed("renew")
        csrf = self._require_csrf()
        response = await self._post(
            "/user/getTimeExtend",
            data={"SYNCHRONIZER_TOKEN": csrf.token, "SYNCHRONIZER_URI": csrf.uri},
            rate_key="submit",
        )
        payload = self._safe_json(response)
        success, message = self._detect_success(payload if isinstance(payload, dict) else {})
        return MutationResult(success=success, message=message, raw=payload)

    async def stop_using(self) -> MutationResult:
        self._require_mutation_allowed("stop_using")
        csrf = self._require_csrf()
        response = await self._post(
            "/user/stopUsing",
            data={"SYNCHRONIZER_TOKEN": csrf.token, "SYNCHRONIZER_URI": csrf.uri},
            rate_key="submit",
        )
        payload = self._safe_json(response)
        success, message = self._detect_success(payload if isinstance(payload, dict) else {})
        return MutationResult(success=success, message=message, raw=payload)

    async def leave(self) -> MutationResult:
        self._require_mutation_allowed("leave")
        csrf = self._require_csrf()
        response = await self._post(
            "/user/leave",
            data={"SYNCHRONIZER_TOKEN": csrf.token, "SYNCHRONIZER_URI": csrf.uri},
            rate_key="submit",
        )
        payload = self._safe_json(response)
        success, message = self._detect_success(payload if isinstance(payload, dict) else {})
        return MutationResult(success=success, message=message, raw=payload)

    async def resume(self) -> MutationResult:
        self._require_mutation_allowed("resume")
        csrf = self._require_csrf()
        response = await self._post(
            "/user/resume",
            data={"SYNCHRONIZER_TOKEN": csrf.token, "SYNCHRONIZER_URI": csrf.uri},
            rate_key="submit",
        )
        payload = self._safe_json(response)
        success, message = self._detect_success(payload if isinstance(payload, dict) else {})
        return MutationResult(success=success, message=message, raw=payload)

    # ------------------------------------------------------------------ read-only user actions

    async def get_roll_text(self) -> str | None:
        response = await self._get("/user/getRollText", rate_key="global")
        payload = self._safe_json(response)
        if isinstance(payload, dict):
            return payload.get("rollText")
        return None

    async def get_history(self, *, history_type: str = "SEAT") -> list[HistoryEntry]:
        response = await self._get("/history", params={"type": history_type}, rate_key="query")
        return parse_history(response.text)

    async def get_reservation_detail(
        self, reservation_id: str, *, history_type: str = "SEAT"
    ) -> ReservationDetail:
        response = await self._get(
            "/view",
            params={"id": str(reservation_id), "type": history_type},
            rate_key="query",
        )
        return parse_reservation_detail(response.text)

