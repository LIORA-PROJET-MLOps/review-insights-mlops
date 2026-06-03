import json
from pathlib import Path

import pandas as pd

from src.review_insights.data_quality import (
    build_annotation_queue,
    build_quality_report,
    load_quality_policy,
)


def test_annotation_queue_is_normalized_by_review_and_theme():
    df = pd.DataFrame(
        [
            {
                "review_id": "r1",
                "review_title": "Mixed experience",
                "review_body": "Delivery was fast but the product was poor.",
                "sentiment_label": "negative",
                "theme_livraison": 1,
                "theme_sav": 0,
                "theme_produit": 1,
                "sentiment_livraison": "positive",
                "sentiment_produit": "",
            }
        ]
    )

    queue = build_annotation_queue(df)

    assert queue["annotation_id"].tolist() == ["r1:produit"]
    assert queue.iloc[0]["label_column"] == "sentiment_produit"
    assert queue.iloc[0]["annotation_status"] == "pending"


def test_quality_report_flags_probable_pii_language_and_missing_theme_labels(tmp_path: Path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "policy_version": "test",
                "dataset_schema_version": "1.0.0",
                "language_scope": "english_reviews_only",
                "gates": {
                    "min_valid_rows": 1,
                    "min_sentiment_class_rows": 0,
                    "min_theme_positive_rows": 0,
                    "max_rejected_fraction": 1.0,
                    "max_probable_pii_rows": 0,
                    "max_probable_non_english_fraction": 0.0,
                    "min_explicit_theme_sentiment_coverage": 1.0,
                },
            }
        ),
        encoding="utf-8",
    )
    valid = pd.DataFrame(
        [
            {
                "review_id": "r1",
                "review_title": "",
                "review_body": "Mon produit est mauvais et contactez test@example.com",
                "sentiment_label": "negative",
                "theme_livraison": 0,
                "theme_sav": 0,
                "theme_produit": 1,
            }
        ]
    )

    report = build_quality_report(valid, valid, valid.iloc[0:0], load_quality_policy(policy_path))

    assert report["status"] == "not_ready"
    assert report["profile"]["probable_pii_rows"] == 1
    assert report["profile"]["probable_non_english_rows"] == 1
    assert "min_explicit_theme_sentiment_coverage_produit" in report["failed_checks"]
