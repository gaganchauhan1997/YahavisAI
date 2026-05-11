from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "YahavisAI"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    SESSION_SECRET: Optional[str] = None
    SECRET_KEY: Optional[str] = None
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://yahavis.hackknow.com",
    ]

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.3
    GEMINI_MAX_TOKENS: int = 2048

    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    REDIS_URL: Optional[str] = None
    N8N_WEBHOOK_URL: Optional[str] = None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def get_cors_origins() -> list[str]:
    if settings.ENVIRONMENT == "development":
        return ["*"]
    return settings.CORS_ORIGINS
