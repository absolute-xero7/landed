from __future__ import annotations

import os
import secrets
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    database_url: str = Field(default="sqlite:///./landed.db", alias="DATABASE_URL")
    app_encryption_key: str = Field(default="", alias="APP_ENCRYPTION_KEY")
    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=480, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    session_ttl_hours: int = Field(default=2, alias="SESSION_TTL_HOURS")
    session_cleanup_interval_seconds: int = Field(default=1800, alias="SESSION_CLEANUP_INTERVAL_SECONDS")
    max_file_size_mb: int = Field(default=10, alias="MAX_FILE_SIZE_MB")
    max_files_per_upload: int = Field(default=10, alias="MAX_FILES_PER_UPLOAD")
    allowed_origins: str = Field(default="http://localhost:3000", alias="ALLOWED_ORIGINS")

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    if not settings.app_encryption_key:
        settings.app_encryption_key = os.getenv("APP_ENCRYPTION_KEY", "")
    if not settings.jwt_secret_key:
        settings.jwt_secret_key = os.getenv("JWT_SECRET_KEY", "")

    if not settings.app_encryption_key:
        settings.app_encryption_key = secrets.token_urlsafe(32)
    if not settings.jwt_secret_key:
        settings.jwt_secret_key = secrets.token_urlsafe(48)

    return settings
