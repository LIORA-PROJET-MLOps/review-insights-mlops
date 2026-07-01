from pathlib import Path
import json
import shutil

import pandas as pd
import pytest

from src.review_insights.data_store import (
    ingest_csv_dataset,
    latest_validated_dataset,
    load_training_dataset,
    validate_training_dataset,
)


def test_git_commit_prefers_deployment_metadata(monkeypatch):
    from src.review_insights.data_store import _current_git_commit

    monkeypatch.setenv("GIT_COMMIT_SHA", "deployment-sha-123")

    assert _current_git_commit() == "deployment-sha-123"


def _clean_work_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def test_ingest_csv_dataset_writes_local_store_artifacts():
    work_dir = Path("tests_runtime/data_store_ingestion")
    _clean_work_dir(work_dir)
    source_path = work_dir / "incoming_reviews.csv"
    source_path.write_text(
        "\n".join(
            [
                "review_id,review_title,review_body,sentiment_label,theme_livraison,theme_sav,theme_produit",
                "r1,Fast delivery,The parcel arrived quickly.,positive,1,0,0",
                "r2,Bad support,Support never answered.,negative,0,1,0",
                "r3,Rejected row,,positive,0,0,1",
            ]
        ),
        encoding="utf-8",
    )

    result = ingest_csv_dataset(source_path, work_dir / "data", dataset_version="20260602T100000Z")

    assert result.rows_ingested == 3
    assert result.rows_valid == 2
    assert result.rows_rejected == 1
    assert Path(result.raw_archive_path).exists()
    assert Path(result.processed_path).exists()
    assert Path(result.processed_parquet_path).exists()
    assert Path(result.validated_path).exists()
    assert Path(result.validated_parquet_path).exists()
    assert Path(result.quarantine_path).exists()
    assert Path(result.quarantine_parquet_path).exists()
    assert Path(result.annotation_queue_path).exists()
    assert Path(result.annotation_queue_parquet_path).exists()
    assert Path(result.quality_report_path).exists()
    assert Path(result.manifest_path).exists()
    assert result.source_sha256
    assert result.processed_sha256
    assert result.processed_parquet_sha256
    assert result.validated_sha256
    assert result.validated_parquet_sha256
    assert result.annotation_rows == 2
    assert result.quality_status == "not_ready"
    assert result.dataset_contract_sha256
    assert result.quality_policy_sha256
    assert result.git_commit
    assert result.pipeline_name == "ingest_csv_dataset"
    assert result.split_rows == {"train": 2, "validation": 0, "test": 0}
    assert latest_validated_dataset(work_dir / "data") == Path(result.validated_parquet_path)

    training_df = load_training_dataset(Path(result.validated_parquet_path))
    assert list(training_df["review_id"]) == ["r1", "r2"]

    shutil.rmtree(work_dir)


def test_ingest_csv_dataset_deduplicates_review_ids():
    work_dir = Path("tests_runtime/data_store_dedup")
    _clean_work_dir(work_dir)
    source_path = work_dir / "incoming_reviews.csv"
    pd.DataFrame(
        [
            {
                "review_id": "r1",
                "review_title": "Old",
                "review_body": "Old text.",
                "sentiment_label": "negative",
                "theme_livraison": 0,
                "theme_sav": 1,
                "theme_produit": 0,
            },
            {
                "review_id": "r1",
                "review_title": "New",
                "review_body": "New text.",
                "sentiment_label": "positive",
                "theme_livraison": 1,
                "theme_sav": 0,
                "theme_produit": 0,
            },
        ]
    ).to_csv(source_path, index=False)

    result = ingest_csv_dataset(source_path, work_dir / "data", dataset_version="20260602T110000Z")

    training_df = load_training_dataset(Path(result.validated_path))
    assert result.duplicate_review_ids == 1
    assert result.rows_rejected == 1
    assert len(training_df) == 1
    assert training_df.iloc[0]["review_title"] == "New"
    rejected_df = pd.read_csv(result.quarantine_path)
    assert rejected_df.iloc[0]["rejection_reasons"] == "duplicate_review_id"

    shutil.rmtree(work_dir)


def test_validate_training_dataset_rejects_missing_required_columns():
    with pytest.raises(ValueError, match="Missing required training columns"):
        validate_training_dataset(pd.DataFrame([{"review_id": "r1", "review_body": "text"}]))


def test_ingestion_is_idempotent_for_same_version_and_source():
    work_dir = Path("tests_runtime/data_store_idempotent")
    _clean_work_dir(work_dir)
    source_path = Path("data/sample/reviews_sample.csv")

    first = ingest_csv_dataset(source_path, work_dir / "data", dataset_version="idempotent")
    second = ingest_csv_dataset(source_path, work_dir / "data", dataset_version="idempotent")

    assert first == second
    registry = json.loads((work_dir / "data" / "registry" / "datasets_manifest.json").read_text(encoding="utf-8"))
    assert len(registry["datasets"]) == 1

    shutil.rmtree(work_dir)


def test_large_ingestion_writes_deterministic_splits():
    work_dir = Path("tests_runtime/data_store_splits")
    _clean_work_dir(work_dir)

    result = ingest_csv_dataset(
        Path("data/sample/reviews_poc_test.csv"),
        work_dir / "data",
        dataset_version="split_test",
    )

    assert result.train_path
    assert result.train_parquet_path
    assert result.validation_path
    assert result.validation_parquet_path
    assert result.test_path
    assert result.test_parquet_path
    split_ids = []
    for path in (result.train_parquet_path, result.validation_parquet_path, result.test_parquet_path):
        split_ids.extend(pd.read_parquet(path)["review_id"].tolist())
    assert len(split_ids) == result.rows_valid
    assert len(set(split_ids)) == result.rows_valid
    assert result.split_rows == {"train": 24, "validation": 6, "test": 10}

    shutil.rmtree(work_dir)


def test_missing_theme_sentiments_are_queued_for_annotation_not_rejected():
    df = pd.DataFrame(
        [
            {
                "review_id": "r1",
                "review_title": "Fast delivery",
                "review_body": "The parcel arrived quickly.",
                "sentiment_label": "positive",
                "theme_livraison": 1,
                "theme_sav": 0,
                "theme_produit": 0,
                "sentiment_livraison": "",
            }
        ]
    )

    valid, rejected = validate_training_dataset(df)

    assert len(valid) == 1
    assert rejected.empty


def test_strict_quality_gates_fail_after_writing_diagnostics():
    work_dir = Path("tests_runtime/data_store_strict_quality")
    _clean_work_dir(work_dir)
    source_path = Path("data/sample/reviews_sample.csv")

    with pytest.raises(ValueError, match="Dataset quality gates failed"):
        ingest_csv_dataset(
            source_path,
            work_dir / "data",
            dataset_version="strict_quality",
            enforce_quality_gates=True,
        )

    assert (work_dir / "data" / "registry" / "quality_report_strict_quality.json").exists()
    assert (work_dir / "data" / "registry" / "dataset_strict_quality.json").exists()

    with pytest.raises(ValueError, match="Dataset quality gates failed"):
        ingest_csv_dataset(
            source_path,
            work_dir / "data",
            dataset_version="strict_quality",
            enforce_quality_gates=True,
        )

    shutil.rmtree(work_dir)
