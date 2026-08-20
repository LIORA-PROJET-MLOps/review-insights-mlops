from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.review_insights.mlflow_tracking import log_training_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Register an evaluated project-model candidate in MLflow.")
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("evaluation_report", type=Path)
    parser.add_argument("--training-dataset", required=True)
    parser.add_argument("--run-name", default="real_gold_release_candidate")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.evaluation_report.read_text(encoding="utf-8"))
    summary = dict(report.get("summary") or report.get("metrics") or {})
    summary.update(
        {
            "training_dataset": args.training_dataset,
            "evaluation_dataset": str(report.get("dataset_path", args.evaluation_report)),
            "backend_name": "project_models_v1",
        }
    )
    result = log_training_run(
        summary,
        model_artifact_dir=args.model_dir,
        run_name=args.run_name,
        register_model=True,
        model_alias="candidate",
    )
    payload = {"summary": summary, "mlflow": asdict(result)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if result.status != "logged" or not result.registered_model_version:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
