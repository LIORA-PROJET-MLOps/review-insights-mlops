from __future__ import annotations

import os
from collections.abc import Callable

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.security import APIKeyHeader
from pathlib import Path

from .dataset import load_default_dataset, prepare_dataset
from .feedback_store import HumanFeedbackRecord, append_feedback, read_feedback
from .schemas import EvaluationResponse, HumanFeedbackRequest
from .security import enforce_api_key
from .settings import get_settings


def _inference_api_url() -> str:
    return os.getenv("API_URL", "http://api:8000").rstrip("/")


def _fetch_inference_evaluation() -> dict:
    headers = {}
    api_key = os.getenv("API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    timeout = float(os.getenv("SERVICE_TIMEOUT_SECONDS", "60"))
    with httpx.Client(timeout=timeout) as client:
        response = client.get(f"{_inference_api_url()}/v1/evaluate/default", headers=headers)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Inference API returned a non-object evaluation payload.")
    return payload


def create_app(evaluation_fetcher: Callable[[], dict] | None = None) -> FastAPI:
    settings = get_settings()
    fetch_evaluation = evaluation_fetcher or _fetch_inference_evaluation
    app = FastAPI(
        title=f"{settings.app_name} Data Service",
        version=settings.app_version,
        summary="Dataset and offline evaluation service for Review Insights+.",
    )
    app.state.settings = settings
    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def require_api_security(request: Request, api_key: str | None = Depends(api_key_header)) -> None:
        enforce_api_key(settings, request, api_key)

    @app.get("/health")
    def healthcheck() -> dict:
        return {
            "status": "ok",
            "service": "data",
            "environment": settings.app_env,
            "inference_api_url": _inference_api_url(),
            "mlflow_tracking_enabled": settings.mlflow_tracking_enabled,
            "mlflow_tracking_uri": settings.mlflow_tracking_uri,
            "feedback_store_path": settings.feedback_store_path,
        }

    @app.get("/v1/datasets/default", dependencies=[Depends(require_api_security)])
    def default_dataset() -> dict:
        df = prepare_dataset(load_default_dataset())
        return {
            "name": "default_reviews",
            "rows": len(df),
            "columns": list(df.columns),
            "records": df.to_dict(orient="records"),
        }

    @app.get("/v1/datasets/default/profile", dependencies=[Depends(require_api_security)])
    def default_dataset_profile() -> dict:
        df = prepare_dataset(load_default_dataset())
        return {
            "rows": len(df),
            "sentiment_distribution": df["sentiment_label"].value_counts().to_dict(),
            "theme_counts": {
                "livraison": int(df["theme_livraison"].sum()),
                "sav": int(df["theme_sav"].sum()),
                "produit": int(df["theme_produit"].sum()),
            },
        }

    @app.get("/v1/evaluate/default", response_model=EvaluationResponse, dependencies=[Depends(require_api_security)])
    def evaluate_default_dataset() -> EvaluationResponse:
        report = fetch_evaluation()
        return EvaluationResponse(**report)

    @app.post("/v1/feedback", dependencies=[Depends(require_api_security)])
    def create_feedback(payload: HumanFeedbackRequest) -> dict:
        record = append_feedback(
            HumanFeedbackRecord(**payload.model_dump()),
            Path(settings.feedback_store_path),
        )
        return {
            "status": "recorded",
            "record": record.to_dict(),
        }

    @app.get("/v1/feedback/recent", dependencies=[Depends(require_api_security)])
    def recent_feedback(limit: int = 100) -> dict:
        records = read_feedback(Path(settings.feedback_store_path), limit=limit)
        return {
            "rows": len(records),
            "records": records,
        }

    return app


app = create_app()
