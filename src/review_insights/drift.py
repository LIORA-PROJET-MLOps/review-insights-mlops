from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .data_store import (
    ALLOWED_SENTIMENTS,
    REQUIRED_TRAINING_COLUMNS,
    THEME_SENTIMENT_COLUMNS,
    latest_ready_validated_dataset,
    load_training_dataset,
)
from .feedback_store import read_feedback
from .prediction_store import THEMES, read_prediction_events


DEFAULT_DRIFT_POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "drift_policy_v1.json"


@dataclass(frozen=True)
class DriftPolicy:
    policy_version: str
    prediction_window_size: int
    minimum_prediction_events: int
    minimum_feedback_records: int
    minimum_retraining_rows: int
    minimum_changed_labeled_rows: int
    max_sentiment_js_divergence: float
    max_theme_js_divergence: float
    max_human_review_rate: float
    max_sentiment_conflict_rate: float
    min_feedback_combined_accuracy: float
    automatic_retraining_enabled: bool
    require_new_labeled_csv: bool


def load_drift_policy(path: Path = DEFAULT_DRIFT_POLICY_PATH) -> DriftPolicy:
    payload = json.loads(path.read_text(encoding="utf-8"))
    thresholds = payload["thresholds"]
    automation = payload["automatic_retraining"]
    policy = DriftPolicy(
        policy_version=str(payload["policy_version"]),
        prediction_window_size=int(payload["prediction_window_size"]),
        minimum_prediction_events=int(payload["minimum_prediction_events"]),
        minimum_feedback_records=int(payload["minimum_feedback_records"]),
        minimum_retraining_rows=int(payload["minimum_retraining_rows"]),
        minimum_changed_labeled_rows=int(payload.get("minimum_changed_labeled_rows", 1)),
        max_sentiment_js_divergence=float(thresholds["max_sentiment_js_divergence"]),
        max_theme_js_divergence=float(thresholds["max_theme_js_divergence"]),
        max_human_review_rate=float(thresholds["max_human_review_rate"]),
        max_sentiment_conflict_rate=float(thresholds["max_sentiment_conflict_rate"]),
        min_feedback_combined_accuracy=float(thresholds["min_feedback_combined_accuracy"]),
        automatic_retraining_enabled=bool(automation["enabled"]),
        require_new_labeled_csv=bool(automation["require_new_labeled_csv"]),
    )
    if min(
        policy.prediction_window_size,
        policy.minimum_prediction_events,
        policy.minimum_feedback_records,
        policy.minimum_retraining_rows,
        policy.minimum_changed_labeled_rows,
    ) <= 0:
        raise ValueError("Drift policy counts must be positive.")
    for value in (
        policy.max_sentiment_js_divergence,
        policy.max_theme_js_divergence,
        policy.max_human_review_rate,
        policy.max_sentiment_conflict_rate,
        policy.min_feedback_combined_accuracy,
    ):
        if not 0 <= value <= 1:
            raise ValueError("Drift policy thresholds must be between 0 and 1.")
    return policy


def _probabilities(values: Iterable[str], categories: Iterable[str]) -> dict[str, float]:
    category_list = list(dict.fromkeys(categories))
    counts = {category: 0 for category in category_list}
    total = 0
    for value in values:
        key = value if value in counts else "unknown"
        counts.setdefault(key, 0)
        counts[key] += 1
        total += 1
    if not total:
        return {category: 0.0 for category in counts}
    return {category: count / total for category, count in counts.items()}


def jensen_shannon_divergence(
    baseline: dict[str, float],
    observed: dict[str, float],
) -> float:
    keys = sorted(set(baseline) | set(observed))
    midpoint = {key: (baseline.get(key, 0.0) + observed.get(key, 0.0)) / 2 for key in keys}

    def kl_divergence(source: dict[str, float]) -> float:
        return sum(
            probability * math.log2(probability / midpoint[key])
            for key in keys
            if (probability := source.get(key, 0.0)) > 0 and midpoint[key] > 0
        )

    return round((kl_divergence(baseline) + kl_divergence(observed)) / 2, 6)


def _baseline_theme_values(df: pd.DataFrame) -> list[str]:
    values: list[str] = []
    for _, row in df.iterrows():
        detected = [theme for theme in THEMES if int(row.get(f"theme_{theme}", 0) or 0) == 1]
        values.extend(detected or ["none"])
    return values


def _observed_theme_values(events: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for event in events:
        detected = [str(theme) for theme in event.get("themes_detected", []) if theme in THEMES]
        values.extend(detected or ["none"])
    return values


def _feedback_metrics(
    events: list[dict[str, Any]],
    feedback_records: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_by_review = {str(event.get("review_id")): event for event in events}
    joined = 0
    presence_correct = 0
    sentiment_evaluated = 0
    sentiment_correct = 0
    combined_correct = 0
    for feedback in feedback_records:
        event = latest_by_review.get(str(feedback.get("review_id")))
        theme = str(feedback.get("theme", ""))
        if event is None or theme not in THEMES:
            continue
        prediction = event.get("theme_predictions", {}).get(theme, {})
        corrected_present = int(feedback.get("corrected_theme_present", 0)) == 1
        predicted_present = bool(prediction.get("present"))
        presence_match = predicted_present == corrected_present
        joined += 1
        presence_correct += int(presence_match)
        sentiment_match = True
        if corrected_present:
            sentiment_evaluated += 1
            sentiment_match = prediction.get("sentiment") == feedback.get("corrected_sentiment")
            sentiment_correct += int(sentiment_match)
        combined_correct += int(presence_match and sentiment_match)
    return {
        "records_available": len(feedback_records),
        "records_joined": joined,
        "theme_presence_accuracy": round(presence_correct / joined, 6) if joined else None,
        "sentiment_accuracy": (
            round(sentiment_correct / sentiment_evaluated, 6) if sentiment_evaluated else None
        ),
        "sentiment_evaluated": sentiment_evaluated,
        "combined_accuracy": round(combined_correct / joined, 6) if joined else None,
    }


def build_drift_report(
    *,
    events: list[dict[str, Any]],
    baseline_df: pd.DataFrame,
    feedback_records: list[dict[str, Any]],
    policy: DriftPolicy,
    created_at: str | None = None,
) -> dict[str, Any]:
    window = events[-policy.prediction_window_size :]
    baseline_sentiments = _probabilities(
        baseline_df["sentiment_label"].astype(str).tolist(),
        [*sorted(ALLOWED_SENTIMENTS), "unknown"],
    )
    observed_sentiments = _probabilities(
        [str(event.get("global_sentiment", "unknown")) for event in window],
        [*sorted(ALLOWED_SENTIMENTS), "unknown"],
    )
    baseline_themes = _probabilities(_baseline_theme_values(baseline_df), [*THEMES, "none", "unknown"])
    observed_themes = _probabilities(_observed_theme_values(window), [*THEMES, "none", "unknown"])
    prediction_count = len(window)
    human_review_rate = (
        sum(bool(event.get("needs_human_review")) for event in window) / prediction_count
        if prediction_count
        else 0.0
    )
    conflict_rate = (
        sum(bool(event.get("sentiment_conflict")) for event in window) / prediction_count
        if prediction_count
        else 0.0
    )
    mean_confidence = (
        sum(float(event.get("global_confidence", 0.0) or 0.0) for event in window)
        / prediction_count
        if prediction_count
        else 0.0
    )
    sentiment_js = jensen_shannon_divergence(baseline_sentiments, observed_sentiments)
    theme_js = jensen_shannon_divergence(baseline_themes, observed_themes)
    feedback = _feedback_metrics(window, feedback_records)
    sufficient_predictions = prediction_count >= policy.minimum_prediction_events
    sufficient_feedback = feedback["records_joined"] >= policy.minimum_feedback_records
    checks = {
        "sentiment_distribution": {
            "evaluated": sufficient_predictions,
            "drifted": sufficient_predictions and sentiment_js > policy.max_sentiment_js_divergence,
            "actual": sentiment_js,
            "operator": "<=",
            "threshold": policy.max_sentiment_js_divergence,
        },
        "theme_distribution": {
            "evaluated": sufficient_predictions,
            "drifted": sufficient_predictions and theme_js > policy.max_theme_js_divergence,
            "actual": theme_js,
            "operator": "<=",
            "threshold": policy.max_theme_js_divergence,
        },
        "human_review_rate": {
            "evaluated": sufficient_predictions,
            "drifted": sufficient_predictions and human_review_rate > policy.max_human_review_rate,
            "actual": round(human_review_rate, 6),
            "operator": "<=",
            "threshold": policy.max_human_review_rate,
        },
        "sentiment_conflict_rate": {
            "evaluated": sufficient_predictions,
            "drifted": sufficient_predictions and conflict_rate > policy.max_sentiment_conflict_rate,
            "actual": round(conflict_rate, 6),
            "operator": "<=",
            "threshold": policy.max_sentiment_conflict_rate,
        },
        "feedback_combined_accuracy": {
            "evaluated": sufficient_feedback,
            "drifted": sufficient_feedback
            and float(feedback["combined_accuracy"] or 0.0)
            < policy.min_feedback_combined_accuracy,
            "actual": feedback["combined_accuracy"],
            "operator": ">=",
            "threshold": policy.min_feedback_combined_accuracy,
        },
    }
    triggers = sorted(name for name, check in checks.items() if check["drifted"])
    drift_detected = bool(triggers)
    if not sufficient_predictions:
        status = "insufficient_data"
        recommendation = "collect_more_predictions"
    elif drift_detected:
        status = "drift_detected"
        recommendation = "retraining_recommended"
    else:
        status = "stable"
        recommendation = "continue_monitoring"
    return {
        "schema_version": "1.0.0",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "status": status,
        "drift_detected": drift_detected,
        "recommendation": recommendation,
        "automatic_retraining_allowed": (
            drift_detected and policy.automatic_retraining_enabled and sufficient_predictions
        ),
        "triggers": triggers,
        "window": {
            "prediction_events": prediction_count,
            "maximum_events": policy.prediction_window_size,
            "minimum_required": policy.minimum_prediction_events,
        },
        "metrics": {
            "sentiment_js_divergence": sentiment_js,
            "theme_js_divergence": theme_js,
            "human_review_rate": round(human_review_rate, 6),
            "sentiment_conflict_rate": round(conflict_rate, 6),
            "mean_global_confidence": round(mean_confidence, 6),
            "feedback": feedback,
        },
        "distributions": {
            "baseline_sentiment": baseline_sentiments,
            "observed_sentiment": observed_sentiments,
            "baseline_theme": baseline_themes,
            "observed_theme": observed_themes,
        },
        "checks": checks,
        "policy": asdict(policy),
        "privacy": {
            "raw_review_text_stored": False,
            "stored_features": "review id, model version, outputs, confidence, flags and text length",
        },
    }


def write_drift_report(report: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary_path.replace(output_path)
    return output_path


def evaluate_drift(
    *,
    event_store_path: Path,
    feedback_store_path: Path,
    data_root: Path,
    output_path: Path,
    policy_path: Path = DEFAULT_DRIFT_POLICY_PATH,
) -> dict[str, Any]:
    policy = load_drift_policy(policy_path)
    events = read_prediction_events(event_store_path, limit=policy.prediction_window_size)
    feedback_records = read_feedback(feedback_store_path, limit=policy.prediction_window_size)
    dataset_path = latest_ready_validated_dataset(data_root)
    if dataset_path is None:
        report = {
            "schema_version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "baseline_unavailable",
            "drift_detected": False,
            "recommendation": "ingest_ready_baseline",
            "automatic_retraining_allowed": False,
            "triggers": [],
            "window": {
                "prediction_events": len(events),
                "maximum_events": policy.prediction_window_size,
                "minimum_required": policy.minimum_prediction_events,
            },
            "metrics": {"feedback": {"records_available": len(feedback_records), "records_joined": 0}},
            "checks": {},
            "policy": asdict(policy),
            "privacy": {"raw_review_text_stored": False},
            "baseline_dataset_path": None,
        }
    else:
        report = build_drift_report(
            events=events,
            baseline_df=load_training_dataset(dataset_path),
            feedback_records=feedback_records,
            policy=policy,
        )
        report["baseline_dataset_path"] = str(dataset_path)
    report["prediction_event_store_path"] = str(event_store_path)
    report["feedback_store_path"] = str(feedback_store_path)
    report["report_path"] = str(output_path)
    write_drift_report(report, output_path)
    return report


def _candidate_records(dataframe: pd.DataFrame) -> dict[str, tuple[Any, ...]]:
    comparison_columns = [*REQUIRED_TRAINING_COLUMNS, *THEME_SENTIMENT_COLUMNS]
    records: dict[str, tuple[Any, ...]] = {}
    for _, row in dataframe.iterrows():
        review_id = str(row.get("review_id", "")).strip()
        values: list[Any] = []
        for column in comparison_columns:
            value = row.get(column, "")
            if column.startswith("theme_"):
                numeric = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0]
                values.append(int(numeric))
            else:
                normalized = "" if pd.isna(value) else str(value).strip()
                if column.startswith("sentiment_") or column == "sentiment_label":
                    normalized = normalized.lower()
                values.append(normalized)
        records[review_id] = tuple(values)
    return records


def inspect_labeled_candidate_csv(
    source_path: Path,
    *,
    minimum_rows: int,
    baseline_path: Path | None = None,
    minimum_changed_rows: int = 1,
) -> dict[str, Any]:
    try:
        dataframe = pd.read_csv(source_path)
    except Exception as exc:
        return {"ready": False, "rows": 0, "reason": f"unreadable_csv:{type(exc).__name__}"}
    required_columns = [*REQUIRED_TRAINING_COLUMNS, *THEME_SENTIMENT_COLUMNS]
    missing_columns = sorted(set(required_columns) - set(dataframe.columns))
    invalid_theme_sentiments = 0
    if not missing_columns:
        for theme in THEMES:
            active = pd.to_numeric(dataframe[f"theme_{theme}"], errors="coerce").fillna(0) == 1
            sentiments = dataframe[f"sentiment_{theme}"].astype("string").str.lower()
            invalid_theme_sentiments += int((active & ~sentiments.isin(ALLOWED_SENTIMENTS)).sum())
    changed_rows = len(dataframe)
    if baseline_path is not None and baseline_path.is_file() and not missing_columns:
        try:
            baseline_records = _candidate_records(load_training_dataset(baseline_path))
            candidate_records = _candidate_records(dataframe)
        except Exception as exc:
            return {
                "ready": False,
                "rows": len(dataframe),
                "reason": f"unreadable_baseline:{type(exc).__name__}",
            }
        changed_rows = sum(
            baseline_records.get(review_id) != fingerprint
            for review_id, fingerprint in candidate_records.items()
        )
    ready = (
        len(dataframe) >= minimum_rows
        and changed_rows >= minimum_changed_rows
        and not missing_columns
        and dataframe["sentiment_label"].astype("string").str.lower().isin(ALLOWED_SENTIMENTS).all()
        and invalid_theme_sentiments == 0
    ) if not missing_columns else False
    if ready:
        reason = "ready"
    elif changed_rows < minimum_changed_rows:
        reason = "insufficient_changed_labeled_rows"
    else:
        reason = "labeled_dataset_requirements_not_met"
    return {
        "ready": bool(ready),
        "rows": len(dataframe),
        "minimum_rows": minimum_rows,
        "changed_rows": changed_rows,
        "minimum_changed_rows": minimum_changed_rows,
        "missing_columns": missing_columns,
        "invalid_theme_sentiments": invalid_theme_sentiments,
        "reason": reason,
    }
