from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable
from urllib.request import urlopen

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.review_insights.data_quality import _contains_probable_pii, _is_probably_non_english


SOURCE_DATASET = "jordiclive/FABSA"
SOURCE_REVISION = "40abb500cd7688529cb831c8c2c2a90d06264379"
SOURCE_PAGE = "https://huggingface.co/datasets/jordiclive/FABSA"
SOURCE_CITATION = (
    "Kontonatsios et al. (2023), FABSA: An aspect-based sentiment analysis "
    "dataset of user reviews, Neurocomputing 562, 126867."
)
SOURCE_URLS = {
    "train": (
        "https://huggingface.co/datasets/jordiclive/FABSA/resolve/"
        "refs%2Fconvert%2Fparquet/default/train/0000.parquet"
    ),
    "validation": (
        "https://huggingface.co/datasets/jordiclive/FABSA/resolve/"
        "refs%2Fconvert%2Fparquet/default/validation/0000.parquet"
    ),
    "test": (
        "https://huggingface.co/datasets/jordiclive/FABSA/resolve/"
        "refs%2Fconvert%2Fparquet/default/test/0000.parquet"
    ),
}

THEME_ASPECTS = {
    "livraison": {"Logistics rides: Speed"},
    "sav": {
        "Account management: Account access",
        "Staff support: Attitude of staff",
        "Staff support: Email",
        "Staff support: Phone",
    },
    "produit": {
        "Online experience: App website",
        "Purchase booking experience: Ease of use",
    },
}
THEMES = tuple(THEME_ASPECTS)
SENTIMENTS = ("negative", "neutral", "positive")
LABEL_MAPPING_VERSION = "fabsa_to_review_insights_v1"

DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "external" / "fabsa" / "gold_900_v1"
DEFAULT_SOURCE_DIR = ROOT_DIR / "data" / "external" / "fabsa" / "source"

# Quotas preserve the official source split and deliberately oversample rare
# neutral and negative labels. Primary theme is assigned in the order below,
# so each multi-label review belongs to exactly one sampling stratum.
DEFAULT_QUOTAS = {
    "train": {
        "livraison": {"negative": 80, "neutral": 20, "positive": 100},
        "sav": {"negative": 70, "neutral": 60, "positive": 70},
        "produit": {"negative": 50, "neutral": 60, "positive": 90},
    },
    "validation": {
        "livraison": {"negative": 20, "neutral": 1, "positive": 29},
        "sav": {"negative": 20, "neutral": 14, "positive": 16},
        "produit": {"negative": 10, "neutral": 15, "positive": 25},
    },
    "test": {
        "livraison": {"negative": 20, "neutral": 7, "positive": 23},
        "sav": {"negative": 17, "neutral": 16, "positive": 17},
        "produit": {"negative": 13, "neutral": 17, "positive": 20},
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_path(path: Path) -> str:
    """Return a repository-relative path when the artifact is inside the project."""
    try:
        return path.resolve().relative_to(ROOT_DIR.resolve()).as_posix()
    except ValueError:
        return str(path)


def _download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return
    with urlopen(url, timeout=60) as response, target.open("wb") as handle:
        while chunk := response.read(1024 * 1024):
            handle.write(chunk)


def _repair_mojibake(value: object) -> str:
    text = str(value or "").strip()
    if not any(marker in text for marker in ("Ã", "â", "Â")):
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _coarse_theme_sentiments(
    labels: Iterable[Iterable[str]],
) -> tuple[dict[str, str | None], bool]:
    sentiments: dict[str, str | None] = {}
    conflict = False
    normalized_labels = [(str(aspect), str(polarity).lower()) for aspect, polarity in labels]
    for theme, mapped_aspects in THEME_ASPECTS.items():
        polarities = {
            polarity
            for aspect, polarity in normalized_labels
            if aspect in mapped_aspects and polarity in SENTIMENTS
        }
        if len(polarities) > 1:
            conflict = True
            sentiments[theme] = None
        else:
            sentiments[theme] = next(iter(polarities)) if polarities else None
    return sentiments, conflict


def _overall_sentiment(theme_sentiments: dict[str, str | None]) -> str:
    present = [theme_sentiments[theme] for theme in THEMES if theme_sentiments[theme]]
    if not present:
        raise ValueError("At least one mapped theme sentiment is required.")
    return str(present[0]) if len(set(present)) == 1 else "neutral"


def transform_source_frame(
    source_df: pd.DataFrame,
    source_split: str,
) -> tuple[pd.DataFrame, Counter]:
    rows: list[dict[str, object]] = []
    exclusions: Counter = Counter()
    for source_row in source_df.itertuples(index=False):
        text = _repair_mojibake(getattr(source_row, "text", ""))
        if not text:
            exclusions["empty_text"] += 1
            continue
        if _contains_probable_pii(text):
            exclusions["probable_pii"] += 1
            continue
        if _is_probably_non_english(text):
            exclusions["probable_non_english"] += 1
            continue

        theme_sentiments, conflict = _coarse_theme_sentiments(
            getattr(source_row, "labels", [])
        )
        if conflict:
            exclusions["coarse_theme_sentiment_conflict"] += 1
            continue
        present_themes = [theme for theme in THEMES if theme_sentiments[theme] is not None]
        if not present_themes:
            exclusions["no_mapped_theme"] += 1
            continue

        rows.append(
            {
                "review_id": f"fabsa_{int(getattr(source_row, 'id'))}",
                "review_title": "",
                "review_body": text,
                "sentiment_label": _overall_sentiment(theme_sentiments),
                **{f"theme_{theme}": int(theme in present_themes) for theme in THEMES},
                **{
                    f"sentiment_{theme}": theme_sentiments[theme] or ""
                    for theme in THEMES
                },
                "source_dataset": SOURCE_DATASET,
                "source_revision": SOURCE_REVISION,
                "source_record_id": str(int(getattr(source_row, "id"))),
                "source_split": source_split,
                "source_platform": str(getattr(source_row, "data_source", "")),
                "source_industry": str(getattr(source_row, "industry", "")),
                "annotation_kind": (
                    "human_aspect_sentiment_with_documented_coarse_mapping"
                ),
                "label_mapping_version": LABEL_MAPPING_VERSION,
                "primary_theme": present_themes[0],
                "normalized_text_key": _normalized_text(text),
            }
        )
    return pd.DataFrame(rows), exclusions


def sample_stratified(
    candidates: pd.DataFrame,
    split: str,
    quotas: dict[str, dict[str, int]],
    seed: int,
) -> pd.DataFrame:
    selected: list[pd.DataFrame] = []
    for theme in THEMES:
        for sentiment in SENTIMENTS:
            requested = int(quotas[theme][sentiment])
            stratum = candidates[
                candidates["primary_theme"].eq(theme)
                & candidates["sentiment_label"].eq(sentiment)
            ]
            if len(stratum) < requested:
                raise ValueError(
                    f"Insufficient rows for {split}/{theme}/{sentiment}: "
                    f"requested={requested}, available={len(stratum)}"
                )
            stratum_seed = seed + sum(ord(char) for char in f"{split}:{theme}:{sentiment}")
            selected.append(
                stratum.sample(n=requested, random_state=stratum_seed, replace=False)
            )
    result = pd.concat(selected, ignore_index=True)
    return result.sample(frac=1.0, random_state=seed).reset_index(drop=True)


def _profile(df: pd.DataFrame) -> dict[str, object]:
    return {
        "rows": int(len(df)),
        "unique_review_ids": int(df["review_id"].nunique()),
        "duplicate_normalized_texts": int(df["normalized_text_key"].duplicated().sum()),
        "sentiment_distribution": {
            str(label): int(count)
            for label, count in df["sentiment_label"].value_counts().sort_index().items()
        },
        "theme_counts": {
            theme: int(df[f"theme_{theme}"].sum())
            for theme in THEMES
        },
        "theme_sentiment_distribution": {
            theme: {
                str(label): int(count)
                for label, count in (
                    df.loc[df[f"theme_{theme}"].eq(1), f"sentiment_{theme}"]
                    .value_counts()
                    .sort_index()
                    .items()
                )
            }
            for theme in THEMES
        },
        "multi_theme_rows": int(
            df[[f"theme_{theme}" for theme in THEMES]].sum(axis=1).gt(1).sum()
        ),
        "source_platform_distribution": {
            str(label): int(count)
            for label, count in df["source_platform"].value_counts().sort_index().items()
        },
        "source_industry_distribution": {
            str(label): int(count)
            for label, count in df["source_industry"].value_counts().sort_index().items()
        },
    }


def build_gold_dataset(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    seed: int = 20260820,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    transformed: dict[str, pd.DataFrame] = {}
    source_files: dict[str, dict[str, object]] = {}
    exclusion_profile: dict[str, dict[str, int]] = {}

    for split, url in SOURCE_URLS.items():
        source_path = source_dir / f"fabsa_{split}.parquet"
        _download(url, source_path)
        source_files[split] = {
            "url": url,
            "path": _portable_path(source_path),
            "sha256": _sha256(source_path),
            "size_bytes": source_path.stat().st_size,
        }
        frame, exclusions = transform_source_frame(pd.read_parquet(source_path), split)
        transformed[split] = frame
        exclusion_profile[split] = dict(sorted(exclusions.items()))

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

    selected = {
        split: sample_stratified(deduped[split], split, DEFAULT_QUOTAS[split], seed)
        for split in ("train", "validation", "test")
    }
    all_selected = pd.concat(selected.values(), ignore_index=True)
    if all_selected["normalized_text_key"].duplicated().any():
        raise AssertionError("Normalized text leakage remains across locked splits.")

    export_columns = [
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
    output_files: dict[str, dict[str, object]] = {}
    for split, frame in selected.items():
        export = frame[export_columns].copy()
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

    full_export = all_selected[export_columns].copy()
    full_csv_path = output_dir / "fabsa_real_gold_900_v1.csv"
    full_parquet_path = output_dir / "fabsa_real_gold_900_v1.parquet"
    full_export.to_csv(full_csv_path, index=False)
    full_export.to_parquet(full_parquet_path, index=False)

    manifest = {
        "schema_version": "1.0.0",
        "dataset_version": "fabsa_real_gold_900_v1",
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
            "primary_theme_order": list(THEMES),
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
            "exclusions": exclusion_profile,
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
        description=(
            "Build a 900-row real, human-annotated and stratified FABSA gold dataset."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--seed", type=int, default=20260820)
    args = parser.parse_args()
    manifest = build_gold_dataset(args.output_dir, args.source_dir, args.seed)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
