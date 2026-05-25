"""CSRF / session metadata extraction helpers.

These helpers wrap :func:`app.library.html_parsers.parse_page_context` to
produce a lightweight dataclass that LibraryClient/LibrarySession persist
between requests.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.library.html_parsers import PageContext, parse_page_context


@dataclass(frozen=True)
class CsrfBundle:
    token: str
    uri: str
    authid: str

    @classmethod
    def from_page(cls, context: PageContext) -> "CsrfBundle | None":
        if context.synchronizer_token and context.synchronizer_uri:
            return cls(
                token=context.synchronizer_token,
                uri=context.synchronizer_uri,
                authid=context.authid or "-1",
            )
        return None


def extract_from_html(html: str) -> tuple[PageContext, CsrfBundle | None]:
    context = parse_page_context(html)
    return context, CsrfBundle.from_page(context)
