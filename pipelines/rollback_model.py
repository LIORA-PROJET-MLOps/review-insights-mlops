from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.review_insights.model_registry import (
    DEFAULT_PROMOTION_POLICY_PATH,
    load_promotion_policy,
    rollback_champion,
)
from src.review_insights.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Rollback the MLflow champion alias to previous_champion.")
    parser.add_argument("--tracking-uri", default=None)
    parser.add_argument("--policy-path", default=str(DEFAULT_PROMOTION_POLICY_PATH))
    parser.add_argument("--registered-model-name", default=None)
    parser.add_argument("--report-path", default=None)
    parser.add_argument("--deploy-model-dir", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        import mlflow
        from mlflow import MlflowClient
    except ImportError as exc:
        raise SystemExit("The mlflow package is required for model rollback.") from exc

    tracking_uri = args.tracking_uri or get_settings().mlflow_tracking_uri
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)
    result = rollback_champion(
        client,
        policy=load_promotion_policy(Path(args.policy_path)),
        registered_model_name=args.registered_model_name,
        report_path=Path(args.report_path) if args.report_path else None,
        deploy_model_dir=Path(args.deploy_model_dir) if args.deploy_model_dir else None,
        dry_run=args.dry_run,
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
