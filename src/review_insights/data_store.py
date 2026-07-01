from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from .data_quality import (
    DEFAULT_QUALITY_POLICY_PATH,
    THEMES,
    build_annotation_queue,
    build_quality_report,
    load_quality_policy,
)
from .dataset import prepare_dataset


DATASET_SCHEMA_VERSION = "1.0.0"
DATASET_MANIFEST_SCHEMA_VERSION = "2.1.0"
DEFAULT_DATASET_CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "contracts" / "reviews_v1.json"
)
REQUIRED_TRAINING_COLUMNS = [
    "review_id",
    "review_body",
    "sentiment_label",
    "theme_livraison",
    "theme_sav",
    "theme_produit",
]
TRAINING_COLUMNS = [
    "review_id",
    "review_title",
    "review_body",
    "sentiment_label",
    "theme_livraison",
    "theme_sav",
    "theme_produit",
]
THEME_SENTIMENT_COLUMNS = [
    "sentiment_livraison",
    "sentiment_sav",
    "sentiment_produit",
]
ALLOWED_SENTIMENTS = {"negative", "neutral", "positive"}
DATASET_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class DatasetIngestionResult:
    dataset_version: str
    schema_version: str
    manifest_schema_version: str
    source_file: str
    source_sha256: str
    raw_archive_path: str
    processed_path: str
    processed_parquet_path: str
    validated_path: str
    validated_parquet_path: str
    quarantine_path: str
    quarantine_parquet_path: str
    annotation_queue_path: str
    annotation_queue_parquet_path: str
    quality_report_path: str
    train_path: str | None
    train_parquet_path: str | None
    validation_path: str | None
    validation_parquet_path: str | None
    test_path: str | None
    test_parquet_path: str | None
    manifest_path: str
    rows_ingested: int
    rows_valid: int
    rows_rejected: int
    duplicate_review_ids: int
    annotation_rows: int
    processed_sha256: str
    processed_parquet_sha256: str
    validated_sha256: str
    validated_parquet_sha256: str
    artifact_sha256: dict[str, str]
    sentiment_distribution: dict[str, int]
    theme_counts: dict[str, int]
    quality_policy_path: str
    quality_policy_version: str
    quality_status: str
    quality_failed_checks: list[str]
    created_at: str
    dataset_contract_path: str = ""
    dataset_contract_sha256: str = ""
    quality_policy_sha256: str = ""
    git_commit: str = "unknown"
    pipeline_name: str = "ingest_csv_dataset"
    split_rows: dict[str, int] = field(default_factory=dict)


def default_data_root(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[2]
    return root / "data"


def build_dataset_version(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return current.strftime("%Y%m%dT%H%M%SZ")


def ensure_data_store(data_root: Path) -> None:
    for relative in (
        "raw/incoming",
        "raw/archive",
        "processed",
        "validated",
        "quarantine",
        "splits",
        "registry",
        "sample",
    ):
        (data_root / relative).mkdir(parents=True, exist_ok=True)


def load_training_dataset(dataset_path: Path) -> pd.DataFrame:
    suffix = dataset_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(dataset_path)
    elif suffix in {".parquet", ".pq"}:
        df = pd.read_parquet(dataset_path, engine="pyarrow")
    else:
        raise ValueError(f"Unsupported training dataset format: {dataset_path.suffix}")
    return prepare_dataset(df)


def _add_rejection_reason(reasons: pd.Series, mask: pd.Series, reason: str) -> None:
    for index in reasons.index[mask]:
        reasons.at[index].append(reason)


def validate_training_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing_columns = sorted(set(REQUIRED_TRAINING_COLUMNS) - set(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required training columns: {', '.join(missing_columns)}")

    prepared = prepare_dataset(df)
    reasons = pd.Series([[] for _ in range(len(prepared))], index=prepared.index, dtype=object)

    review_ids = prepared["review_id"].astype(str).str.strip()
    review_bodies = prepared["review_body"].astype(str).str.strip()
    sentiments = prepared["sentiment_label"].astype(str).str.lower().str.strip()

    _add_rejection_reason(reasons, review_ids.eq(""), "empty_review_id")
    _add_rejection_reason(reasons, review_bodies.eq(""), "empty_review_body")
    _add_rejection_reason(reasons, ~sentiments.isin(ALLOWED_SENTIMENTS), "invalid_sentiment_label")

    prepared["review_id"] = review_ids
    prepared["sentiment_label"] = sentiments

    for theme in ("livraison", "sav", "produit"):
        theme_column = f"theme_{theme}"
        numeric = pd.to_numeric(prepared[theme_column], errors="coerce")
        _add_rejection_reason(reasons, ~numeric.isin([0, 1]), f"invalid_{theme_column}")
        prepared[theme_column] = numeric

        sentiment_column = f"sentiment_{theme}"
        if sentiment_column in prepared.columns:
            theme_sentiments = prepared[sentiment_column].astype(str).str.lower().str.strip()
            invalid_sentiment = theme_sentiments.ne("") & ~theme_sentiments.isin(ALLOWED_SENTIMENTS)
            _add_rejection_reason(reasons, invalid_sentiment, f"invalid_{sentiment_column}")
            prepared[sentiment_column] = theme_sentiments

    valid_mask = reasons.apply(len).eq(0)
    duplicate_mask = valid_mask & prepared["review_id"].duplicated(keep="last")
    _add_rejection_reason(reasons, duplicate_mask, "duplicate_review_id")
    valid_mask &= ~duplicate_mask

    output_columns = TRAINING_COLUMNS + [
        column for column in THEME_SENTIMENT_COLUMNS if column in prepared.columns
    ]
    valid = prepared.loc[valid_mask, output_columns].copy()
    rejected = prepared.loc[~valid_mask].copy()
    rejected["rejection_reasons"] = reasons.loc[~valid_mask].apply(lambda values: ",".join(values))

    for column in ("theme_livraison", "theme_sav", "theme_produit"):
        valid[column] = valid[column].astype(int)

    return valid.reset_index(drop=True), rejected.reset_index(drop=True)


def _registry_path(data_root: Path) -> Path:
    return data_root / "registry" / "datasets_manifest.json"


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def _write_dataframe_atomic(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    if path.suffix.lower() == ".csv":
        df.to_csv(temporary_path, index=False)
    elif path.suffix.lower() in {".parquet", ".pq"}:
        df.to_parquet(temporary_path, index=False, engine="pyarrow", compression="zstd")
    else:
        raise ValueError(f"Unsupported dataframe artifact format: {path.suffix}")
    temporary_path.replace(path)


def _write_registry_entry(data_root: Path, result: DatasetIngestionResult) -> None:
    path = _registry_path(data_root)
    if path.exists():
        registry = json.loads(path.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": DATASET_SCHEMA_VERSION, "datasets": []}
    datasets = [
        entry
        for entry in registry.get("datasets", [])
        if entry.get("dataset_version") != result.dataset_version
    ]
    datasets.append(asdict(result))
    registry["schema_version"] = DATASET_SCHEMA_VERSION
    registry["datasets"] = datasets
    _write_json_atomic(path, registry)


def _copy_raw_source(source_path: Path, archive_path: Path) -> None:
    if source_path.resolve() != archive_path.resolve():
        shutil.copy2(source_path, archive_path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _current_git_commit(project_root: Path | None = None) -> str:
    for variable in ("GIT_COMMIT_SHA", "GITHUB_SHA", "SOURCE_VERSION"):
        value = os.getenv(variable, "").strip()
        if value:
            return value
    root = project_root or Path(__file__).resolve().parents[2]
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _artifact_checksums(data_root: Path, paths: Iterable[Path | None]) -> dict[str, str]:
    return {
        path.relative_to(data_root).as_posix(): _sha256(path)
        for path in paths
        if path is not None and path.exists()
    }


def _raise_for_failed_quality_gates(result: DatasetIngestionResult) -> None:
    if result.quality_status == "ready":
        return
    failed = ", ".join(result.quality_failed_checks)
    raise ValueError(f"Dataset quality gates failed for {result.dataset_version}: {failed}")


def _stable_row_score(review_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{review_id}".encode("utf-8")).hexdigest()


def split_training_dataset(
    df: pd.DataFrame,
    *,
    seed: int = 42,
    validation_fraction: float = 0.15,
    test_fraction: float = 0.25,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if len(df) < 12:
        return df.copy(), df.iloc[0:0].copy(), df.iloc[0:0].copy()

    assignments: dict[int, str] = {}
    for _, group in df.groupby("sentiment_label", sort=True):
        ordered_indexes = sorted(
            group.index,
            key=lambda index: _stable_row_score(str(df.at[index, "review_id"]), seed),
        )
        group_size = len(ordered_indexes)
        validation_size = max(1, round(group_size * validation_fraction))
        test_size = max(1, round(group_size * test_fraction))
        while group_size - validation_size - test_size < 1:
            if validation_size >= test_size and validation_size > 1:
                validation_size -= 1
            elif test_size > 1:
                test_size -= 1
            else:
                return df.copy(), df.iloc[0:0].copy(), df.iloc[0:0].copy()

        for index in ordered_indexes[:test_size]:
            assignments[index] = "test"
        for index in ordered_indexes[test_size : test_size + validation_size]:
            assignments[index] = "validation"
        for index in ordered_indexes[test_size + validation_size :]:
            assignments[index] = "train"

    split = pd.Series(assignments)
    train = df.loc[split[split == "train"].index].copy()
    validation = df.loc[split[split == "validation"].index].copy()
    test = df.loc[split[split == "test"].index].copy()
    return (
        train.sort_values("review_id").reset_index(drop=True),
        validation.sort_values("review_id").reset_index(drop=True),
        test.sort_values("review_id").reset_index(drop=True),
    )


def _existing_ingestion_result(manifest_path: Path, source_sha256: str) -> DatasetIngestionResult | None:
    if not manifest_path.exists():
        return None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("source_sha256") != source_sha256:
        raise ValueError(
            f"Dataset version {payload.get('dataset_version', 'unknown')} already exists for a different source file."
        )
    try:
        return DatasetIngestionResult(**payload)
    except TypeError as exc:
        raise ValueError("Existing dataset manifest is incompatible with the current schema.") from exc


def ingest_csv_dataset(
    source_path: Path,
    data_root: Path,
    dataset_version: str | None = None,
    *,
    quality_policy_path: Path | None = None,
    enforce_quality_gates: bool = False,
) -> DatasetIngestionResult:
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"Source CSV file not found: {source_path}")

    ensure_data_store(data_root)
    version = dataset_version or build_dataset_version()
    if not DATASET_VERSION_PATTERN.fullmatch(version):
        raise ValueError("Dataset version may only contain letters, numbers, dots, dashes, and underscores.")

    raw_archive_path = data_root / "raw" / "archive" / f"{version}_{source_path.name}"
    processed_path = data_root / "processed" / f"reviews_clean_{version}.csv"
    processed_parquet_path = data_root / "processed" / f"reviews_clean_{version}.parquet"
    validated_path = data_root / "validated" / f"training_dataset_{version}.csv"
    validated_parquet_path = data_root / "validated" / f"training_dataset_{version}.parquet"
    quarantine_path = data_root / "quarantine" / f"rejected_reviews_{version}.csv"
    quarantine_parquet_path = data_root / "quarantine" / f"rejected_reviews_{version}.parquet"
    annotation_queue_path = data_root / "quarantine" / f"annotation_queue_{version}.csv"
    annotation_queue_parquet_path = data_root / "quarantine" / f"annotation_queue_{version}.parquet"
    split_dir = data_root / "splits" / version
    manifest_path = data_root / "registry" / f"dataset_{version}.json"
    quality_report_path = data_root / "registry" / f"quality_report_{version}.json"
    source_sha256 = _sha256(source_path)

    existing = _existing_ingestion_result(manifest_path, source_sha256)
    if existing is not None:
        if enforce_quality_gates:
            _raise_for_failed_quality_gates(existing)
        return existing

    raw_df = pd.read_csv(source_path)
    valid_df, rejected_df = validate_training_dataset(raw_df)
    annotation_queue = build_annotation_queue(valid_df)
    resolved_quality_policy_path = quality_policy_path or DEFAULT_QUALITY_POLICY_PATH
    quality_policy = load_quality_policy(resolved_quality_policy_path)
    if quality_policy.dataset_schema_version != DATASET_SCHEMA_VERSION:
        raise ValueError(
            "Quality policy dataset schema version does not match the training dataset contract."
        )
    quality_report = build_quality_report(raw_df, valid_df, rejected_df, quality_policy)
    duplicate_review_ids = int(raw_df["review_id"].astype(str).duplicated().sum())
    train_df, validation_df, test_df = split_training_dataset(valid_df)

    _copy_raw_source(source_path, raw_archive_path)
    processed_df = prepare_dataset(raw_df)
    _write_dataframe_atomic(processed_df, processed_path)
    _write_dataframe_atomic(processed_df, processed_parquet_path)
    _write_dataframe_atomic(valid_df, validated_path)
    _write_dataframe_atomic(valid_df, validated_parquet_path)
    _write_dataframe_atomic(rejected_df, quarantine_path)
    _write_dataframe_atomic(rejected_df, quarantine_parquet_path)
    _write_dataframe_atomic(annotation_queue, annotation_queue_path)
    _write_dataframe_atomic(annotation_queue, annotation_queue_parquet_path)
    _write_json_atomic(quality_report_path, quality_report)

    train_path: Path | None = None
    train_parquet_path: Path | None = None
    validation_path: Path | None = None
    validation_parquet_path: Path | None = None
    test_path: Path | None = None
    test_parquet_path: Path | None = None
    if len(validation_df) and len(test_df):
        split_dir.mkdir(parents=True, exist_ok=True)
        train_path = split_dir / "train.csv"
        train_parquet_path = split_dir / "train.parquet"
        validation_path = split_dir / "validation.csv"
        validation_parquet_path = split_dir / "validation.parquet"
        test_path = split_dir / "test.csv"
        test_parquet_path = split_dir / "test.parquet"
        _write_dataframe_atomic(train_df, train_path)
        _write_dataframe_atomic(train_df, train_parquet_path)
        _write_dataframe_atomic(validation_df, validation_path)
        _write_dataframe_atomic(validation_df, validation_parquet_path)
        _write_dataframe_atomic(test_df, test_path)
        _write_dataframe_atomic(test_df, test_parquet_path)

    artifact_sha256 = _artifact_checksums(
        data_root,
        (
            raw_archive_path,
            processed_path,
            processed_parquet_path,
            validated_path,
            validated_parquet_path,
            quarantine_path,
            quarantine_parquet_path,
            annotation_queue_path,
            annotation_queue_parquet_path,
            quality_report_path,
            train_path,
            train_parquet_path,
            validation_path,
            validation_parquet_path,
            test_path,
            test_parquet_path,
        ),
    )

    result = DatasetIngestionResult(
        dataset_version=version,
        schema_version=DATASET_SCHEMA_VERSION,
        manifest_schema_version=DATASET_MANIFEST_SCHEMA_VERSION,
        source_file=str(source_path),
        source_sha256=source_sha256,
        raw_archive_path=str(raw_archive_path),
        processed_path=str(processed_path),
        processed_parquet_path=str(processed_parquet_path),
        validated_path=str(validated_path),
        validated_parquet_path=str(validated_parquet_path),
        quarantine_path=str(quarantine_path),
        quarantine_parquet_path=str(quarantine_parquet_path),
        annotation_queue_path=str(annotation_queue_path),
        annotation_queue_parquet_path=str(annotation_queue_parquet_path),
        quality_report_path=str(quality_report_path),
        train_path=str(train_path) if train_path else None,
        train_parquet_path=str(train_parquet_path) if train_parquet_path else None,
        validation_path=str(validation_path) if validation_path else None,
        validation_parquet_path=str(validation_parquet_path) if validation_parquet_path else None,
        test_path=str(test_path) if test_path else None,
        test_parquet_path=str(test_parquet_path) if test_parquet_path else None,
        manifest_path=str(manifest_path),
        rows_ingested=int(len(raw_df)),
        rows_valid=int(len(valid_df)),
        rows_rejected=int(len(rejected_df)),
        duplicate_review_ids=duplicate_review_ids,
        annotation_rows=int(len(annotation_queue)),
        processed_sha256=_sha256(processed_path),
        processed_parquet_sha256=_sha256(processed_parquet_path),
        validated_sha256=_sha256(validated_path),
        validated_parquet_sha256=_sha256(validated_parquet_path),
        artifact_sha256=artifact_sha256,
        sentiment_distribution={
            str(label): int(count)
            for label, count in valid_df["sentiment_label"].value_counts().sort_index().items()
        },
        theme_counts={
            theme: int(valid_df[f"theme_{theme}"].sum())
            for theme in THEMES
        },
        quality_policy_path=str(resolved_quality_policy_path),
        quality_policy_version=quality_policy.policy_version,
        quality_status=str(quality_report["status"]),
        quality_failed_checks=list(quality_report["failed_checks"]),
        created_at=datetime.now(timezone.utc).isoformat(),
        dataset_contract_path=str(DEFAULT_DATASET_CONTRACT_PATH),
        dataset_contract_sha256=_sha256(DEFAULT_DATASET_CONTRACT_PATH),
        quality_policy_sha256=_sha256(resolved_quality_policy_path),
        git_commit=_current_git_commit(),
        split_rows={
            "train": int(len(train_df)),
            "validation": int(len(validation_df)),
            "test": int(len(test_df)),
        },
    )
    _write_json_atomic(manifest_path, asdict(result))
    _write_registry_entry(data_root, result)
    if enforce_quality_gates:
        _raise_for_failed_quality_gates(result)
    return result


def latest_validated_dataset(data_root: Path) -> Path | None:
    validated_dir = data_root / "validated"
    if not validated_dir.exists():
        return None
    parquet_candidates: Iterable[Path] = validated_dir.glob("training_dataset_*.parquet")
    latest_parquet = max(parquet_candidates, key=lambda path: path.stat().st_mtime, default=None)
    if latest_parquet is not None:
        return latest_parquet
    csv_candidates: Iterable[Path] = validated_dir.glob("training_dataset_*.csv")
    return max(csv_candidates, key=lambda path: path.stat().st_mtime, default=None)


def latest_ready_validated_dataset(data_root: Path) -> Path | None:
    registry_dir = data_root / "registry"
    manifests = sorted(
        registry_dir.glob("dataset_*.json") if registry_dir.exists() else [],
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for manifest_path in manifests:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("quality_status") != "ready":
            continue
        for field_name in ("validated_parquet_path", "validated_path"):
            candidate = Path(str(manifest.get(field_name, "")))
            if candidate.is_file():
                return candidate
    return None
