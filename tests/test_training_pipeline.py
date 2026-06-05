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
    assert summary["threshold_strategy"] == "fixed"
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


def test_training_pipeline_tunes_thresholds_with_validation_dataset():
    work_dir = Path("tests_runtime/training_artifacts_with_validation")
    if work_dir.exists():
        shutil.rmtree(work_dir)

    training_path = Path("data/sample/reviews_sample.csv")
    validation_path = Path("data/sample/reviews_poc_test.csv")
    summary = build_training_artifacts(
        work_dir,
        dataset_path=training_path,
        validation_dataset_path=validation_path,
    )

    assert summary["threshold_strategy"] == "validation_f1_tuned"
    assert summary["validation_dataset"] == str(validation_path)
    assert set(summary["theme_thresholds"]) == {"livraison", "sav", "produit"}
    assert summary["threshold_tuning_report"]["livraison"]["validation_f1"] >= 0.0

    shutil.rmtree(work_dir)


def test_training_pipeline_accepts_parquet_dataset():
    work_dir = Path("tests_runtime/training_artifacts_from_parquet")
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    dataset_path = work_dir / "reviews_sample.parquet"
    import pandas as pd

    pd.read_csv("data/sample/reviews_sample.csv").to_parquet(dataset_path, index=False)
    summary = build_training_artifacts(work_dir / "models", dataset_path=dataset_path)

    assert summary["training_rows"] == 3
    assert summary["training_dataset"] == str(dataset_path)
    assert (work_dir / "models" / "manifest.json").exists()

    shutil.rmtree(work_dir)
