import os
import sys
import shutil
from pathlib import Path
from types import SimpleNamespace

from src.review_insights.model_backend import ARTIFACT_FILENAMES
from src.review_insights.mlflow_tracking import _configure_mlflow_console_output, log_evaluation_run, log_training_run
from src.review_insights.settings import Settings


def test_mlflow_console_urls_are_suppressed_by_default(monkeypatch):
    monkeypatch.delenv("MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT", raising=False)
    monkeypatch.delenv("MLFLOW_PRINT_MODEL_URLS_ON_CREATION", raising=False)

    _configure_mlflow_console_output()

    assert os.environ["MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT"] == "true"
    assert os.environ["MLFLOW_PRINT_MODEL_URLS_ON_CREATION"] == "false"


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


def test_mlflow_training_disabled_returns_status():
    result = log_training_run(
        {"rows": 2, "sentiment_accuracy": 0.5},
        model_artifact_dir="missing",
        settings=Settings(mlflow_tracking_enabled=False),
    )

    assert result.status == "disabled"
    assert result.reason == "MLFLOW_TRACKING_ENABLED is false."


def test_mlflow_training_registers_candidate_model(monkeypatch):
    work_dir = Path("tests_runtime/mlflow_training_stub")
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

    class FakeRun:
        info = SimpleNamespace(run_id="training_run_123")

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    class FakeClient:
        def __init__(self):
            self.version_tags = []
            self.aliases = []

        def set_model_version_tag(self, name, version, key, value):
            self.version_tags.append((name, version, key, value))

        def set_registered_model_alias(self, name, alias, version):
            self.aliases.append((name, alias, version))

    fake_client = FakeClient()
    fake_mlflow = SimpleNamespace(
        params=[],
        metrics=[],
        tags=[],
        artifact_dirs=[],
        registered=[],
        set_tracking_uri=lambda *_: None,
        set_experiment=lambda *_: None,
        start_run=lambda **_: FakeRun(),
    )
    fake_mlflow.log_params = lambda params: fake_mlflow.params.append(params)
    fake_mlflow.log_metric = lambda key, value: fake_mlflow.metrics.append((key, value))
    fake_mlflow.set_tags = lambda tags: fake_mlflow.tags.append(tags)
    fake_mlflow.log_artifacts = lambda path, artifact_path=None: fake_mlflow.artifact_dirs.append((path, artifact_path))
    fake_mlflow.pyfunc = SimpleNamespace(
        log_model=lambda **kwargs: fake_mlflow.registered.append(kwargs) or SimpleNamespace(registered_model_version="7")
    )
    fake_mlflow.tracking = SimpleNamespace(MlflowClient=lambda: fake_client)
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)

    result = log_training_run(
        {
            "rows": 40,
            "sentiment_accuracy": 0.9,
            "theme_exact_match": 0.8,
            "backend_name": "project_models_v1",
            "training_dataset": "data/validated/training_dataset_poc_test_40.csv",
            "threshold": 0.5,
        },
        model_artifact_dir=model_dir,
        settings=Settings(
            mlflow_tracking_enabled=True,
            mlflow_tracking_uri=str(work_dir / "mlruns"),
            mlflow_experiment_name="review-insights-training",
        ),
        register_model=True,
        registered_model_name="review-insights-project-models",
    )

    assert result.status == "logged"
    assert result.run_id == "training_run_123"
    assert result.registered_model_name == "review-insights-project-models"
    assert result.registered_model_version == "7"
    assert result.model_stage == "candidate"
    assert fake_mlflow.artifact_dirs == [(str(model_dir), "model")]
    assert fake_mlflow.registered[0]["registered_model_name"] == "review-insights-project-models"
    assert fake_mlflow.registered[0]["artifact_path"] == "registered_model"
    assert fake_client.aliases == [("review-insights-project-models", "candidate", "7")]
    assert ("review-insights-project-models", "7", "stage", "candidate") in fake_client.version_tags

    shutil.rmtree(work_dir)


def test_mlflow_training_registry_falls_back_to_logged_artifacts(monkeypatch):
    work_dir = Path("tests_runtime/mlflow_training_fallback_stub")
    if work_dir.exists():
        shutil.rmtree(work_dir)

    model_dir = work_dir / "models"
    model_dir.mkdir(parents=True)
    for filename in ARTIFACT_FILENAMES:
        (model_dir / filename).write_text("stub", encoding="utf-8")

    class FakeRun:
        info = SimpleNamespace(run_id="training_run_fallback")

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    class FakeClient:
        def __init__(self):
            self.created_models = []
            self.created_versions = []
            self.version_tags = []
            self.aliases = []

        def create_registered_model(self, name, tags=None, description=None):
            self.created_models.append((name, tags, description))

        def create_model_version(self, name, source, run_id=None, tags=None):
            self.created_versions.append((name, source, run_id, tags))
            return SimpleNamespace(version="3", run_id=run_id)

        def set_model_version_tag(self, name, version, key, value):
            self.version_tags.append((name, version, key, value))

        def set_registered_model_alias(self, name, alias, version):
            self.aliases.append((name, alias, version))

    fake_client = FakeClient()
    fake_mlflow = SimpleNamespace(
        params=[],
        metrics=[],
        artifact_dirs=[],
        set_tracking_uri=lambda *_: None,
        set_experiment=lambda *_: None,
        start_run=lambda **_: FakeRun(),
    )
    fake_mlflow.log_params = lambda params: fake_mlflow.params.append(params)
    fake_mlflow.log_metric = lambda key, value: fake_mlflow.metrics.append((key, value))
    fake_mlflow.log_artifacts = lambda path, artifact_path=None: fake_mlflow.artifact_dirs.append((path, artifact_path))
    fake_mlflow.pyfunc = SimpleNamespace(log_model=lambda **_: (_ for _ in ()).throw(PermissionError("tmp denied")))
    fake_mlflow.tracking = SimpleNamespace(MlflowClient=lambda: fake_client)
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)

    result = log_training_run(
        {
            "rows": 40,
            "sentiment_accuracy": 0.9,
            "theme_exact_match": 0.8,
            "training_dataset": "data/validated/training_dataset_poc_test_40.csv",
        },
        model_artifact_dir=model_dir,
        settings=Settings(mlflow_tracking_enabled=True),
        register_model=True,
        registered_model_name="review-insights-project-models",
    )

    assert result.status == "logged"
    assert result.registered_model_version == "3"
    assert result.reason == "pyfunc registration failed; registered logged artifacts instead (PermissionError)."
    assert fake_client.created_versions == [
        (
            "review-insights-project-models",
            "runs:/training_run_fallback/model",
            "training_run_fallback",
            {"registry_method": "logged_artifacts_fallback"},
        )
    ]
    assert fake_client.aliases == [("review-insights-project-models", "candidate", "3")]

    shutil.rmtree(work_dir)
