from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.train_models import _evaluate_trained_artifacts


def evaluate_artifacts(model_dir: Path, dataset_path: Path, output_path: Path) -> dict[str, object]:
    frame = pd.read_parquet(dataset_path)
    metrics = _evaluate_trained_artifacts(model_dir, frame)
    report: dict[str, object] = {
        "schema_version": "1.0.0",
        "model_dir": str(model_dir),
        "dataset_path": str(dataset_path),
        "summary": metrics,
        "metrics": metrics,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a model artifact set on a labeled Parquet dataset.")
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("dataset_path", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate_artifacts(args.model_dir, args.dataset_path, args.output_path), indent=2))


if __name__ == "__main__":
    main()
