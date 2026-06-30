import json

import pandas as pd

from src.review_insights.drift import (
    DriftPolicy,
    build_drift_report,
    evaluate_drift,
    inspect_labeled_candidate_csv,
    jensen_shannon_divergence,
)


def _policy(**overrides) -> DriftPolicy:
    values = {
        "policy_version": "test",
        "prediction_window_size": 100,
        "minimum_prediction_events": 2,
        "minimum_feedback_records": 2,
        "minimum_retraining_rows": 3,
        "minimum_changed_labeled_rows": 1,
        "max_sentiment_js_divergence": 0.1,
        "max_theme_js_divergence": 0.1,
        "max_human_review_rate": 0.6,
        "max_sentiment_conflict_rate": 0.2,
        "min_feedback_combined_accuracy": 0.7,
        "automatic_retraining_enabled": True,
        "require_new_labeled_csv": True,
    }
    return DriftPolicy(**(values | overrides))


def _baseline() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "review_id": "r1",
                "review_body": "good delivery",
                "sentiment_label": "positive",
                "theme_livraison": 1,
                "theme_sav": 0,
                "theme_produit": 0,
                "sentiment_livraison": "positive",
                "sentiment_sav": "neutral",
                "sentiment_produit": "neutral",
            },
            {
                "review_id": "r2",
                "review_body": "bad support",
                "sentiment_label": "negative",
                "theme_livraison": 0,
                "theme_sav": 1,
                "theme_produit": 0,
                "sentiment_livraison": "neutral",
                "sentiment_sav": "negative",
                "sentiment_produit": "neutral",
            },
        ]
    )


def _event(review_id: str, sentiment: str, theme: str) -> dict:
    return {
        "review_id": review_id,
        "global_sentiment": sentiment,
        "global_confidence": 0.9,
        "themes_detected": [theme],
        "theme_predictions": {
            "livraison": {"present": theme == "livraison", "sentiment": sentiment},
            "sav": {"present": theme == "sav", "sentiment": sentiment},
            "produit": {"present": theme == "produit", "sentiment": sentiment},
        },
        "needs_human_review": False,
        "sentiment_conflict": False,
    }


def test_jensen_shannon_divergence_is_zero_for_equal_distributions():
    distribution = {"positive": 0.5, "negative": 0.5}
    assert jensen_shannon_divergence(distribution, distribution) == 0.0


def test_drift_report_is_stable_for_matching_window():
    report = build_drift_report(
        events=[_event("r1", "positive", "livraison"), _event("r2", "negative", "sav")],
        baseline_df=_baseline(),
        feedback_records=[],
        policy=_policy(),
    )

    assert report["status"] == "stable"
    assert report["recommendation"] == "continue_monitoring"
    assert report["automatic_retraining_allowed"] is False
    assert report["privacy"]["raw_review_text_stored"] is False


def test_drift_and_low_feedback_accuracy_recommend_controlled_retraining():
    events = [_event("r1", "negative", "produit"), _event("r2", "negative", "produit")]
    feedback = [
        {
            "review_id": review_id,
            "theme": "produit",
            "corrected_theme_present": 0,
            "corrected_sentiment": "negative",
        }
        for review_id in ("r1", "r2")
    ]

    report = build_drift_report(
        events=events,
        baseline_df=_baseline(),
        feedback_records=feedback,
        policy=_policy(),
    )

    assert report["status"] == "drift_detected"
    assert report["recommendation"] == "retraining_recommended"
    assert report["automatic_retraining_allowed"] is True
    assert "feedback_combined_accuracy" in report["triggers"]


def test_drift_report_waits_for_minimum_prediction_window():
    report = build_drift_report(
        events=[_event("r1", "negative", "produit")],
        baseline_df=_baseline(),
        feedback_records=[],
        policy=_policy(),
    )

    assert report["status"] == "insufficient_data"
    assert report["drift_detected"] is False


def test_evaluate_drift_writes_baseline_unavailable_report(tmp_path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "policy_version": "test",
                "prediction_window_size": 100,
                "minimum_prediction_events": 2,
                "minimum_feedback_records": 2,
                "minimum_retraining_rows": 3,
                "minimum_changed_labeled_rows": 1,
                "thresholds": {
                    "max_sentiment_js_divergence": 0.1,
                    "max_theme_js_divergence": 0.1,
                    "max_human_review_rate": 0.6,
                    "max_sentiment_conflict_rate": 0.2,
                    "min_feedback_combined_accuracy": 0.7,
                },
                "automatic_retraining": {"enabled": True, "require_new_labeled_csv": True},
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "reports" / "drift.json"

    report = evaluate_drift(
        event_store_path=tmp_path / "events.jsonl",
        feedback_store_path=tmp_path / "feedback.jsonl",
        data_root=tmp_path / "data",
        policy_path=policy_path,
        output_path=output,
    )

    assert report["status"] == "baseline_unavailable"
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "baseline_unavailable"


def test_labeled_candidate_validation_enforces_columns_and_minimum_rows(tmp_path):
    valid_path = tmp_path / "valid.csv"
    pd.concat([_baseline(), _baseline().assign(review_id="r3")], ignore_index=True).to_csv(
        valid_path, index=False
    )
    invalid_path = tmp_path / "invalid.csv"
    pd.DataFrame([{"review_id": "r1"}]).to_csv(invalid_path, index=False)

    valid = inspect_labeled_candidate_csv(valid_path, minimum_rows=3)
    invalid = inspect_labeled_candidate_csv(invalid_path, minimum_rows=3)

    assert valid["ready"] is True
    assert invalid["ready"] is False
    assert "review_body" in invalid["missing_columns"]


def test_labeled_candidate_requires_a_meaningful_delta_from_baseline(tmp_path):
    baseline_path = tmp_path / "baseline.csv"
    candidate_path = tmp_path / "candidate.csv"
    baseline = pd.concat([_baseline()] * 5, ignore_index=True)
    baseline["review_id"] = [f"r{index}" for index in range(len(baseline))]
    baseline.to_csv(baseline_path, index=False)
    candidate = baseline.copy()
    candidate.loc[0, "review_id"] = "one-new-review"
    candidate.to_csv(candidate_path, index=False)

    result = inspect_labeled_candidate_csv(
        candidate_path,
        minimum_rows=3,
        baseline_path=baseline_path,
        minimum_changed_rows=2,
    )

    assert result["ready"] is False
    assert result["changed_rows"] == 1
    assert result["reason"] == "insufficient_changed_labeled_rows"
