from __future__ import annotations

from pathlib import Path
import time
import uuid

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .dataset import load_reference_evaluation_dataset, prepare_dataset
from .mlflow_tracking import log_evaluation_run
from .schemas import AnalyzeReviewRequest, AnalyzeReviewResponse, EvaluationResponse, HealthResponse, MetricsResponse
from .security import InMemoryRateLimiter, build_security_profile, client_identifier, enforce_api_key, log_security_event
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
    app.state.rate_limiter = InMemoryRateLimiter(
        requests_per_window=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_telemetry_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = (time.perf_counter() - started_at) * 1000
            service.monitoring.record_http_request(request.method, request.url.path, 500, latency_ms)
            raise
        latency_ms = (time.perf_counter() - started_at) * 1000
        service.monitoring.record_http_request(request.method, request.url.path, response.status_code, latency_ms)
        response.headers["X-Request-ID"] = request_id
        return response

    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def require_api_security(request: Request, api_key: str | None = Depends(api_key_header)) -> None:
        enforce_api_key(settings, request, api_key)
        if not settings.rate_limit_enabled:
            return
        identifier = client_identifier(request, api_key=api_key)
        try:
            app.state.rate_limiter.check(identifier)
        except HTTPException:
            log_security_event("rate_limit_exceeded", request, "Too many requests.", identifier=identifier)
            raise

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})

    @app.get("/health", response_model=HealthResponse)
    def healthcheck() -> HealthResponse:
        resolved_source = settings.model_source.strip().lower()
        manifest_path = Path(settings.models_dir) / "manifest.json"
        manifest_present = service.backend_name == "project_models_v1" if resolved_source == "hf_hub" else manifest_path.exists()
        security_profile = build_security_profile(settings)
        return HealthResponse(
            status="ok",
            app_name=settings.app_name,
            app_version=settings.app_version,
            environment=settings.app_env,
            inference_backend=service.active_backend_name,
            model_source=resolved_source,
            model_revision=service.model_revision or "unknown",
            artifact_set_version=service.artifact_set_version,
            models_manifest_present=manifest_present,
            protected_endpoints=bool(security_profile["protected_endpoints"]),
            security_profile=str(security_profile["level"]),
            security_warnings=list(security_profile["warnings"]),
            model_load_error=service.model_load_error,
            sentiment_backend=service.sentiment_backend_name,
            sentiment_model_id=service.sentiment_model_id,
            sentiment_model_revision=service.sentiment_model_revision,
            sentiment_load_error=service.sentiment_load_error,
            prediction_event_store_enabled=bool(settings.prediction_event_store_path),
        )

    @app.post("/v1/analyze", response_model=AnalyzeReviewResponse, dependencies=[Depends(require_api_security)])
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

    @app.get("/metrics", response_model=MetricsResponse, dependencies=[Depends(require_api_security)])
    def metrics_endpoint() -> MetricsResponse:
        return MetricsResponse(**service.get_monitoring_metrics())

    @app.get("/v1/evaluate/default", response_model=EvaluationResponse, dependencies=[Depends(require_api_security)])
    def evaluate_default_dataset(background_tasks: BackgroundTasks) -> EvaluationResponse:
        df = prepare_dataset(load_reference_evaluation_dataset())
        report = service.evaluate_dataframe(df)
        background_tasks.add_task(
            log_evaluation_run,
            report,
            run_name="inference_api_default_evaluation",
        )
        return EvaluationResponse(**report)

    return app


app = create_app()
