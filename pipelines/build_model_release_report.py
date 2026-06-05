from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.review_insights.release import build_model_release_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a local model release report from evaluation metrics and promotion gates."
    )
    parser.add_argument("--evaluation-report", default=str(ROOT_DIR / "reports" / "default_evaluation.json"))
    parser.add_argument("--promotion-policy", default=str(ROOT_DIR / "config" / "model_promotion_policy_v1.json"))
    parser.add_argument("--model-manifest", default=str(ROOT_DIR / "models" / "manifest.json"))
    parser.add_argument("--output-json", default=str(ROOT_DIR / "reports" / "model_release_report.json"))
    parser.add_argument("--output-md", default=str(ROOT_DIR / "reports" / "model_release_report.md"))
    args = parser.parse_args()

    report = build_model_release_report(
        evaluation_report_path=Path(args.evaluation_report),
        promotion_policy_path=Path(args.promotion_policy),
        model_manifest_path=Path(args.model_manifest),
        output_json_path=Path(args.output_json),
        output_markdown_path=Path(args.output_md),
    )
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    if report.status == "rejected":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
