from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import __version__


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
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", __version__))
    api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    theme_threshold: float = field(default_factory=lambda: float(os.getenv("THEME_THRESHOLD", "0.34")))
    models_dir: str = field(default_factory=lambda: os.getenv("MODELS_DIR", "models"))
    model_source: str = field(default_factory=lambda: os.getenv("MODEL_SOURCE", "local"))
    hf_model_repo_id: str | None = field(default_factory=lambda: os.getenv("HF_MODEL_REPO_ID") or None)
    hf_model_revision: str | None = field(default_factory=lambda: os.getenv("HF_MODEL_REVISION") or None)
    hf_token: str | None = field(default_factory=lambda: os.getenv("HF_TOKEN") or None)
    hf_cache_dir: str = field(default_factory=lambda: os.getenv("HF_CACHE_DIR", ".cache/huggingface"))
    hf_artifacts_dir: str = field(default_factory=lambda: os.getenv("HF_ARTIFACTS_DIR", ".cache/review_insights/models"))
    sentiment_backend: str = field(default_factory=lambda: os.getenv("SENTIMENT_BACKEND", "project"))
    hf_sentiment_model_id: str = field(
        default_factory=lambda: os.getenv(
            "HF_SENTIMENT_MODEL_ID",
            "SebasLopez-ai/distilbert-amazon-reviews-sentiment",
        )
    )
    hf_sentiment_revision: str = field(
        default_factory=lambda: os.getenv(
            "HF_SENTIMENT_REVISION",
            "881c6455b01b7ef50026f33902f6433651a1b1f0",
        )
    )
    hf_sentiment_artifacts_dir: str = field(
        default_factory=lambda: os.getenv(
            "HF_SENTIMENT_ARTIFACTS_DIR",
            ".cache/review_insights/sentiment",
        )
    )
    hf_sentiment_max_length: int = field(
        default_factory=lambda: int(os.getenv("HF_SENTIMENT_MAX_LENGTH", "256"))
    )
    sentiment_review_threshold: float = field(
        default_factory=lambda: float(os.getenv("SENTIMENT_REVIEW_THRESHOLD", "0.45"))
    )
    api_key: str | None = field(default_factory=lambda: os.getenv("API_KEY") or None)
    require_api_key: bool = field(default_factory=lambda: _parse_bool_env("REQUIRE_API_KEY", False))
    rate_limit_enabled: bool = field(default_factory=lambda: _parse_bool_env("RATE_LIMIT_ENABLED", True))
    rate_limit_requests: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_REQUESTS", "60")))
    rate_limit_window_seconds: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")))
    mlflow_tracking_enabled: bool = field(default_factory=lambda: _parse_bool_env("MLFLOW_TRACKING_ENABLED", False))
    mlflow_tracking_uri: str = field(default_factory=lambda: os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns"))
    mlflow_experiment_name: str = field(default_factory=lambda: os.getenv("MLFLOW_EXPERIMENT_NAME", "review-insights-default"))
    feedback_store_path: str = field(default_factory=lambda: os.getenv("FEEDBACK_STORE_PATH", "data/feedback/human_feedback.jsonl"))
    prediction_event_store_path: str | None = field(
        default_factory=lambda: os.getenv("PREDICTION_EVENT_STORE_PATH") or None
    )
    max_review_chars: int = field(default_factory=lambda: int(os.getenv("MAX_REVIEW_CHARS", "5000")))
    allowed_origins: tuple[str, ...] = field(default_factory=lambda: _parse_csv_env("ALLOWED_ORIGINS", "*"))
    trusted_hosts: tuple[str, ...] = field(default_factory=lambda: _parse_csv_env("TRUSTED_HOSTS", "*"))
    enable_docs: bool = field(default_factory=lambda: _parse_bool_env("ENABLE_DOCS", True))


def get_settings() -> Settings:
    return Settings()
