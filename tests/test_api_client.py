import httpx

from src.review_insights.api_client import ReviewInsightsApiClient


def test_api_client_routes_calls_to_the_configured_services():
    requests: list[tuple[str, str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, str(request.url), request.headers.get("x-api-key")))
        if request.url.path == "/v1/analyze":
            return httpx.Response(200, json={"review_id": "r1"})
        if request.url.path == "/v1/datasets/default":
            return httpx.Response(200, json={"records": []})
        if request.url.path == "/v1/api/metrics":
            return httpx.Response(200, json={"total_requests": 0})
        if request.url.path == "/v1/feedback":
            return httpx.Response(200, json={"status": "recorded"})
        if request.url.path == "/v1/feedback/recent":
            return httpx.Response(200, json={"records": []})
        return httpx.Response(200, json={"status": "ok"})

    client = ReviewInsightsApiClient(
        api_url="http://api:8000",
        data_url="http://data:8001",
        monitoring_url="http://monitoring:9000",
        api_key="secret",
        transport=httpx.MockTransport(handler),
    )

    client.health()
    client.analyze("good product", "r1")
    client.default_dataset()
    client.metrics()
    client.submit_feedback(
        {
            "review_id": "r1",
            "theme": "sav",
            "corrected_theme_present": 1,
            "corrected_sentiment": "negative",
        }
    )
    client.recent_feedback(limit=5)

    assert requests == [
        ("GET", "http://api:8000/health", "secret"),
        ("POST", "http://api:8000/v1/analyze", "secret"),
        ("GET", "http://data:8001/v1/datasets/default", "secret"),
        ("GET", "http://monitoring:9000/v1/api/metrics", "secret"),
        ("POST", "http://data:8001/v1/feedback", "secret"),
        ("GET", "http://data:8001/v1/feedback/recent?limit=5", "secret"),
    ]
