from src.review_insights.service import ReviewAnalysisService
from src.review_insights.dataset import load_default_dataset, prepare_dataset


def test_service_returns_negative_support_signal():
    service = ReviewAnalysisService()
    result = service.analyze(
        review_text="customer support never answered and the refund process was slow",
        review_id="svc_1",
    )
    assert result.global_sentiment in {"negative", "neutral"}
    assert "sav" in result.themes_detected


def test_analyze_dataframe_preserves_theme_ground_truth():
    service = ReviewAnalysisService()
    df = prepare_dataset(load_default_dataset().head(1))

    enriched = service.analyze_dataframe(df)

    assert "true_theme_livraison" in enriched.columns
    assert enriched.iloc[0]["true_theme_livraison"] == df.iloc[0]["theme_livraison"]
