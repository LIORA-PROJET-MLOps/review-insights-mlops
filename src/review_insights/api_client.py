from __future__ import annotations

import os
from typing import Any

import httpx


class ReviewInsightsClientError(RuntimeError):
    pass


class ReviewInsightsApiClient:
    def __init__(
        self,
        *,
        api_url: str,
        data_url: str,
        monitoring_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.data_url = data_url.rstrip("/")
        self.monitoring_url = monitoring_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @classmethod
    def from_env(cls) -> "ReviewInsightsApiClient":
        return cls(
            api_url=os.getenv("API_URL", "http://localhost:8000"),
            data_url=os.getenv("DATA_URL", "http://localhost:8001"),
            monitoring_url=os.getenv("MONITORING_URL", "http://localhost:9000"),
            api_key=os.getenv("API_KEY") or None,
            timeout_seconds=float(os.getenv("SERVICE_TIMEOUT_SECONDS", "15")),
        )

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def _request(self, base_url: str, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.request(method, f"{base_url}{path}", headers=headers, **kwargs)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ReviewInsightsClientError(f"Service call failed for {path}: {exc}") from exc
        payload = response.json()
        if not isinstance(payload, dict):
            raise ReviewInsightsClientError(f"Service returned a non-object JSON payload for {path}.")
        return payload

    def health(self) -> dict[str, Any]:
        return self._request(self.api_url, "GET", "/health")

    def analyze(self, review_text: str, review_id: str, threshold: float | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "review_text": review_text,
            "review_id": review_id,
        }
        if threshold is not None:
            payload["threshold"] = threshold
        return self._request(self.api_url, "POST", "/v1/analyze", json=payload)

    def metrics(self) -> dict[str, Any]:
        return self._request(self.monitoring_url, "GET", "/v1/api/metrics")

    def default_dataset(self) -> dict[str, Any]:
        return self._request(self.data_url, "GET", "/v1/datasets/default")

    def evaluate_default(self) -> dict[str, Any]:
        return self._request(self.data_url, "GET", "/v1/evaluate/default")
