from fastapi.testclient import TestClient

from src.review_insights.data_api import app, create_app


client = TestClient(app)


def test_data_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "data"
    assert payload["inference_api_url"]


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
    evaluation_client = TestClient(
        create_app(
            evaluation_fetcher=lambda: {
                "summary": {"rows": 40, "backend_name": "project_models_v1+hf_onnx_sentiment_v1"},
                "rows_preview": [],
            }
        )
    )
    response = evaluation_client.get("/v1/evaluate/default")
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


def test_feedback_endpoint_records_and_returns_recent_feedback(monkeypatch, tmp_path):
    feedback_path = tmp_path / "feedback.jsonl"
    monkeypatch.setenv("FEEDBACK_STORE_PATH", str(feedback_path))
    feedback_client = TestClient(create_app())

    created = feedback_client.post(
        "/v1/feedback",
        json={
            "review_id": "r1",
            "theme": "sav",
            "corrected_theme_present": 1,
            "corrected_sentiment": "negative",
            "reviewer": "qa",
            "notes": "Support issue confirmed.",
        },
    )
    recent = feedback_client.get("/v1/feedback/recent")

    assert created.status_code == 200
    assert created.json()["status"] == "recorded"
    assert feedback_path.exists()
    assert recent.status_code == 200
    assert recent.json()["rows"] == 1
    assert recent.json()["records"][0]["theme"] == "sav"

    monkeypatch.delenv("FEEDBACK_STORE_PATH", raising=False)
