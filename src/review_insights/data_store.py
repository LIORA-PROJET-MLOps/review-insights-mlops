from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from .dataset import prepare_dataset


TRAINING_COLUMNS = [
    "review_id",
    "review_title",
    "review_body",
    "sentiment_label",
    "theme_livraison",
    "theme_sav",
    "theme_produit",
]
ALLOWED_SENTIMENTS = {"negative", "neutral", "positive"}


@dataclass(frozen=True)
class DatasetIngestionResult:
    dataset_version: str
    source_file: str
    raw_archive_path: str
    processed_path: str
    validated_path: str
    manifest_path: str
    rows_ingested: int
    rows_valid: int
    rows_rejected: int
    duplicate_review_ids: int
    created_at: str


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
        "registry",
        "sample",
    ):
        (data_root / relative).mkdir(parents=True, exist_ok=True)


def load_training_dataset(dataset_path: Path) -> pd.DataFrame:
    return prepare_dataset(pd.read_csv(dataset_path))


def validate_training_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    prepared = prepare_dataset(df)
    valid_mask = prepared["review_body"].astype(str).str.strip().ne("")
    valid_mask &= prepared["sentiment_label"].astype(str).str.lower().isin(ALLOWED_SENTIMENTS)

    for column in ("theme_livraison", "theme_sav", "theme_produit"):
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
        valid_mask &= prepared[column].isin([0, 1])

    valid = prepared.loc[valid_mask, TRAINING_COLUMNS].copy()
    rejected = prepared.loc[~valid_mask].copy()

    valid["sentiment_label"] = valid["sentiment_label"].astype(str).str.lower()
    for column in ("theme_livraison", "theme_sav", "theme_produit"):
        valid[column] = valid[column].astype(int)

    return valid.drop_duplicates(subset=["review_id"], keep="last"), rejected


def _registry_path(data_root: Path) -> Path:
    return data_root / "registry" / "datasets_manifest.json"


def _write_registry_entry(data_root: Path, result: DatasetIngestionResult) -> None:
    path = _registry_path(data_root)
    if path.exists():
        registry = json.loads(path.read_text(encoding="utf-8"))
    else:
        registry = {"datasets": []}
    registry["datasets"].append(asdict(result))
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def _copy_raw_source(source_path: Path, archive_path: Path) -> None:
    if source_path.resolve() != archive_path.resolve():
        shutil.copy2(source_path, archive_path)


def ingest_csv_dataset(
    source_path: Path,
    data_root: Path,
    dataset_version: str | None = None,
) -> DatasetIngestionResult:
    ensure_data_store(data_root)
    version = dataset_version or build_dataset_version()
    raw_archive_path = data_root / "raw" / "archive" / f"{version}_{source_path.name}"
    processed_path = data_root / "processed" / f"reviews_clean_{version}.csv"
    validated_path = data_root / "validated" / f"training_dataset_{version}.csv"
    manifest_path = data_root / "registry" / f"dataset_{version}.json"

    raw_df = pd.read_csv(source_path)
    valid_df, rejected_df = validate_training_dataset(raw_df)
    duplicate_review_ids = int(raw_df["review_id"].duplicated().sum()) if "review_id" in raw_df.columns else 0

    _copy_raw_source(source_path, raw_archive_path)
    prepare_dataset(raw_df).to_csv(processed_path, index=False)
    valid_df.to_csv(validated_path, index=False)

    result = DatasetIngestionResult(
        dataset_version=version,
        source_file=str(source_path),
        raw_archive_path=str(raw_archive_path),
        processed_path=str(processed_path),
        validated_path=str(validated_path),
        manifest_path=str(manifest_path),
        rows_ingested=int(len(raw_df)),
        rows_valid=int(len(valid_df)),
        rows_rejected=int(len(rejected_df)),
        duplicate_review_ids=duplicate_review_ids,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    manifest_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    _write_registry_entry(data_root, result)
    return result


def latest_validated_dataset(data_root: Path) -> Path | None:
    validated_dir = data_root / "validated"
    if not validated_dir.exists():
        return None
    candidates: Iterable[Path] = validated_dir.glob("training_dataset_*.csv")
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)
