from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.security import APIKeyHeader

from .dataset import load_default_dataset, load_reference_evaluation_dataset, prepare_dataset
from .mlflow_tracking import log_evaluation_run
from .schemas import EvaluationResponse
from .security import enforce_api_key
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
    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def require_api_security(request: Request, api_key: str | None = Depends(api_key_header)) -> None:
        enforce_api_key(settings, request, api_key)

    @app.get("/health")
    def healthcheck() -> dict:
        return {
            "status": "ok",
            "service": "data",
            "environment": settings.app_env,
            "model_source": settings.model_source,
            "inference_backend": service.backend_name,
            "model_load_error": service.model_load_error,
            "model_revision": service.model_revision,
            "artifact_set_version": service.artifact_set_version,
            "mlflow_tracking_enabled": settings.mlflow_tracking_enabled,
            "mlflow_tracking_uri": settings.mlflow_tracking_uri,
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
        df = prepare_dataset(load_reference_evaluation_dataset())
        report = service.evaluate_dataframe(df)
        log_evaluation_run(report, run_name="data_api_default_evaluation")
        return EvaluationResponse(**report)

    return app


app = create_app()
