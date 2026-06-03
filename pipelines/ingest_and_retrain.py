from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.train_models import build_training_artifacts
from src.review_insights.data_store import default_data_root, ingest_csv_dataset
from src.review_insights.mlflow_tracking import log_training_run


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)


def ingest_and_retrain(
    source_csv: Path,
    *,
    data_root: Path,
    dataset_version: str | None = None,
    output_dir: Path | None = None,
    threshold: float = 0.5,
    mlflow_log: bool = False,
    register_model: bool = False,
    registered_model_name: str = "review-insights-project-models",
    model_stage: str = "candidate",
) -> dict[str, Any]:
    ingestion = ingest_csv_dataset(
        source_path=source_csv,
        data_root=data_root,
        dataset_version=dataset_version,
    )
    resolved_output_dir = output_dir or ROOT_DIR / "artifacts" / f"trained_models_{_safe_name(ingestion.dataset_version)}"
    training_dataset_path = Path(ingestion.train_path or ingestion.validated_path)
    evaluation_dataset_path = Path(ingestion.test_path) if ingestion.test_path else None
    training = build_training_artifacts(
        resolved_output_dir,
        threshold=threshold,
        dataset_path=training_dataset_path,
        evaluation_dataset_path=evaluation_dataset_path,
    )
    if mlflow_log or register_model:
        mlflow_result = log_training_run(
            training,
            model_artifact_dir=resolved_output_dir,
            register_model=register_model,
            registered_model_name=registered_model_name,
            model_stage=model_stage,
        )
        training["mlflow"] = asdict(mlflow_result)
    return {
        "ingestion": asdict(ingestion),
        "training": training,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a review CSV, validate it, retrain models, and optionally log/register in MLflow.")
    parser.add_argument("source_csv", help="Path to the source CSV file.")
    parser.add_argument("--data-root", default=str(default_data_root(ROOT_DIR)))
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--mlflow-log", action="store_true", help="Log the training run and artifacts to MLflow.")
    parser.add_argument("--register-model", action="store_true", help="Register the trained model as a candidate model version.")
    parser.add_argument("--registered-model-name", default="review-insights-project-models")
    parser.add_argument("--model-stage", default="candidate")
    args = parser.parse_args()

    result = ingest_and_retrain(
        Path(args.source_csv),
        data_root=Path(args.data_root),
        dataset_version=args.dataset_version,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        threshold=args.threshold,
        mlflow_log=args.mlflow_log,
        register_model=args.register_model,
        registered_model_name=args.registered_model_name,
        model_stage=args.model_stage,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
