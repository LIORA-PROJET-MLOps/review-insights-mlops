from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.review_insights.drift import DEFAULT_DRIFT_POLICY_PATH, evaluate_drift


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate production prediction and labeled-feedback drift.",
    )
    parser.add_argument(
        "--event-store",
        type=Path,
        default=Path(os.getenv("PREDICTION_EVENT_STORE_PATH", "data/predictions/prediction_events.jsonl")),
    )
    parser.add_argument(
        "--feedback-store",
        type=Path,
        default=Path(os.getenv("FEEDBACK_STORE_PATH", "data/feedback/human_feedback.jsonl")),
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(os.getenv("ORCHESTRATOR_DATA_ROOT", "data")),
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path(os.getenv("DRIFT_POLICY_PATH", str(DEFAULT_DRIFT_POLICY_PATH))),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.getenv("DRIFT_REPORT_PATH", "reports/drift/latest_drift_report.json")),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = evaluate_drift(
        event_store_path=args.event_store,
        feedback_store_path=args.feedback_store,
        data_root=args.data_root,
        output_path=args.output,
        policy_path=args.policy,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
