from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="AUTO_LIBRARY_APP_ENV")
    secret_key: str = Field(default="autolibrary", alias="AUTO_LIBRARY_SECRET_KEY")
    database_url: str = Field(
        default="sqlite:///./data/autolibrary.db",
        alias="AUTO_LIBRARY_DATABASE_URL",
    )
    library_login_url: str = Field(
        default="http://10.1.20.7/login",
        alias="AUTO_LIBRARY_LOGIN_URL",
    )
    allow_live_test: bool = Field(default=True, alias="ALLOW_LIVE_TEST")
    allow_mutation_test: bool = Field(default=True, alias="ALLOW_MUTATION_TEST")
    enable_captcha_ocr: bool = Field(default=True, alias="AUTO_LIBRARY_ENABLE_CAPTCHA_OCR")
    max_login_retries: int = Field(default=3, ge=1, le=10, alias="AUTO_LIBRARY_MAX_LOGIN_RETRIES")

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
