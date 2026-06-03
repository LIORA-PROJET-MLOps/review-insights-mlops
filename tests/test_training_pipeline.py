import shutil
from pathlib import Path

from pipelines.train_models import build_training_artifacts
from src.review_insights.model_backend import ARTIFACT_FILENAMES


def test_training_pipeline_writes_model_artifacts():
    work_dir = Path("tests_runtime/training_artifacts")
    if work_dir.exists():
        shutil.rmtree(work_dir)

    summary = build_training_artifacts(work_dir)

    assert summary["rows"] == 40
    assert summary["evaluation_status"] == "completed"
    assert summary["training_dataset"] == "default_reviews"
    assert Path(summary["evaluation_dataset"]).name == "reviews_poc_test.csv"
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

    assert summary["rows"] == 0
    assert summary["training_rows"] == 3
    assert summary["evaluation_status"] == "not_run"
    assert summary["training_dataset"] == str(dataset_path)
    assert (work_dir / "manifest.json").exists()

    shutil.rmtree(work_dir)


def test_training_pipeline_accepts_independent_evaluation_dataset():
    work_dir = Path("tests_runtime/training_artifacts_with_evaluation")
    if work_dir.exists():
        shutil.rmtree(work_dir)

    training_path = Path("data/sample/reviews_sample.csv")
    evaluation_path = Path("data/sample/reviews_poc_test.csv")
    summary = build_training_artifacts(
        work_dir,
        dataset_path=training_path,
        evaluation_dataset_path=evaluation_path,
    )

    assert summary["training_rows"] == 3
    assert summary["rows"] == 40
    assert summary["training_dataset"] == str(training_path)
    assert summary["evaluation_dataset"] == str(evaluation_path)

    shutil.rmtree(work_dir)
