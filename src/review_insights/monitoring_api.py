from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Request, Response
from fastapi.security import APIKeyHeader

from .security import enforce_api_key
from .settings import get_settings


def _api_base_url() -> str:
    return os.getenv("API_URL", "http://api:8000").rstrip("/")


async def _fetch_json(path: str) -> dict[str, Any]:
    headers = {}
    api_key = os.getenv("API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{_api_base_url()}{path}", headers=headers)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {"payload": payload}


def _format_prometheus(metrics: dict[str, Any]) -> str:
    lines = [
        "# HELP review_insights_requests_total Total analysis requests processed by the API.",
        "# TYPE review_insights_requests_total counter",
        f"review_insights_requests_total {metrics.get('total_requests', 0)}",
        "# HELP review_insights_human_review_requests_total Requests flagged for human review.",
        "# TYPE review_insights_human_review_requests_total counter",
        f"review_insights_human_review_requests_total {metrics.get('human_review_requests', 0)}",
        "# HELP review_insights_human_review_rate Ratio of requests flagged for human review.",
        "# TYPE review_insights_human_review_rate gauge",
        f"review_insights_human_review_rate {metrics.get('human_review_rate', 0.0)}",
        "# HELP review_insights_sentiment_conflict_requests_total Predictions with conflicting global and theme sentiments.",
        "# TYPE review_insights_sentiment_conflict_requests_total counter",
        f"review_insights_sentiment_conflict_requests_total {metrics.get('sentiment_conflict_requests', 0)}",
        "# HELP review_insights_sentiment_conflict_rate Ratio of predictions with sentiment conflicts.",
        "# TYPE review_insights_sentiment_conflict_rate gauge",
        f"review_insights_sentiment_conflict_rate {metrics.get('sentiment_conflict_rate', 0.0)}",
        "# HELP review_insights_inference_latency_ms Inference latency in milliseconds.",
        "# TYPE review_insights_inference_latency_ms gauge",
        f'review_insights_inference_latency_ms{{stat="avg"}} {metrics.get("inference_latency_ms_avg", 0.0)}',
        f'review_insights_inference_latency_ms{{stat="p50"}} {metrics.get("inference_latency_ms_p50", 0.0)}',
        f'review_insights_inference_latency_ms{{stat="p95"}} {metrics.get("inference_latency_ms_p95", 0.0)}',
        "# HELP review_insights_http_requests_total Total HTTP requests observed by the API.",
        "# TYPE review_insights_http_requests_total counter",
        f"review_insights_http_requests_total {metrics.get('http_requests_total', 0)}",
        "# HELP review_insights_http_error_requests_total HTTP 5xx requests observed by the API.",
        "# TYPE review_insights_http_error_requests_total counter",
        f"review_insights_http_error_requests_total {metrics.get('http_error_requests', 0)}",
        "# HELP review_insights_http_error_rate Ratio of HTTP 5xx requests.",
        "# TYPE review_insights_http_error_rate gauge",
        f"review_insights_http_error_rate {metrics.get('http_error_rate', 0.0)}",
        "# HELP review_insights_http_latency_ms HTTP request latency in milliseconds.",
        "# TYPE review_insights_http_latency_ms gauge",
        f'review_insights_http_latency_ms{{stat="avg"}} {metrics.get("http_latency_ms_avg", 0.0)}',
        f'review_insights_http_latency_ms{{stat="p50"}} {metrics.get("http_latency_ms_p50", 0.0)}',
        f'review_insights_http_latency_ms{{stat="p95"}} {metrics.get("http_latency_ms_p95", 0.0)}',
    ]

    for sentiment, value in metrics.get("sentiment_distribution", {}).items():
        lines.append(f'review_insights_sentiment_total{{sentiment="{sentiment}"}} {value}')
    for theme, value in metrics.get("theme_distribution", {}).items():
        lines.append(f'review_insights_theme_total{{theme="{theme}"}} {value}')
    for backend, value in metrics.get("backend_distribution", {}).items():
        lines.append(f'review_insights_backend_total{{backend="{backend}"}} {value}')
    for backend, value in metrics.get("sentiment_backend_distribution", {}).items():
        lines.append(f'review_insights_sentiment_backend_total{{backend="{backend}"}} {value}')
    for status, value in metrics.get("http_status_distribution", {}).items():
        lines.append(f'review_insights_http_status_total{{status="{status}"}} {value}')
    for endpoint, value in metrics.get("http_endpoint_distribution", {}).items():
        lines.append(f'review_insights_http_endpoint_total{{endpoint="{endpoint}"}} {value}')

    return "\n".join(lines) + "\n"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} Monitoring Service",
        version=settings.app_version,
        summary="Monitoring gateway for Review Insights+ API metrics.",
    )
    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def require_api_security(request: Request, api_key: str | None = Depends(api_key_header)) -> None:
        enforce_api_key(settings, request, api_key)

    @app.get("/health")
    async def healthcheck() -> dict:
        try:
            api_health = await _fetch_json("/health")
            api_status = api_health.get("status", "unknown")
        except Exception as exc:
            api_health = {"error": str(exc)}
            api_status = "unreachable"
        return {
            "status": "ok" if api_status == "ok" else "degraded",
            "service": "monitoring",
            "api_url": _api_base_url(),
            "api": api_health,
        }

    @app.get("/v1/api/health", dependencies=[Depends(require_api_security)])
    async def api_health() -> dict:
        return await _fetch_json("/health")

    @app.get("/v1/api/metrics", dependencies=[Depends(require_api_security)])
    async def api_metrics() -> dict:
        return await _fetch_json("/metrics")

    @app.get("/metrics", dependencies=[Depends(require_api_security)])
    async def prometheus_metrics() -> Response:
        metrics = await _fetch_json("/metrics")
        return Response(content=_format_prometheus(metrics), media_type="text/plain; version=0.0.4")

    return app


app = create_app()
