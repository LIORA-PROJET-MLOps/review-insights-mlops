from __future__ import annotations

import logging
import hashlib
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock

from fastapi import HTTPException, Request, status

from .settings import Settings


security_logger = logging.getLogger("review_insights.security")
LOCAL_ENVIRONMENTS = {"local", "dev", "development", "test"}


def build_security_profile(settings: Settings) -> dict[str, object]:
    warnings: list[str] = []
    non_local = settings.app_env.strip().lower() not in LOCAL_ENVIRONMENTS
    protected_endpoints = settings.require_api_key or bool(settings.api_key)

    if non_local and not protected_endpoints:
        warnings.append("api_key_not_required")
    if "*" in settings.allowed_origins:
        warnings.append("wildcard_cors")
    if "*" in settings.trusted_hosts:
        warnings.append("wildcard_trusted_hosts")
    if non_local and settings.enable_docs:
        warnings.append("docs_enabled")
    if not settings.rate_limit_enabled:
        warnings.append("rate_limit_disabled")
    if settings.model_source.strip().lower() == "hf_hub" and settings.hf_model_revision in {None, "", "main"}:
        warnings.append("mutable_model_revision")

    if warnings:
        level = "local_relaxed" if not non_local else "needs_hardening"
    else:
        level = "staging_ready" if non_local else "local_hardened"

    return {
        "level": level,
        "warnings": warnings,
        "protected_endpoints": protected_endpoints,
        "docs_enabled": settings.enable_docs,
        "allowed_origins": list(settings.allowed_origins),
        "trusted_hosts": list(settings.trusted_hosts),
        "rate_limit_enabled": settings.rate_limit_enabled,
    }


def client_identifier(request: Request, api_key: str | None = None) -> str:
    if api_key:
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
        return f"api_key:{digest}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def log_security_event(event: str, request: Request, detail: str, identifier: str | None = None) -> None:
    security_logger.warning(
        "security_event=%s method=%s path=%s client=%s detail=%s",
        event,
        request.method,
        request.url.path,
        identifier or client_identifier(request),
        detail,
    )


@dataclass
class InMemoryRateLimiter:
    requests_per_window: int
    window_seconds: int
    _requests: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))
    _lock: Lock = field(default_factory=Lock)

    def check(self, identifier: str) -> None:
        if self.requests_per_window <= 0 or self.window_seconds <= 0:
            return

        now = time.monotonic()
        window_start = now - self.window_seconds
        with self._lock:
            bucket = self._requests[identifier]
            while bucket and bucket[0] < window_start:
                bucket.popleft()
            if len(bucket) >= self.requests_per_window:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded.",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)


def enforce_api_key(settings: Settings, request: Request, api_key: str | None) -> None:
    configured_key = settings.api_key
    api_key_required = settings.require_api_key or bool(configured_key)

    if not api_key_required:
        return
    if not configured_key:
        log_security_event("api_key_not_configured", request, "API key is required but missing from configuration.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key protection is required but not configured.",
        )
    if not api_key or not secrets.compare_digest(api_key, configured_key):
        log_security_event("api_key_rejected", request, "Invalid or missing API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
