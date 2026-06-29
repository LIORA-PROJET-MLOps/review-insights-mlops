from src.review_insights.service import ReviewAnalysisService
from src.review_insights.dataset import load_default_dataset, prepare_dataset
from src.review_insights.transformer_sentiment import SentimentPrediction


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


def test_optional_transformer_overrides_only_global_sentiment(monkeypatch):
    class FakeSentimentBackend:
        name = "hf_onnx_sentiment_v1"
        model_id = "test/sentiment"
        revision = "immutable-test-revision"

        def __init__(self, **_kwargs):
            pass

        def predict(self, _text):
            return SentimentPrediction(
                label="positive",
                confidence=0.91,
                probabilities={"negative": 0.02, "neutral": 0.07, "positive": 0.91},
            )

    monkeypatch.setenv("SENTIMENT_BACKEND", "hf_onnx")
    monkeypatch.setattr("src.review_insights.service.OnnxSentimentBackend", FakeSentimentBackend)

    service = ReviewAnalysisService()
    result = service.analyze(
        review_text="customer support never answered and the refund process was slow",
        review_id="svc_transformer",
    )

    assert result.global_sentiment == "positive"
    assert result.score_global == 0.91
    assert "sav" in result.themes_detected
    assert service.sentiment_backend_name == "hf_onnx_sentiment_v1"
    assert result.sentiment_conflict is True
    assert result.sentiment_conflict_themes == ["sav"]
    assert result.needs_human_review is True
    assert result.provenance.sentiment_model_id == "test/sentiment"
    assert result.provenance.sentiment_model_revision == "immutable-test-revision"
    assert result.provenance.inference_backend == "project_models_v1+hf_onnx_sentiment_v1"
    metrics = service.get_monitoring_metrics()
    assert metrics["sentiment_conflict_requests"] == 1
    assert metrics["sentiment_conflict_rate"] == 1.0


def test_optional_transformer_load_failure_keeps_project_backend(monkeypatch):
    monkeypatch.setenv("SENTIMENT_BACKEND", "project")
    baseline_service = ReviewAnalysisService()
    baseline = baseline_service.analyze(
        review_text="customer support never answered",
        review_id="svc_fallback_baseline",
    )

    class BrokenSentimentBackend:
        def __init__(self, **_kwargs):
            raise RuntimeError("model unavailable")

    monkeypatch.setenv("SENTIMENT_BACKEND", "hf_onnx")
    monkeypatch.setattr("src.review_insights.service.OnnxSentimentBackend", BrokenSentimentBackend)

    service = ReviewAnalysisService()
    result = service.analyze(
        review_text="customer support never answered",
        review_id="svc_fallback",
    )

    assert result.global_sentiment == baseline.global_sentiment
    assert result.score_global == baseline.score_global
    assert service.sentiment_backend_name == service.backend_name
    assert service.sentiment_load_error == "model unavailable"
    assert result.provenance.sentiment_backend == service.backend_name


def test_evaluation_reports_the_effective_sentiment_backend(monkeypatch):
    class FakeSentimentBackend:
        name = "hf_onnx_sentiment_v1"
        model_id = "test/sentiment"
        revision = "immutable-test-revision"

        def __init__(self, **_kwargs):
            pass

        def predict(self, _text):
            return SentimentPrediction(
                label="positive",
                confidence=0.91,
                probabilities={"negative": 0.02, "neutral": 0.07, "positive": 0.91},
            )

    monkeypatch.setenv("SENTIMENT_BACKEND", "hf_onnx")
    monkeypatch.setattr("src.review_insights.service.OnnxSentimentBackend", FakeSentimentBackend)
    service = ReviewAnalysisService()

    report = service.evaluate_dataframe(prepare_dataset(load_default_dataset().head(2)))

    assert report["summary"]["backend_name"] == "project_models_v1+hf_onnx_sentiment_v1"
    assert report["summary"]["sentiment_backend_name"] == "hf_onnx_sentiment_v1"
    assert report["summary"]["sentiment_model_revision"] == "immutable-test-revision"
