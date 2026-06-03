from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.review_insights.data_store import default_data_root, ingest_csv_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a review CSV into the local Review Insights+ data store.")
    parser.add_argument("source_csv", help="Path to the source CSV file.")
    parser.add_argument("--data-root", default=str(default_data_root(ROOT_DIR)))
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--quality-policy-path", default=None)
    parser.add_argument(
        "--enforce-quality-gates",
        action="store_true",
        help="Fail after writing diagnostic artifacts when the dataset is not staging-ready.",
    )
    args = parser.parse_args()

    result = ingest_csv_dataset(
        source_path=Path(args.source_csv),
        data_root=Path(args.data_root),
        dataset_version=args.dataset_version,
        quality_policy_path=Path(args.quality_policy_path) if args.quality_policy_path else None,
        enforce_quality_gates=args.enforce_quality_gates,
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
