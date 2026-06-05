import json
from pathlib import Path

from src.review_insights.release import build_model_release_report


def test_build_model_release_report_applies_promotion_gates(tmp_path: Path):
    evaluation_path = tmp_path / "evaluation.json"
    evaluation_path.write_text(
        json.dumps(
            {
                "summary": {
                    "rows": 40,
                    "sentiment_accuracy": 0.6,
                    "sentiment_macro_f1": 0.55,
                    "theme_exact_match": 0.7,
                    "theme_precision_macro": 0.9,
                    "theme_recall_macro": 0.9,
                    "theme_f1_macro": 0.9,
                    "human_review_rate": 0.4,
                }
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"artifact_set_version": "test"}', encoding="utf-8")

    report = build_model_release_report(
        evaluation_report_path=evaluation_path,
        model_manifest_path=manifest_path,
        output_json_path=tmp_path / "release.json",
        output_markdown_path=tmp_path / "release.md",
    )

    assert report.status == "approved"
    assert report.gate_report["failed_checks"] == []
    assert (tmp_path / "release.json").exists()
    assert (tmp_path / "release.md").exists()
