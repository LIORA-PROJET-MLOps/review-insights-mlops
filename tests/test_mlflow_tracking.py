from src.review_insights.mlflow_tracking import log_evaluation_run
from src.review_insights.settings import Settings


def test_mlflow_tracking_disabled_returns_status():
    result = log_evaluation_run(
        {"summary": {"rows": 2, "sentiment_accuracy": 0.5}},
        settings=Settings(mlflow_tracking_enabled=False),
    )

    assert result.status == "disabled"
    assert result.reason == "MLFLOW_TRACKING_ENABLED is false."


def test_mlflow_tracking_without_package_is_skipped(monkeypatch):
    def fail_import(name, *args, **kwargs):
        if name == "mlflow":
            raise ImportError("missing mlflow")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr("builtins.__import__", fail_import)

    result = log_evaluation_run(
        {"summary": {"rows": 2, "sentiment_accuracy": 0.5}},
        settings=Settings(mlflow_tracking_enabled=True),
    )

    assert result.status == "skipped"
    assert result.reason == "mlflow package is not installed."
