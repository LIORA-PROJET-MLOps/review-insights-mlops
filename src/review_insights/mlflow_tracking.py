from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Dict, Iterable
from urllib import parse, request

from .settings import Settings, get_settings


@dataclass
class MLflowRunResult:
    status: str
    tracking_uri: str
    experiment_name: str
    run_id: str | None = None
    reason: str | None = None


def _numeric_metrics(summary: Dict) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    for key in ("rows", "sentiment_accuracy", "theme_exact_match", "theme_precision_macro", "theme_recall_macro"):
        value = summary.get(key)
        if isinstance(value, (int, float)):
            metrics[key] = float(value)
    return metrics


def log_evaluation_run(
    report: Dict,
    *,
    settings: Settings | None = None,
    artifact_paths: Iterable[Path] | None = None,
    run_name: str = "default_evaluation",
) -> MLflowRunResult:
    resolved_settings = settings or get_settings()
    tracking_uri = resolved_settings.mlflow_tracking_uri
    experiment_name = resolved_settings.mlflow_experiment_name

    if not resolved_settings.mlflow_tracking_enabled:
        return MLflowRunResult(
            status="disabled",
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            reason="MLFLOW_TRACKING_ENABLED is false.",
        )

    if tracking_uri.startswith(("http://", "https://")):
        return _log_evaluation_run_http(
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            report=report,
            run_name=run_name,
        )

    try:
        import mlflow
    except ImportError:
        return MLflowRunResult(
            status="skipped",
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            reason="mlflow package is not installed.",
        )

    summary = report.get("summary", {})
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=run_name) as active_run:
        mlflow.log_params(
            {
                "backend_name": summary.get("backend_name", "unknown"),
                "dataset": "default_reviews",
            }
        )
        for metric_name, metric_value in _numeric_metrics(summary).items():
            mlflow.log_metric(metric_name, metric_value)
        for artifact_path in artifact_paths or []:
            if artifact_path.exists():
                mlflow.log_artifact(str(artifact_path))
        return MLflowRunResult(
            status="logged",
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            run_id=active_run.info.run_id,
        )


def _mlflow_request(tracking_uri: str, path: str, payload: Dict | None = None, method: str = "POST") -> Dict:
    url = f"{tracking_uri.rstrip('/')}{path}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=10) as response:
        content = response.read().decode("utf-8")
    return json.loads(content) if content else {}


def _get_or_create_experiment_id(tracking_uri: str, experiment_name: str) -> str:
    query = parse.urlencode({"experiment_name": experiment_name})
    try:
        response = _mlflow_request(
            tracking_uri,
            f"/api/2.0/mlflow/experiments/get-by-name?{query}",
            method="GET",
        )
        experiment = response.get("experiment")
        if experiment and experiment.get("experiment_id"):
            return str(experiment["experiment_id"])
    except Exception:
        pass

    response = _mlflow_request(
        tracking_uri,
        "/api/2.0/mlflow/experiments/create",
        {"name": experiment_name},
    )
    return str(response["experiment_id"])


def _log_evaluation_run_http(
    *,
    tracking_uri: str,
    experiment_name: str,
    report: Dict,
    run_name: str,
) -> MLflowRunResult:
    try:
        experiment_id = _get_or_create_experiment_id(tracking_uri, experiment_name)
        now_ms = int(time.time() * 1000)
        run_response = _mlflow_request(
            tracking_uri,
            "/api/2.0/mlflow/runs/create",
            {
                "experiment_id": experiment_id,
                "start_time": now_ms,
                "tags": [{"key": "mlflow.runName", "value": run_name}],
            },
        )
        run_id = run_response["run"]["info"]["run_id"]
        summary = report.get("summary", {})
        _mlflow_request(
            tracking_uri,
            "/api/2.0/mlflow/runs/log-batch",
            {
                "run_id": run_id,
                "params": [
                    {"key": "backend_name", "value": str(summary.get("backend_name", "unknown"))},
                    {"key": "dataset", "value": "default_reviews"},
                ],
                "metrics": [
                    {"key": key, "value": value, "timestamp": now_ms, "step": 0}
                    for key, value in _numeric_metrics(summary).items()
                ],
            },
        )
        _mlflow_request(
            tracking_uri,
            "/api/2.0/mlflow/runs/update",
            {"run_id": run_id, "status": "FINISHED", "end_time": int(time.time() * 1000)},
        )
        return MLflowRunResult(
            status="logged",
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            run_id=run_id,
        )
    except Exception as exc:
        return MLflowRunResult(
            status="skipped",
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            reason=f"MLflow HTTP logging failed: {exc}",
        )
