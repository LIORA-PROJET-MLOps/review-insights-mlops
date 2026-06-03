from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


THEMES = ("livraison", "sav", "produit")
ALLOWED_SENTIMENTS = {"negative", "neutral", "positive"}
DEFAULT_QUALITY_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "contracts" / "reviews_quality_policy_v1.json"
)

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
WORD_PATTERN = re.compile(r"[A-Za-zÀ-ÿ']+")

ENGLISH_MARKERS = {
    "a",
    "and",
    "arrived",
    "but",
    "delivery",
    "for",
    "good",
    "great",
    "i",
    "in",
    "is",
    "it",
    "my",
    "not",
    "of",
    "on",
    "product",
    "quality",
    "service",
    "shipping",
    "support",
    "the",
    "this",
    "to",
    "very",
    "was",
    "with",
}
NON_ENGLISH_MARKERS = {
    "avec",
    "ce",
    "cette",
    "des",
    "est",
    "et",
    "je",
    "la",
    "le",
    "les",
    "livraison",
    "ma",
    "mais",
    "mon",
    "pas",
    "pour",
    "produit",
    "très",
    "un",
    "une",
}


@dataclass(frozen=True)
class DataQualityPolicy:
    policy_version: str
    dataset_schema_version: str
    language_scope: str
    min_valid_rows: int
    min_sentiment_class_rows: int
    min_theme_positive_rows: int
    max_rejected_fraction: float
    max_probable_pii_rows: int
    max_probable_non_english_fraction: float
    min_explicit_theme_sentiment_coverage: float


def load_quality_policy(path: Path | None = None) -> DataQualityPolicy:
    policy_path = path or DEFAULT_QUALITY_POLICY_PATH
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    gates = payload["gates"]
    return DataQualityPolicy(
        policy_version=str(payload["policy_version"]),
        dataset_schema_version=str(payload["dataset_schema_version"]),
        language_scope=str(payload["language_scope"]),
        min_valid_rows=int(gates["min_valid_rows"]),
        min_sentiment_class_rows=int(gates["min_sentiment_class_rows"]),
        min_theme_positive_rows=int(gates["min_theme_positive_rows"]),
        max_rejected_fraction=float(gates["max_rejected_fraction"]),
        max_probable_pii_rows=int(gates["max_probable_pii_rows"]),
        max_probable_non_english_fraction=float(gates["max_probable_non_english_fraction"]),
        min_explicit_theme_sentiment_coverage=float(gates["min_explicit_theme_sentiment_coverage"]),
    )


def _review_text(df: pd.DataFrame) -> pd.Series:
    title = df.get("review_title", pd.Series("", index=df.index)).astype(str)
    body = df.get("review_body", pd.Series("", index=df.index)).astype(str)
    return title.str.cat(body, sep=" ").str.strip()


def _contains_probable_pii(value: str) -> bool:
    return bool(
        EMAIL_PATTERN.search(value)
        or PHONE_PATTERN.search(value)
        or IPV4_PATTERN.search(value)
    )


def _is_probably_non_english(value: str) -> bool:
    words = [word.lower() for word in WORD_PATTERN.findall(value)]
    if len(words) < 4:
        return False
    english_score = sum(word in ENGLISH_MARKERS for word in words)
    non_english_score = sum(word in NON_ENGLISH_MARKERS for word in words)
    non_ascii_letters = sum(any(ord(char) > 127 for char in word) for word in words)
    return (non_english_score >= 2 and non_english_score > english_score) or (
        non_ascii_letters / len(words) >= 0.2 and english_score == 0
    )


def build_annotation_queue(valid_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, review in valid_df.iterrows():
        for theme in THEMES:
            theme_column = f"theme_{theme}"
            sentiment_column = f"sentiment_{theme}"
            if int(review.get(theme_column, 0)) != 1:
                continue
            current_label = str(review.get(sentiment_column, "")).strip().lower()
            if current_label in ALLOWED_SENTIMENTS:
                continue
            review_id = str(review.get("review_id", "")).strip()
            rows.append(
                {
                    "annotation_id": f"{review_id}:{theme}",
                    "review_id": review_id,
                    "review_title": str(review.get("review_title", "")),
                    "review_body": str(review.get("review_body", "")),
                    "theme": theme,
                    "label_column": sentiment_column,
                    "global_sentiment_context": str(review.get("sentiment_label", "")),
                    "sentiment_label": "",
                    "annotation_status": "pending",
                }
            )
    columns = [
        "annotation_id",
        "review_id",
        "review_title",
        "review_body",
        "theme",
        "label_column",
        "global_sentiment_context",
        "sentiment_label",
        "annotation_status",
    ]
    return pd.DataFrame(rows, columns=columns)


def _check(actual: int | float, threshold: int | float, operator: str) -> dict[str, Any]:
    if operator == ">=":
        passed = actual >= threshold
    elif operator == "<=":
        passed = actual <= threshold
    else:
        raise ValueError(f"Unsupported quality check operator: {operator}")
    return {
        "passed": bool(passed),
        "actual": actual,
        "operator": operator,
        "threshold": threshold,
    }


def build_quality_report(
    raw_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    rejected_df: pd.DataFrame,
    policy: DataQualityPolicy,
) -> dict[str, Any]:
    texts = _review_text(valid_df)
    probable_pii_mask = texts.apply(_contains_probable_pii)
    probable_non_english_mask = texts.apply(_is_probably_non_english)
    rows_ingested = int(len(raw_df))
    rows_valid = int(len(valid_df))
    rows_rejected = int(len(rejected_df))
    rejected_fraction = rows_rejected / rows_ingested if rows_ingested else 0.0
    probable_non_english_fraction = (
        int(probable_non_english_mask.sum()) / rows_valid if rows_valid else 0.0
    )

    sentiment_distribution = {
        str(label): int(count)
        for label, count in valid_df["sentiment_label"].value_counts().sort_index().items()
    }
    theme_counts = {
        theme: int(valid_df[f"theme_{theme}"].sum())
        for theme in THEMES
    }
    explicit_theme_sentiment_coverage: dict[str, float] = {}
    explicit_theme_sentiment_rows: dict[str, int] = {}
    for theme in THEMES:
        theme_column = f"theme_{theme}"
        sentiment_column = f"sentiment_{theme}"
        present_mask = valid_df[theme_column].astype(int).eq(1)
        present_rows = int(present_mask.sum())
        if sentiment_column in valid_df.columns:
            explicit_mask = (
                valid_df[sentiment_column].astype(str).str.lower().isin(ALLOWED_SENTIMENTS)
            )
            labeled_rows = int((present_mask & explicit_mask).sum())
        else:
            labeled_rows = 0
        explicit_theme_sentiment_rows[theme] = labeled_rows
        explicit_theme_sentiment_coverage[theme] = (
            labeled_rows / present_rows if present_rows else 1.0
        )

    checks: dict[str, dict[str, Any]] = {
        "min_valid_rows": _check(rows_valid, policy.min_valid_rows, ">="),
        "max_rejected_fraction": _check(
            round(rejected_fraction, 6),
            policy.max_rejected_fraction,
            "<=",
        ),
        "max_probable_pii_rows": _check(
            int(probable_pii_mask.sum()),
            policy.max_probable_pii_rows,
            "<=",
        ),
        "max_probable_non_english_fraction": _check(
            round(probable_non_english_fraction, 6),
            policy.max_probable_non_english_fraction,
            "<=",
        ),
    }
    for sentiment in sorted(ALLOWED_SENTIMENTS):
        checks[f"min_sentiment_rows_{sentiment}"] = _check(
            sentiment_distribution.get(sentiment, 0),
            policy.min_sentiment_class_rows,
            ">=",
        )
    for theme in THEMES:
        checks[f"min_theme_rows_{theme}"] = _check(
            theme_counts[theme],
            policy.min_theme_positive_rows,
            ">=",
        )
        checks[f"min_explicit_theme_sentiment_coverage_{theme}"] = _check(
            round(explicit_theme_sentiment_coverage[theme], 6),
            policy.min_explicit_theme_sentiment_coverage,
            ">=",
        )

    failed_checks = sorted(name for name, check in checks.items() if not check["passed"])
    return {
        "policy": asdict(policy),
        "status": "ready" if not failed_checks else "not_ready",
        "failed_checks": failed_checks,
        "profile": {
            "rows_ingested": rows_ingested,
            "rows_valid": rows_valid,
            "rows_rejected": rows_rejected,
            "rejected_fraction": round(rejected_fraction, 6),
            "sentiment_distribution": sentiment_distribution,
            "theme_counts": theme_counts,
            "explicit_theme_sentiment_rows": explicit_theme_sentiment_rows,
            "explicit_theme_sentiment_coverage": {
                theme: round(value, 6)
                for theme, value in explicit_theme_sentiment_coverage.items()
            },
            "probable_pii_rows": int(probable_pii_mask.sum()),
            "probable_pii_review_ids": valid_df.loc[probable_pii_mask, "review_id"].astype(str).tolist(),
            "probable_non_english_rows": int(probable_non_english_mask.sum()),
            "probable_non_english_review_ids": (
                valid_df.loc[probable_non_english_mask, "review_id"].astype(str).tolist()
            ),
        },
        "checks": checks,
        "notes": [
            "PII and language checks are deterministic screening heuristics, not authoritative classifiers.",
            "A not_ready dataset remains available for diagnosis unless strict quality gates are enforced.",
        ],
    }
