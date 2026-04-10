from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .dataset import load_default_dataset, prepare_dataset
from .schemas import AnalyzeReviewRequest, AnalyzeReviewResponse, EvaluationResponse, HealthResponse, MetricsResponse
from .service import get_review_analysis_service
from .settings import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        return response


def create_app() -> FastAPI:
    settings = get_settings()
    service = get_review_analysis_service()
    docs_url = "/docs" if settings.enable_docs else None
    redoc_url = "/redoc" if settings.enable_docs else None
    openapi_url = "/openapi.json" if settings.enable_docs else None
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        summary="Production-shaped API for Review Insights+ POC",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    app.state.settings = settings
    app.state.service = service
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def require_api_key(api_key: str | None = Depends(api_key_header)) -> None:
        configured_key = settings.api_key
        if not configured_key:
            return
        if api_key != configured_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key.",
            )

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})

    @app.get("/health", response_model=HealthResponse)
    def healthcheck() -> HealthResponse:
        resolved_source = settings.model_source.strip().lower()
        manifest_path = Path(settings.models_dir) / "manifest.json"
        manifest_present = service.backend_name == "project_models_v1" if resolved_source == "hf_hub" else manifest_path.exists()
        return HealthResponse(
            status="ok",
            app_name=settings.app_name,
            app_version=settings.app_version,
            environment=settings.app_env,
            inference_backend=service.backend_name,
            model_source=resolved_source,
            models_manifest_present=manifest_present,
            protected_endpoints=bool(settings.api_key),
        )

    @app.post("/v1/analyze", response_model=AnalyzeReviewResponse, dependencies=[Depends(require_api_key)])
    def analyze_review_endpoint(payload: AnalyzeReviewRequest) -> AnalyzeReviewResponse:
        if len(payload.review_text) > settings.max_review_chars:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Review text exceeds the configured limit of {settings.max_review_chars} characters.",
            )
        return service.analyze(
            review_text=payload.review_text,
            review_id=payload.review_id,
            threshold=payload.threshold,
        )

    @app.get("/metrics", response_model=MetricsResponse, dependencies=[Depends(require_api_key)])
    def metrics_endpoint() -> MetricsResponse:
        return MetricsResponse(**service.get_monitoring_metrics())

    @app.get("/v1/evaluate/default", response_model=EvaluationResponse, dependencies=[Depends(require_api_key)])
    def evaluate_default_dataset() -> EvaluationResponse:
        df = prepare_dataset(load_default_dataset())
        report = service.evaluate_dataframe(df)
        return EvaluationResponse(**report)

    return app


app = create_app()
