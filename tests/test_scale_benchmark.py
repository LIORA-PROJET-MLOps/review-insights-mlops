from types import SimpleNamespace

from pipelines.run_scale_benchmark import select_champion_candidate


def _metrics(value: float) -> dict[str, float]:
    return {
        "rows": 1000,
        "sentiment_accuracy": value,
        "sentiment_macro_f1": value,
        "theme_exact_match": value,
        "theme_precision_macro": value,
        "theme_recall_macro": value,
        "theme_f1_macro": value,
        "human_review_rate": 0.05,
    }


def _policy():
    return SimpleNamespace(
        required_metrics={
            "rows": 30,
            "sentiment_accuracy": 0.55,
            "sentiment_macro_f1": 0.5,
            "theme_exact_match": 0.65,
            "theme_precision_macro": 0.85,
            "theme_recall_macro": 0.85,
            "theme_f1_macro": 0.85,
        },
        maximum_metrics={"human_review_rate": 0.6},
        max_metric_regression={},
    )


def test_selection_prefers_robust_candidate_that_passes_every_profile():
    candidates = [
        {
            "name": "fragile",
            "aggregate_metrics": _metrics(0.96),
            "profile_metrics": {
                "balanced": _metrics(0.99),
                "noisy": _metrics(0.80),
            },
            "training_seconds": 1.0,
        },
        {
            "name": "robust",
            "aggregate_metrics": _metrics(0.93),
            "profile_metrics": {
                "balanced": _metrics(0.93),
                "noisy": _metrics(0.93),
            },
            "training_seconds": 1.0,
        },
    ]

    selected = select_champion_candidate(candidates, _policy())

    assert selected is not None
    assert selected["name"] == "robust"
    assert selected["eligible"] is True


def test_selection_rejects_candidate_with_failing_segment():
    candidate = {
        "name": "fails-noisy",
        "aggregate_metrics": _metrics(0.90),
        "profile_metrics": {"balanced": _metrics(0.95), "noisy": _metrics(0.49)},
        "training_seconds": 1.0,
    }

    assert select_champion_candidate([candidate], _policy()) is None
    assert candidate["eligible"] is False
