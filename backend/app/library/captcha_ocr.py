"""Optional captcha OCR using `ddddocr <https://github.com/sml2h3/ddddocr>`_.

This was deliberately excluded from the original web rewrite (see
``docs/AGENT_PROGRESS.md`` for the rationale: the library system's captcha
exists to throttle abuse). The user has since opted to re-enable it for
their own account. The OCR runs only when
``Settings.enable_captcha_ocr`` is on; the user can still override the
recognized answer in the UI, and the rate limiter (≥3s/≥1s/≥60s) stays
intact.

Loading the ONNX model is expensive (≈1 s, ≈100 MB resident), so the
``DdddOcr`` instance is built lazily on first use and cached for the
process lifetime.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("autolibrary.captcha_ocr")


class _OcrEngine(Protocol):
    def classification(self, image: bytes) -> str: ...


@dataclass(frozen=True)
class OcrResult:
    answer: str
    engine: str  # "ddddocr" or "noop"


class CaptchaOcr:
    """Thread-safe lazy holder for a ``ddddocr.DdddOcr`` instance."""

    def __init__(self) -> None:
        self._engine: _OcrEngine | None = None
        self._lock = threading.Lock()
        self._tried_load = False
        self._error: str | None = None

    def _ensure_engine(self) -> _OcrEngine | None:
        if self._engine is not None or self._tried_load:
            return self._engine
        with self._lock:
            if self._engine is not None or self._tried_load:
                return self._engine
            self._tried_load = True
            try:
                import ddddocr  # type: ignore[import-untyped]

                self._engine = ddddocr.DdddOcr(show_ad=False, beta=False)
                logger.info("ddddocr engine loaded")
            except Exception as exc:  # noqa: BLE001 — keep service alive
                self._error = f"{type(exc).__name__}: {exc}"
                logger.warning("ddddocr unavailable: %s", self._error)
                self._engine = None
        return self._engine

    @property
    def last_error(self) -> str | None:
        return self._error

    def recognize(self, image_bytes: bytes) -> OcrResult | None:
        engine = self._ensure_engine()
        if engine is None:
            return None
        try:
            answer = engine.classification(image_bytes)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ddddocr recognize failed: %s", exc)
            return None
        cleaned = (answer or "").strip()
        if not cleaned:
            return None
        return OcrResult(answer=cleaned, engine="ddddocr")


_global_ocr = CaptchaOcr()


def get_captcha_ocr() -> CaptchaOcr:
    return _global_ocr
