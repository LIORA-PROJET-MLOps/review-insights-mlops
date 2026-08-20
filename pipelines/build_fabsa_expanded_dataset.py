from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.build_fabsa_gold_dataset import (
    DEFAULT_QUOTAS,
    DEFAULT_SOURCE_DIR,
    LABEL_MAPPING_VERSION,
    SOURCE_CITATION,
    SOURCE_DATASET,
    SOURCE_PAGE,
    SOURCE_REVISION,
    SOURCE_URLS,
    THEME_ASPECTS,
    _download,
    _portable_path,
    _profile,
    _sha256,
    sample_stratified,
    transform_source_frame,
)


DATASET_VERSION = "fabsa_real_gold_expanded_v1"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "external" / "fabsa" / "gold_expanded_v1"
EXPORT_COLUMNS = [
    "review_id",
    "review_title",
    "review_body",
    "sentiment_label",
    "theme_livraison",
    "theme_sav",
    "theme_produit",
    "sentiment_livraison",
    "sentiment_sav",
    "sentiment_produit",
    "source_dataset",
    "source_revision",
    "source_record_id",
    "source_split",
    "source_platform",
    "source_industry",
    "annotation_kind",
    "label_mapping_version",
    "primary_theme",
]


def _load_deduplicated_source(
    source_dir: Path,
) -> tuple[
    dict[str, pd.DataFrame],
    dict[str, dict[str, object]],
    dict[str, dict[str, int]],
    dict[str, int],
]:
    transformed: dict[str, pd.DataFrame] = {}
    source_files: dict[str, dict[str, object]] = {}
    exclusions: dict[str, dict[str, int]] = {}
    for split, url in SOURCE_URLS.items():
        source_path = source_dir / f"fabsa_{split}.parquet"
        _download(url, source_path)
        source_files[split] = {
            "url": url,
            "path": _portable_path(source_path),
            "sha256": _sha256(source_path),
            "size_bytes": source_path.stat().st_size,
        }
        frame, split_exclusions = transform_source_frame(pd.read_parquet(source_path), split)
        transformed[split] = frame
        exclusions[split] = dict(sorted(split_exclusions.items()))

    seen_texts: set[str] = set()
    deduped: dict[str, pd.DataFrame] = {}
    cross_split_duplicates: dict[str, int] = {}
    for split in ("train", "validation", "test"):
        frame = transformed[split]
        keep_mask = ~frame["normalized_text_key"].isin(seen_texts)
        cross_split_duplicates[split] = int((~keep_mask).sum())
        frame = frame.loc[keep_mask].drop_duplicates("normalized_text_key", keep="first").copy()
        seen_texts.update(frame["normalized_text_key"].tolist())
        deduped[split] = frame
    return deduped, source_files, exclusions, cross_split_duplicates


def build_expanded_dataset(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    seed: int = 20260820,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    deduped, source_files, exclusions, cross_split_duplicates = (
        _load_deduplicated_source(source_dir)
    )

    selected = {
        "train": deduped["train"].sample(frac=1.0, random_state=seed).reset_index(drop=True),
        "validation": sample_stratified(
            deduped["validation"],
            "validation",
            DEFAULT_QUOTAS["validation"],
            seed,
        ),
        "test": sample_stratified(
            deduped["test"],
            "test",
            DEFAULT_QUOTAS["test"],
            seed,
        ),
    }
    all_selected = pd.concat(selected.values(), ignore_index=True)
    if all_selected["normalized_text_key"].duplicated().any():
        raise AssertionError("Normalized text leakage remains across locked splits.")

    output_files: dict[str, dict[str, object]] = {}
    for split, frame in selected.items():
        export = frame[EXPORT_COLUMNS].copy()
        csv_path = output_dir / f"{split}.csv"
        parquet_path = output_dir / f"{split}.parquet"
        export.to_csv(csv_path, index=False)
        export.to_parquet(parquet_path, index=False)
        output_files[split] = {
            "csv_path": _portable_path(csv_path),
            "csv_sha256": _sha256(csv_path),
            "parquet_path": _portable_path(parquet_path),
            "parquet_sha256": _sha256(parquet_path),
            "profile": _profile(frame),
        }

    full_export = all_selected[EXPORT_COLUMNS].copy()
    full_csv_path = output_dir / f"{DATASET_VERSION}.csv"
    full_parquet_path = output_dir / f"{DATASET_VERSION}.parquet"
    full_export.to_csv(full_csv_path, index=False)
    full_export.to_parquet(full_parquet_path, index=False)

    manifest = {
        "schema_version": "1.0.0",
        "dataset_version": DATASET_VERSION,
        "created_by": _portable_path(Path(__file__)),
        "seed": seed,
        "source": {
            "dataset": SOURCE_DATASET,
            "revision": SOURCE_REVISION,
            "page": SOURCE_PAGE,
            "citation": SOURCE_CITATION,
            "annotation": "Human aspect-category sentiment annotations by FABSA annotators.",
            "license_note": (
                "The public dataset card does not declare an explicit license; keep this "
                "derived snapshot for local POC/research use unless redistribution rights "
                "are confirmed."
            ),
            "files": source_files,
        },
        "mapping": {
            "version": LABEL_MAPPING_VERSION,
            "theme_aspects": {
                theme: sorted(aspects) for theme, aspects in THEME_ASPECTS.items()
            },
            "coarse_conflicts": "excluded",
            "global_sentiment": (
                "single mapped polarity when unanimous; neutral when mapped themes disagree"
            ),
        },
        "selection": {
            "train": "all eligible, de-duplicated rows from the official FABSA train split",
            "validation": "fixed 150-row stratified sample from the official validation split",
            "test": "fixed 150-row blind stratified sample from the official test split",
        },
        "locked_splits": output_files,
        "full_dataset": {
            "csv_path": _portable_path(full_csv_path),
            "csv_sha256": _sha256(full_csv_path),
            "parquet_path": _portable_path(full_parquet_path),
            "parquet_sha256": _sha256(full_parquet_path),
            "profile": _profile(all_selected),
        },
        "quality": {
            "exclusions": exclusions,
            "cross_split_duplicate_texts_removed": cross_split_duplicates,
            "exact_normalized_text_leakage": 0,
            "split_sizes": {split: int(len(frame)) for split, frame in selected.items()},
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the expanded real FABSA training dataset with locked holdouts."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--seed", type=int, default=20260820)
    args = parser.parse_args()
    print(
        json.dumps(
            build_expanded_dataset(args.output_dir, args.source_dir, args.seed),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
