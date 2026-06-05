from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.review_insights.annotation import prepare_annotation_batch
from src.review_insights.data_store import default_data_root


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a portable theme-sentiment annotation batch from a review CSV."
    )
    parser.add_argument("source_csv", help="Path to the source CSV file.")
    parser.add_argument("--data-root", default=str(default_data_root(ROOT_DIR)))
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--output-dir", default=str(ROOT_DIR / "artifacts" / "annotation_batches"))
    parser.add_argument("--quality-policy-path", default=None)
    args = parser.parse_args()

    result = prepare_annotation_batch(
        Path(args.source_csv),
        output_dir=Path(args.output_dir),
        data_root=Path(args.data_root),
        dataset_version=args.dataset_version,
        quality_policy_path=Path(args.quality_policy_path) if args.quality_policy_path else None,
    )
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
