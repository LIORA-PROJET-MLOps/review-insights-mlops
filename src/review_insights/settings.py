from __future__ import annotations

import os
from dataclasses import dataclass, field


def _parse_csv_env(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return tuple(values)


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "local"))
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Review Insights+"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "0.2.0"))
    api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    theme_threshold: float = field(default_factory=lambda: float(os.getenv("THEME_THRESHOLD", "0.34")))
    models_dir: str = field(default_factory=lambda: os.getenv("MODELS_DIR", "models"))
    api_key: str | None = field(default_factory=lambda: os.getenv("API_KEY") or None)
    max_review_chars: int = field(default_factory=lambda: int(os.getenv("MAX_REVIEW_CHARS", "5000")))
    allowed_origins: tuple[str, ...] = field(default_factory=lambda: _parse_csv_env("ALLOWED_ORIGINS", "*"))
    trusted_hosts: tuple[str, ...] = field(default_factory=lambda: _parse_csv_env("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver"))
    enable_docs: bool = field(default_factory=lambda: _parse_bool_env("ENABLE_DOCS", True))


def get_settings() -> Settings:
    return Settings()
