"""Per-library-user session container."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from app.library.csrf import CsrfBundle


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class LibrarySession:
    library_user_id: int
    sys_username: str | None = None
    sys_token: str | None = None
    csrf: CsrfBundle | None = None
    captcha_id: str | None = None
    user_info: dict[str, Any] | None = field(default=None)
    cookies: dict[str, str] = field(default_factory=dict)
    last_refreshed_at: datetime = field(default_factory=_utc_now)
    logged_in: bool = False

    def with_csrf(self, csrf: CsrfBundle | None) -> "LibrarySession":
        return replace(self, csrf=csrf, last_refreshed_at=_utc_now())

    def with_login(
        self,
        *,
        cookies: dict[str, str],
        sys_username: str | None,
        sys_token: str | None,
        csrf: CsrfBundle | None,
        user_info: dict[str, Any] | None,
    ) -> "LibrarySession":
        return replace(
            self,
            cookies=dict(cookies),
            sys_username=sys_username,
            sys_token=sys_token,
            csrf=csrf,
            user_info=user_info,
            logged_in=True,
            last_refreshed_at=_utc_now(),
        )

    def cleared(self) -> "LibrarySession":
        return LibrarySession(library_user_id=self.library_user_id)
