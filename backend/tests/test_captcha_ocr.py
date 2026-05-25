"""Tests for the captcha OCR wiring.

The OCR engine itself (ddddocr) is heavy and loads a 100 MB ONNX model;
its accuracy is tested upstream. Here we only verify the integration
points: lazy load, recognize failure handling, and that the
``Settings.enable_captcha_ocr`` flag actually gates the service call.
"""

from __future__ import annotations

import base64
from typing import Callable

import httpx
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.library import get_library_service
from app.core.config import get_settings
from app.db.session import get_session
from app.library.captcha_ocr import CaptchaOcr
from app.library.client import CaptchaImage
from app.library.rate_limit import RateLimiter
from app.main import create_app
from app.services.library_service import LibraryService
from app.services.library_session_store import LibrarySessionStore


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
    enable_ocr: bool,
):
    monkeypatch.setenv("AUTO_LIBRARY_SECRET_KEY", "unit-test")
    monkeypatch.setenv("AUTO_LIBRARY_DATABASE_URL", f"sqlite:///{tmp_path}/o.db")
    monkeypatch.setenv("AUTO_LIBRARY_LOGIN_URL", "http://10.1.20.7/login")
    monkeypatch.setenv("AUTO_LIBRARY_ENABLE_CAPTCHA_OCR", "true" if enable_ocr else "false")
    get_settings.cache_clear()
    settings = get_settings()
    app = create_app()
    transport = httpx.MockTransport(handler)
    store = LibrarySessionStore()

    def _override(db_session: Session = Depends(get_session)) -> LibraryService:
        return LibraryService(
            db_session,
            settings=settings,
            store=store,
            rate_limiter=_no_rate_limit(),
            transport=transport,
        )

    app.dependency_overrides[get_library_service] = _override
    return app


def _create_user(client: TestClient) -> int:
    response = client.post(
        "/api/users",
        json={"username": "202404020113", "password": "library-pass"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _png_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        content=b"\x89PNG\r\n\x1a\nfake",
        headers={"content-type": "image/png"},
    )


def test_captcha_ocr_disabled_returns_no_suggestion(monkeypatch, tmp_path) -> None:
    app = _make_app(monkeypatch, tmp_path, handler=_png_handler, enable_ocr=False)
    with TestClient(app) as client:
        user_id = _create_user(client)
        body = client.get(f"/api/library/{user_id}/captcha").json()
    assert body["suggested_answer"] is None
    assert body["ocr_engine"] is None


def test_captcha_ocr_enabled_uses_engine(monkeypatch, tmp_path) -> None:
    captured_bytes: dict[str, bytes] = {}

    class FakeOcr:
        def recognize(self, image_bytes: bytes):
            captured_bytes["raw"] = image_bytes
            from app.library.captcha_ocr import OcrResult

            return OcrResult(answer="abcd", engine="ddddocr")

    monkeypatch.setattr(
        "app.services.library_service.get_captcha_ocr",
        lambda: FakeOcr(),
        raising=False,
    )
    # The import is inside the function body; patch the module the function
    # actually pulls from.
    import app.library.captcha_ocr as ocr_mod

    monkeypatch.setattr(ocr_mod, "get_captcha_ocr", lambda: FakeOcr())

    app = _make_app(monkeypatch, tmp_path, handler=_png_handler, enable_ocr=True)
    with TestClient(app) as client:
        user_id = _create_user(client)
        body = client.get(f"/api/library/{user_id}/captcha").json()

    assert body["suggested_answer"] == "abcd"
    assert body["ocr_engine"] == "ddddocr"
    assert captured_bytes["raw"] == b"\x89PNG\r\n\x1a\nfake"


def test_runtime_settings_exposes_ocr_flag(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTO_LIBRARY_SECRET_KEY", "x")
    monkeypatch.setenv("AUTO_LIBRARY_DATABASE_URL", f"sqlite:///{tmp_path}/r.db")
    monkeypatch.setenv("AUTO_LIBRARY_ENABLE_CAPTCHA_OCR", "false")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        body = client.get("/api/settings/runtime").json()
    assert body["enable_captcha_ocr"] is False


def test_captcha_ocr_returns_none_on_engine_error() -> None:
    ocr = CaptchaOcr()

    class Bomb:
        def classification(self, image: bytes) -> str:
            raise RuntimeError("boom")

    ocr._engine = Bomb()  # type: ignore[assignment]
    ocr._tried_load = True
    assert ocr.recognize(b"data") is None


def test_captcha_ocr_returns_none_when_engine_missing() -> None:
    ocr = CaptchaOcr()
    ocr._tried_load = True
    ocr._engine = None
    assert ocr.recognize(b"data") is None
