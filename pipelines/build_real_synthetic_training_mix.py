from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.build_fabsa_gold_dataset import _portable_path


DEFAULT_REAL_TRAIN = ROOT_DIR / "data" / "external" / "fabsa" / "gold_expanded_v1" / "train.parquet"
DEFAULT_SYNTHETIC_TRAINS = (
    ROOT_DIR / "data" / "splits" / "scale_balanced_core_15000_v1" / "train.parquet",
    ROOT_DIR / "data" / "splits" / "scale_noisy_long_tail_15000_v1" / "train.parquet",
    ROOT_DIR / "data" / "splits" / "scale_multitheme_context_15000_v1" / "train.parquet",
)
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "external" / "fabsa" / "training_mix_v1"
TRAINING_COLUMNS = [
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
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sample_balanced_sentiment(df: pd.DataFrame, rows: int, seed: int) -> pd.DataFrame:
    labels = ("negative", "neutral", "positive")
    base, remainder = divmod(rows, len(labels))
    pieces = []
    for index, label in enumerate(labels):
        requested = base + int(index < remainder)
        group = df[df["sentiment_label"].eq(label)]
        if len(group) < requested:
            raise ValueError(
                f"Insufficient {label} rows: requested={requested}, available={len(group)}"
            )
        pieces.append(group.sample(n=requested, random_state=seed + index, replace=False))
    return pd.concat(pieces, ignore_index=True)


def build_training_mix(
    real_train_path: Path = DEFAULT_REAL_TRAIN,
    synthetic_train_paths: tuple[Path, ...] = DEFAULT_SYNTHETIC_TRAINS,
    synthetic_rows_per_profile: int = 1_500,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    seed: int = 20260820,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    real = pd.read_parquet(real_train_path)[TRAINING_COLUMNS].copy()
    real["training_source"] = "fabsa_real_human_annotated"
    pieces = [real]
    sources: list[dict[str, object]] = [
        {"kind": "real", "path": _portable_path(real_train_path), "rows": int(len(real))}
    ]
    for index, path in enumerate(synthetic_train_paths):
        source = pd.read_parquet(path)[TRAINING_COLUMNS].copy()
        sample = _sample_balanced_sentiment(
            source,
            synthetic_rows_per_profile,
            seed + (index + 1) * 100,
        )
        sample["training_source"] = f"synthetic_{path.parent.name}"
        pieces.append(sample)
        sources.append(
            {
                "kind": "synthetic",
                "path": _portable_path(path),
                "source_rows": int(len(source)),
                "sampled_rows": int(len(sample)),
            }
        )
    mixed = pd.concat(pieces, ignore_index=True)
    normalized = (
        mixed["review_title"].fillna("").astype(str)
        .str.cat(mixed["review_body"].fillna("").astype(str), sep=" ")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.casefold()
    )
    if normalized.duplicated().any():
        mixed = mixed.loc[~normalized.duplicated(keep="first")].copy()
    mixed = mixed.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    csv_path = output_dir / "fabsa_real_plus_synthetic_train_v1.csv"
    parquet_path = output_dir / "fabsa_real_plus_synthetic_train_v1.parquet"
    mixed.to_csv(csv_path, index=False)
    mixed.to_parquet(parquet_path, index=False)
    manifest = {
        "schema_version": "1.0.0",
        "dataset_version": "fabsa_real_plus_synthetic_train_v1",
        "seed": seed,
        "sources": sources,
        "rows": int(len(mixed)),
        "real_rows": int(mixed["training_source"].eq("fabsa_real_human_annotated").sum()),
        "synthetic_rows": int(mixed["training_source"].ne("fabsa_real_human_annotated").sum()),
        "duplicate_normalized_texts": 0,
        "sentiment_distribution": {
            str(label): int(count)
            for label, count in mixed["sentiment_label"].value_counts().sort_index().items()
        },
        "theme_counts": {
            theme: int(mixed[f"theme_{theme}"].sum())
            for theme in ("livraison", "sav", "produit")
        },
        "csv_path": _portable_path(csv_path),
        "csv_sha256": _sha256(csv_path),
        "parquet_path": _portable_path(parquet_path),
        "parquet_sha256": _sha256(parquet_path),
        "holdouts": {
            "validation": _portable_path(
                ROOT_DIR / "data" / "external" / "fabsa" / "gold_expanded_v1" / "validation.parquet"
            ),
            "blind_test": _portable_path(
                ROOT_DIR / "data" / "external" / "fabsa" / "gold_expanded_v1" / "test.parquet"
            ),
            "holdout_rows_used_in_training": 0,
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a real-majority training mix with balanced synthetic domain anchors."
    )
    parser.add_argument("--real-train-path", type=Path, default=DEFAULT_REAL_TRAIN)
    parser.add_argument("--synthetic-rows-per-profile", type=int, default=1_500)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=20260820)
    args = parser.parse_args()
    print(
        json.dumps(
            build_training_mix(
                real_train_path=args.real_train_path,
                synthetic_rows_per_profile=args.synthetic_rows_per_profile,
                output_dir=args.output_dir,
                seed=args.seed,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
