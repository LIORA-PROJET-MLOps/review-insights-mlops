import shutil
from pathlib import Path

from pipelines.train_models import build_training_artifacts
from src.review_insights.model_backend import ARTIFACT_FILENAMES


def test_training_pipeline_writes_model_artifacts():
    work_dir = Path("tests_runtime/training_artifacts")
    if work_dir.exists():
        shutil.rmtree(work_dir)

    summary = build_training_artifacts(work_dir)

    assert summary["rows"] >= 1
    assert (work_dir / "manifest.json").exists()
    for filename in ARTIFACT_FILENAMES:
        assert (work_dir / filename).exists()

    shutil.rmtree(work_dir)


def test_training_pipeline_accepts_validated_dataset_path():
    work_dir = Path("tests_runtime/training_artifacts_from_csv")
    if work_dir.exists():
        shutil.rmtree(work_dir)

    dataset_path = Path("data/sample/reviews_sample.csv")
    summary = build_training_artifacts(work_dir, dataset_path=dataset_path)

    assert summary["rows"] >= 1
    assert summary["training_dataset"] == str(dataset_path)
    assert (work_dir / "manifest.json").exists()

    shutil.rmtree(work_dir)
