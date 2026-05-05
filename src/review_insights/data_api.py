from __future__ import annotations

from fastapi import FastAPI

from .dataset import load_default_dataset, prepare_dataset
from .schemas import EvaluationResponse
from .service import get_review_analysis_service
from .settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    service = get_review_analysis_service()
    app = FastAPI(
        title=f"{settings.app_name} Data Service",
        version=settings.app_version,
        summary="Dataset and offline evaluation service for Review Insights+.",
    )
    app.state.settings = settings
    app.state.service = service

    @app.get("/health")
    def healthcheck() -> dict:
        return {
            "status": "ok",
            "service": "data",
            "environment": settings.app_env,
            "model_source": settings.model_source,
            "inference_backend": service.backend_name,
        }

    @app.get("/v1/datasets/default")
    def default_dataset() -> dict:
        df = prepare_dataset(load_default_dataset())
        return {
            "name": "default_reviews",
            "rows": len(df),
            "columns": list(df.columns),
            "records": df.to_dict(orient="records"),
        }

    @app.get("/v1/datasets/default/profile")
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

    @app.get("/v1/evaluate/default", response_model=EvaluationResponse)
    def evaluate_default_dataset() -> EvaluationResponse:
        df = prepare_dataset(load_default_dataset())
        report = service.evaluate_dataframe(df)
        return EvaluationResponse(**report)

    return app


app = create_app()

