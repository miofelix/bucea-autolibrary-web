from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings


router = APIRouter()


class RuntimeSettings(BaseModel):
    app_env: str
    library_login_url: str
    library_base_url: str
    allow_live_test: bool
    allow_mutation_test: bool
    enable_captcha_ocr: bool


@router.get("/runtime", response_model=RuntimeSettings)
def runtime_settings(settings: Settings = Depends(get_settings)) -> RuntimeSettings:
    base = settings.library_login_url
    if base.endswith("/login"):
        base = base[: -len("/login")]
    return RuntimeSettings(
        app_env=settings.app_env,
        library_login_url=settings.library_login_url,
        library_base_url=base,
        allow_live_test=settings.allow_live_test,
        allow_mutation_test=settings.allow_mutation_test,
        enable_captcha_ocr=settings.enable_captcha_ocr,
    )
