import sys
import shutil
from pathlib import Path
from types import SimpleNamespace

from src.review_insights.model_backend import ARTIFACT_FILENAMES
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


def test_mlflow_tracking_logs_model_artifacts(monkeypatch):
    work_dir = Path("tests_runtime/mlflow_stub")
    if work_dir.exists():
        shutil.rmtree(work_dir)

    model_dir = work_dir / "models"
    model_dir.mkdir(parents=True)
    for filename in ARTIFACT_FILENAMES:
        (model_dir / filename).write_text("stub", encoding="utf-8")
    (model_dir / "manifest.json").write_text(
        '{"project": "Review Insights+", "artifact_set_version": "0.1.0", "language_scope": "english_reviews_only"}',
        encoding="utf-8",
    )
    report_path = work_dir / "report.json"
    report_path.write_text("{}", encoding="utf-8")

    class FakeRun:
        info = SimpleNamespace(run_id="run_123")

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    fake_mlflow = SimpleNamespace(
        params=[],
        metrics=[],
        artifact_files=[],
        artifact_dirs=[],
        set_tracking_uri=lambda *_: None,
        set_experiment=lambda *_: None,
        start_run=lambda **_: FakeRun(),
    )
    fake_mlflow.log_params = lambda params: fake_mlflow.params.append(params)
    fake_mlflow.log_metric = lambda key, value: fake_mlflow.metrics.append((key, value))
    fake_mlflow.log_artifact = lambda path: fake_mlflow.artifact_files.append(path)
    fake_mlflow.log_artifacts = lambda path, artifact_path=None: fake_mlflow.artifact_dirs.append((path, artifact_path))
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)

    result = log_evaluation_run(
        {"summary": {"rows": 2, "sentiment_accuracy": 0.5, "backend_name": "project_models_v1"}},
        settings=Settings(
            mlflow_tracking_enabled=True,
            mlflow_tracking_uri=str(work_dir / "mlruns"),
            models_dir=str(model_dir),
        ),
        artifact_paths=[report_path],
    )

    assert result.status == "logged"
    assert result.run_id == "run_123"
    assert result.model_logged is True
    assert result.artifact_count >= len(ARTIFACT_FILENAMES) + 1
    assert fake_mlflow.artifact_dirs == [(str(model_dir), "model")]
    assert fake_mlflow.params[0]["model_artifacts_present"] == "true"

    shutil.rmtree(work_dir)
