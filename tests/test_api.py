from fastapi.testclient import TestClient

from src.review_insights.api import app, create_app


client = TestClient(app)


def test_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["inference_backend"] in {"heuristic_rules_v1", "project_models_v1"}
    assert "app_version" in payload
    assert "models_manifest_present" in payload
    assert "model_revision" in payload
    assert "artifact_set_version" in payload
    assert payload["model_source"] in {"local", "hf_hub"}
    assert "security_profile" in payload
    assert isinstance(payload["security_warnings"], list)


def test_healthcheck_has_security_headers():
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_analyze_endpoint():
    response = client.post(
        "/v1/analyze",
        json={
            "review_id": "api_1",
            "review_text": "fast delivery and great product",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["global_sentiment"] in {"positive", "neutral"}
    assert "livraison" in payload["themes_detected"]


def test_analyze_rejects_oversized_payload():
    response = client.post(
        "/v1/analyze",
        json={
            "review_id": "too_big",
            "review_text": "x" * 10001,
        },
    )
    assert response.status_code == 422


def test_metrics_endpoint():
    client.post(
        "/v1/analyze",
        json={"review_id": "api_metrics", "review_text": "customer support never answered my refund request"},
    )
    response = client.get("/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_requests"] >= 1
    assert payload["http_requests_total"] >= 1
    assert "http_status_distribution" in payload


def test_request_id_is_returned_and_http_metrics_are_recorded():
    isolated_client = TestClient(create_app())

    health = isolated_client.get("/health", headers={"X-Request-ID": "req-test-123"})
    metrics = isolated_client.get("/metrics")
    payload = metrics.json()

    assert health.headers["x-request-id"] == "req-test-123"
    assert payload["http_requests_total"] >= 1
    assert payload["http_endpoint_distribution"]["GET /health"] == 1


def test_evaluate_default_dataset_endpoint():
    response = client.get("/v1/evaluate/default")
    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert payload["summary"]["rows"] == 40
    assert payload["summary"]["theme_exact_match"] < 1.0


def test_api_key_protection_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret-key")
    secured_client = TestClient(create_app())

    unauthorized = secured_client.post(
        "/v1/analyze",
        json={"review_id": "auth_1", "review_text": "fast delivery and good product"},
    )
    assert unauthorized.status_code == 401

    authorized = secured_client.post(
        "/v1/analyze",
        headers={"X-API-Key": "secret-key"},
        json={"review_id": "auth_2", "review_text": "fast delivery and good product"},
    )
    assert authorized.status_code == 200

    monkeypatch.delenv("API_KEY", raising=False)


def test_api_key_required_without_config_returns_service_error(monkeypatch):
    monkeypatch.setenv("REQUIRE_API_KEY", "true")
    monkeypatch.delenv("API_KEY", raising=False)
    secured_client = TestClient(create_app())

    response = secured_client.post(
        "/v1/analyze",
        json={"review_id": "auth_required", "review_text": "fast delivery and good product"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "API key protection is required but not configured."
    monkeypatch.delenv("REQUIRE_API_KEY", raising=False)


def test_healthcheck_flags_unhardened_staging_configuration(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("REQUIRE_API_KEY", "false")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("TRUSTED_HOSTS", "*")
    monkeypatch.setenv("ENABLE_DOCS", "true")

    staging_client = TestClient(create_app())
    payload = staging_client.get("/health").json()

    assert payload["security_profile"] == "needs_hardening"
    assert "api_key_not_required" in payload["security_warnings"]
    assert "wildcard_cors" in payload["security_warnings"]
    assert "wildcard_trusted_hosts" in payload["security_warnings"]
    assert "docs_enabled" in payload["security_warnings"]

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("REQUIRE_API_KEY", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("TRUSTED_HOSTS", raising=False)
    monkeypatch.delenv("ENABLE_DOCS", raising=False)


def test_rate_limit_blocks_excess_requests(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    limited_client = TestClient(create_app())
    payload = {"review_id": "rate_limit", "review_text": "fast delivery and good product"}

    first = limited_client.post("/v1/analyze", json=payload)
    second = limited_client.post("/v1/analyze", json=payload)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"]
    monkeypatch.delenv("RATE_LIMIT_ENABLED", raising=False)
    monkeypatch.delenv("RATE_LIMIT_REQUESTS", raising=False)
    monkeypatch.delenv("RATE_LIMIT_WINDOW_SECONDS", raising=False)
