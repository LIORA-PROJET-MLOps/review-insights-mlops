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


def test_evaluate_default_dataset_endpoint():
    response = client.get("/v1/evaluate/default")
    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert payload["summary"]["rows"] >= 1


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
