from fastapi.testclient import TestClient

from src.review_insights.data_api import app, create_app


client = TestClient(app)


def test_data_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "data"
    assert "model_revision" in payload
    assert "artifact_set_version" in payload


def test_default_dataset_endpoint():
    response = client.get("/v1/datasets/default")
    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"] >= 1
    assert "review_id" in payload["columns"]
    assert len(payload["records"]) == payload["rows"]


def test_default_dataset_profile_endpoint():
    response = client.get("/v1/datasets/default/profile")
    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"] >= 1
    assert "theme_counts" in payload


def test_reference_evaluation_endpoint_uses_test_dataset():
    response = client.get("/v1/evaluate/default")
    assert response.status_code == 200
    assert response.json()["summary"]["rows"] == 40


def test_data_endpoints_use_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret-key")
    secured_client = TestClient(create_app())

    unauthorized = secured_client.get("/v1/datasets/default")
    authorized = secured_client.get("/v1/datasets/default", headers={"X-API-Key": "secret-key"})

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    monkeypatch.delenv("API_KEY", raising=False)
