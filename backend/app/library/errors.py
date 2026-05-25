from __future__ import annotations

from app.core.errors import AppError


class LibraryClientError(AppError):
    pass


class SessionExpiredError(LibraryClientError):
    def __init__(self, message: str = "library session expired"):
        super().__init__("library_session_expired", message, status_code=401)


class NotLoggedInError(LibraryClientError):
    def __init__(self, message: str = "library client is not logged in"):
        super().__init__("library_not_logged_in", message, status_code=401)


class CaptchaRequiredError(LibraryClientError):
    def __init__(self, message: str = "captcha required for the next action"):
        super().__init__("library_captcha_required", message, status_code=409)


class RateLimitedError(LibraryClientError):
    def __init__(self, message: str = "library rate limit triggered"):
        super().__init__("library_rate_limited", message, status_code=429)


class MutationDisabledError(LibraryClientError):
    def __init__(self, action: str):
        super().__init__(
            "library_mutation_disabled",
            f"mutation action '{action}' is disabled; set ALLOW_MUTATION_TEST=true to enable",
            status_code=409,
        )


class LibraryParseError(LibraryClientError):
    def __init__(self, message: str):
        super().__init__("library_parse_error", message, status_code=502)


class LibraryUpstreamError(LibraryClientError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__("library_upstream_error", message, status_code=status_code)
