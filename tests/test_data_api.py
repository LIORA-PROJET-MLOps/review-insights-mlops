from fastapi.testclient import TestClient

from src.review_insights.data_api import app


client = TestClient(app)


def test_data_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "data"


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

