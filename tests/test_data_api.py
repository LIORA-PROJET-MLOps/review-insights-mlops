from fastapi.testclient import TestClient
import pandas as pd

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


def test_data_service_exposes_latest_ready_orchestrated_dataset(monkeypatch, tmp_path):
    data_root = tmp_path / "data"
    validated_dir = data_root / "validated"
    registry_dir = data_root / "registry"
    validated_dir.mkdir(parents=True)
    registry_dir.mkdir(parents=True)
    dataset_path = validated_dir / "training_dataset_ready_v1.csv"
    pd.DataFrame(
        [
            {
                "review_id": "orchestrated_1",
                "review_title": "Fast delivery",
                "review_body": "The parcel arrived early.",
                "sentiment_label": "positive",
                "theme_livraison": 1,
                "theme_sav": 0,
                "theme_produit": 0,
            }
        ]
    ).to_csv(dataset_path, index=False)
    (registry_dir / "dataset_ready_v1.json").write_text(
        '{"quality_status":"ready","validated_path":"'
        + dataset_path.as_posix()
        + '"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("ORCHESTRATOR_DATA_ROOT", str(data_root))

    response = TestClient(create_app()).get("/v1/datasets/default")

    assert response.status_code == 200
    assert response.json()["rows"] == 1
    assert response.json()["records"][0]["review_id"] == "orchestrated_1"
    assert response.json()["source"] == str(dataset_path)


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


def test_drift_endpoint_returns_latest_report(monkeypatch, tmp_path):
    report_path = tmp_path / "latest_drift_report.json"
    report_path.write_text(
        '{"status":"stable","recommendation":"continue_monitoring"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("DRIFT_REPORT_PATH", str(report_path))

    response = TestClient(create_app()).get("/v1/drift/latest")

    assert response.status_code == 200
    assert response.json()["status"] == "stable"


def test_drift_endpoint_explains_missing_report(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIFT_REPORT_PATH", str(tmp_path / "missing.json"))

    response = TestClient(create_app()).get("/v1/drift/latest")

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
