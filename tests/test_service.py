from src.review_insights.service import ReviewAnalysisService


def test_service_returns_negative_support_signal():
    service = ReviewAnalysisService()
    result = service.analyze(
        review_text="customer support never answered and the refund process was slow",
        review_id="svc_1",
    )
    assert result.global_sentiment in {"negative", "neutral"}
    assert "sav" in result.themes_detected
