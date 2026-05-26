"""Service layer that bridges FastAPI routes and LibraryClient.

Responsibilities:
- Resolve LibraryUser record + decrypted password.
- Borrow the persisted LibrarySession from the store and create a new
  LibraryClient bound to it.
- Persist any session mutation back into the store before returning.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx

from app.core.config import Settings, get_settings
from app.core.crypto import PasswordEncryptor
from app.core.errors import NotFoundError
from app.db.models import LibraryUser
from app.library.client import (
    CaptchaImage,
    LibraryClient,
    LoginOutcome,
    MutationResult,
    SeatSearchFilters,
)
from app.library.errors import (
    LibraryUpstreamError,
    MutationDisabledError,
    NotLoggedInError,
)
from app.library.html_parsers import (
    HistoryEntry,
    ReservationDetail,
    RoomOption,
    SearchResult,
    StartTimesResult,
    TimeOption,
)
from app.library.rate_limit import RateLimiter
from app.services.library_session_store import (
    LibrarySessionStore,
    get_library_session_store,
)
from sqlmodel import Session, select


class LibraryService:
    def __init__(
        self,
        db_session: Session,
        *,
        settings: Settings | None = None,
        store: LibrarySessionStore | None = None,
        encryptor: PasswordEncryptor | None = None,
        rate_limiter: RateLimiter | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._db = db_session
        self._settings = settings or get_settings()
        self._store = store or get_library_session_store()
        self._encryptor = encryptor or PasswordEncryptor.from_settings(self._settings)
        self._rate_limiter = rate_limiter
        self._transport = transport

    def _load_user(self, library_user_id: int) -> LibraryUser:
        user = self._db.get(LibraryUser, library_user_id)
        if user is None:
            raise NotFoundError(f"library user {library_user_id} not found")
        return user

    @asynccontextmanager
    async def _client(self, library_user_id: int) -> AsyncIterator[LibraryClient]:
        session = await self._store.get(library_user_id)
        client = LibraryClient(
            session=session,
            settings=self._settings,
            transport=self._transport,
            rate_limiter=self._rate_limiter,
        )
        try:
            yield client
        finally:
            await self._store.set(client.session)
            await client.aclose()

    @asynccontextmanager
    async def _authenticated_client(
        self, library_user_id: int, *, require_csrf: bool = False
    ) -> AsyncIterator[LibraryClient]:
        async with self._client(library_user_id) as client:
            await self._ensure_logged_in(library_user_id, client, require_csrf=require_csrf)
            yield client

    async def _ensure_logged_in(
        self,
        library_user_id: int,
        client: LibraryClient,
        *,
        require_csrf: bool = False,
    ) -> None:
        if client.session.logged_in and (not require_csrf or client.session.csrf is not None):
            return

        user = self._load_user(library_user_id)
        password = self._encryptor.decrypt(user.password_encrypted)
        outcome = await self._auto_login(client, user.username, password)
        if not outcome.success:
            raise NotLoggedInError(f"自动登录失败：{outcome.message}")
        if require_csrf and client.session.csrf is None:
            raise NotLoggedInError("自动登录成功，但缺少 CSRF token")

    async def _auto_login(
        self, client: LibraryClient, username: str, password: str
    ) -> LoginOutcome:
        # Match the browser flow recorded in docs/har/2.har:
        #   GET /login  →  GET /auth/createCaptcha  →  POST /auth/signIn
        # The captcha is bound to the JSESSIONID the server assigns on /login,
        # so the bootstrap must happen *before* the captcha is fetched.
        if client.session.csrf is None:
            await client.bootstrap_session()

        attempts = max(1, self._settings.max_login_retries)
        last_outcome: LoginOutcome | None = None
        for _ in range(attempts):
            captcha = await self._fetch_and_recognize_captcha(client)
            if captcha is None or not captcha.suggested_answer:
                # OCR couldn't read this image; try a fresh captcha rather
                # than wasting a signIn attempt with an empty answer.
                last_outcome = LoginOutcome(
                    success=False,
                    message="captcha OCR unreadable",
                    session=client.session,
                    captcha_required=True,
                )
                continue
            outcome = await client.login(
                username=username,
                password=password,
                captcha_answer=captcha.suggested_answer,
                captcha_id=captcha.captcha_id,
            )
            last_outcome = outcome
            if outcome.success or not outcome.captcha_required:
                return outcome
        assert last_outcome is not None
        return last_outcome

    def _require_mutation_enabled(self, action: str) -> None:
        if not self._settings.allow_mutation_test:
            raise MutationDisabledError(action)

    # ------------------------------------------------------------------ session

    async def bootstrap(self, library_user_id: int) -> dict[str, str | None]:
        async with self._client(library_user_id) as client:
            context = await client.bootstrap_session()
        return {
            "synchronizer_uri": context.synchronizer_uri,
            "authid": context.authid,
            "sys_username": context.sys_username,
        }

    async def get_captcha(self, library_user_id: int) -> CaptchaImage:
        async with self._client(library_user_id) as client:
            captcha = await self._fetch_and_recognize_captcha(client)
        assert captcha is not None
        return captcha

    async def login(self, library_user_id: int) -> LoginOutcome:
        user = self._load_user(library_user_id)
        password = self._encryptor.decrypt(user.password_encrypted)

        async with self._client(library_user_id) as client:
            # The user clicked "auto login" -- treat it as "start clean".
            # Otherwise stale cookies/CSRF from a timed-out upstream session
            # cause the captcha to bind to a freshly rotated JSESSIONID
            # while we POST signIn with the old SYNCHRONIZER_TOKEN, which
            # the server rejects as "still on login page".
            client.reset()
            return await self._auto_login(client, user.username, password)

    async def _fetch_and_recognize_captcha(
        self, client: LibraryClient
    ) -> CaptchaImage | None:
        captcha = await client.get_captcha()
        if not self._settings.enable_captcha_ocr:
            return captcha
        if captcha.suggested_answer:
            return captcha
        import base64
        from dataclasses import replace as _replace

        from app.library.captcha_ocr import get_captcha_ocr

        try:
            image_bytes = base64.b64decode(captcha.image_base64)
        except ValueError:
            return captcha
        result = get_captcha_ocr().recognize(image_bytes)
        if result is None:
            return captcha
        return _replace(captcha, suggested_answer=result.answer, ocr_engine=result.engine)

    async def logout(self, library_user_id: int) -> None:
        async with self._client(library_user_id) as client:
            await client.logout()
        await self._store.clear(library_user_id)

    async def session_status(self, library_user_id: int) -> dict[str, object]:
        async with self._client(library_user_id) as client:
            # Don't trust the cached logged_in flag -- if the upstream
            # session was rotated/expired we'd report "已登录" while every
            # real action fails. verify_logged_in() resets local state on
            # failure so the next step / next call can re-handshake.
            if client.session.logged_in:
                await client.verify_logged_in()
            # Preserve the prior behavior of attempting a login from this
            # endpoint, but stay tolerant: session_status reports state,
            # it shouldn't 500 just because the upstream is unhealthy.
            if not client.session.logged_in:
                user = self._load_user(library_user_id)
                password = self._encryptor.decrypt(user.password_encrypted)
                try:
                    await self._auto_login(client, user.username, password)
                except LibraryUpstreamError:
                    pass
            session = client.session
        return {
            "library_user_id": library_user_id,
            "logged_in": session.logged_in,
            "sys_username": session.sys_username,
            "user_info": session.user_info,
            "has_csrf": session.csrf is not None,
        }

    # ------------------------------------------------------------------ read

    async def get_rooms(self, library_user_id: int, building_id: str) -> list[RoomOption]:
        async with self._authenticated_client(library_user_id) as client:
            return await client.get_rooms(building_id)

    async def search_seats(self, library_user_id: int, filters: SeatSearchFilters) -> SearchResult:
        async with self._authenticated_client(library_user_id) as client:
            return await client.search_seats(filters)

    async def get_start_times(
        self, library_user_id: int, seat_id: int | str, date: str
    ) -> StartTimesResult:
        async with self._authenticated_client(library_user_id) as client:
            return await client.get_start_times(seat_id, date=date)

    async def get_end_times(
        self, library_user_id: int, *, start: str, seat_id: int | str, date: str
    ) -> list[TimeOption]:
        async with self._authenticated_client(library_user_id) as client:
            return await client.get_end_times(start=start, seat_id=seat_id, date=date)

    async def get_history(self, library_user_id: int) -> list[HistoryEntry]:
        async with self._authenticated_client(library_user_id) as client:
            return await client.get_history()

    async def get_reservation_detail(
        self, library_user_id: int, reservation_id: str
    ) -> ReservationDetail:
        async with self._authenticated_client(library_user_id) as client:
            return await client.get_reservation_detail(reservation_id)

    async def get_roll_text(self, library_user_id: int) -> str | None:
        async with self._authenticated_client(library_user_id) as client:
            return await client.get_roll_text()

    # ------------------------------------------------------------------ mutations

    async def submit_reservation(
        self,
        library_user_id: int,
        *,
        seat_id: int | str,
        start: str,
        end: str,
        date: str,
    ) -> MutationResult:
        self._require_mutation_enabled("submit_reservation")
        async with self._authenticated_client(library_user_id, require_csrf=True) as client:
            return await client.submit_reservation(
                seat_id=seat_id, start=start, end=end, date=date
            )

    async def cancel_reservation(
        self, library_user_id: int, reservation_id: str
    ) -> MutationResult:
        self._require_mutation_enabled("cancel_reservation")
        async with self._authenticated_client(library_user_id, require_csrf=True) as client:
            return await client.cancel_reservation(reservation_id)

    async def check_in(self, library_user_id: int) -> MutationResult:
        self._require_mutation_enabled("check_in")
        async with self._authenticated_client(library_user_id, require_csrf=True) as client:
            return await client.check_in()

    async def renew(self, library_user_id: int) -> MutationResult:
        self._require_mutation_enabled("renew")
        async with self._authenticated_client(library_user_id, require_csrf=True) as client:
            return await client.renew()

    async def stop_using(self, library_user_id: int) -> MutationResult:
        self._require_mutation_enabled("stop_using")
        async with self._authenticated_client(library_user_id, require_csrf=True) as client:
            return await client.stop_using()

    async def leave(self, library_user_id: int) -> MutationResult:
        self._require_mutation_enabled("leave")
        async with self._authenticated_client(library_user_id, require_csrf=True) as client:
            return await client.leave()

    async def resume(self, library_user_id: int) -> MutationResult:
        self._require_mutation_enabled("resume")
        async with self._authenticated_client(library_user_id, require_csrf=True) as client:
            return await client.resume()

    # ------------------------------------------------------------------ misc

    def list_enabled_user_ids(self) -> list[int]:
        statement = select(LibraryUser.id).where(LibraryUser.enabled == True)  # noqa: E712
        return [row for row in self._db.exec(statement).all() if row is not None]
