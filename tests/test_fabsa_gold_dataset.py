from __future__ import annotations

import pandas as pd

from pipelines.build_fabsa_gold_dataset import (
    DEFAULT_QUOTAS,
    _coarse_theme_sentiments,
    _overall_sentiment,
    sample_stratified,
    transform_source_frame,
)


def test_coarse_mapping_and_global_sentiment() -> None:
    labels = [
        ["Logistics rides: Speed", "negative"],
        ["Staff support: Phone", "positive"],
        ["Online experience: App website", "positive"],
    ]
    sentiments, conflict = _coarse_theme_sentiments(labels)
    assert conflict is False
    assert sentiments == {
        "livraison": "negative",
        "sav": "positive",
        "produit": "positive",
    }
    assert _overall_sentiment(sentiments) == "neutral"


def test_conflicting_labels_are_excluded() -> None:
    frame = pd.DataFrame(
        [
            {
                "id": 1,
                "data_source": "Trustpilot",
                "industry": "Fashion",
                "text": "Support answered but the phone agent was rude and unhelpful.",
                "labels": [
                    ["Staff support: Phone", "positive"],
                    ["Staff support: Attitude of staff", "negative"],
                ],
            }
        ]
    )
    transformed, exclusions = transform_source_frame(frame, "train")
    assert transformed.empty
    assert exclusions["coarse_theme_sentiment_conflict"] == 1


def test_stratified_sampler_honors_requested_cells() -> None:
    rows = []
    for theme, sentiments in DEFAULT_QUOTAS["validation"].items():
        for sentiment, requested in sentiments.items():
            for idx in range(requested + 2):
                rows.append(
                    {
                        "review_id": f"{theme}-{sentiment}-{idx}",
                        "primary_theme": theme,
                        "sentiment_label": sentiment,
                    }
                )
    selected = sample_stratified(
        pd.DataFrame(rows),
        "validation",
        DEFAULT_QUOTAS["validation"],
        seed=7,
    )
    assert len(selected) == 150
    observed = selected.groupby(["primary_theme", "sentiment_label"]).size().to_dict()
    for theme, sentiments in DEFAULT_QUOTAS["validation"].items():
        for sentiment, requested in sentiments.items():
            assert observed[(theme, sentiment)] == requested
