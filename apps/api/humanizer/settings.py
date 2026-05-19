"""Application settings loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed environment configuration."""

    model_config = SettingsConfigDict(
        env_file=None,  # Coolify injects env vars directly
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "production"
    web_origin: str = "http://localhost:3000"
    max_text_length: int = 10_000
    rate_limit_per_min: int = 30
    trust_proxy: bool = True
    uvicorn_workers: int = 2

    enable_synthid: bool = False
    synthid_model: str = "google/gemma-2b"

    rate_limit_window_seconds: int = 60

    @property
    def version(self) -> str:
        from humanizer import __version__

        return __version__


_settings: Settings | None = None


def get_settings() -> Settings:
    """Cached settings accessor."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
