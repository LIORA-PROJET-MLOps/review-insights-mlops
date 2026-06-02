import shutil
from pathlib import Path

from pipelines.ingest_and_retrain import ingest_and_retrain
from src.review_insights.model_backend import ARTIFACT_FILENAMES


def test_ingest_and_retrain_pipeline_writes_data_and_model_artifacts():
    work_dir = Path("tests_runtime/ingest_and_retrain")
    if work_dir.exists():
        shutil.rmtree(work_dir)

    result = ingest_and_retrain(
        Path("data/sample/reviews_sample.csv"),
        data_root=work_dir / "data",
        dataset_version="pipeline_test",
        output_dir=work_dir / "models",
    )

    ingestion = result["ingestion"]
    training = result["training"]
    assert ingestion["rows_ingested"] == 3
    assert ingestion["rows_valid"] == 3
    assert Path(ingestion["validated_path"]).exists()
    assert training["rows"] == 3
    assert training["training_dataset"] == ingestion["validated_path"]
    for filename in ARTIFACT_FILENAMES:
        assert (work_dir / "models" / filename).exists()

    shutil.rmtree(work_dir)
