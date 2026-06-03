from src.review_insights.monitoring_api import _format_prometheus


def test_prometheus_formatter_exports_core_metrics():
    payload = _format_prometheus(
        {
            "total_requests": 3,
            "human_review_requests": 1,
            "human_review_rate": 0.3333,
            "sentiment_distribution": {"negative": 2},
            "theme_distribution": {"sav": 2},
            "backend_distribution": {"heuristic_rules_v1": 3},
        }
    )

    assert "review_insights_requests_total 3" in payload
    assert 'review_insights_sentiment_total{sentiment="negative"} 2' in payload
    assert 'review_insights_theme_total{theme="sav"} 2' in payload
    assert 'review_insights_inference_latency_ms{stat="p95"} 0.0' in payload
