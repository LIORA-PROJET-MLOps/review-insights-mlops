from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Dict, Iterable
from urllib import parse, request

from .model_backend import ARTIFACT_FILENAMES
from .settings import Settings, get_settings


@dataclass
class MLflowRunResult:
    status: str
    tracking_uri: str
    experiment_name: str
    run_id: str | None = None
    reason: str | None = None
    model_logged: bool = False
    artifact_count: int = 0
    registered_model_name: str | None = None
    registered_model_version: str | None = None
    model_alias: str | None = None


def _configure_mlflow_console_output() -> None:
    # MLflow 3 prints emoji-prefixed run URLs, which can fail on Windows cp1252 consoles.
    os.environ.setdefault("MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT", "true")
    os.environ.setdefault("MLFLOW_PRINT_MODEL_URLS_ON_CREATION", "false")


def _numeric_metrics(summary: Dict) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    for key in (
        "rows",
        "sentiment_accuracy",
        "sentiment_macro_precision",
        "sentiment_macro_recall",
        "sentiment_macro_f1",
        "sentiment_evaluated_rows",
        "theme_exact_match",
        "theme_precision_macro",
        "theme_recall_macro",
        "theme_f1_macro",
        "human_review_rate",
    ):
        value = summary.get(key)
        if isinstance(value, (int, float)):
            metrics[key] = float(value)
    return metrics


def _resolve_model_artifact_dir(settings: Settings, model_artifact_dir: Path | str | None = None) -> Path:
    if model_artifact_dir is not None:
        return Path(model_artifact_dir)
    if settings.model_source.strip().lower() == "hf_hub":
        return Path(settings.hf_artifacts_dir)
    return Path(settings.models_dir)


def _complete_model_artifact_dir(settings: Settings, model_artifact_dir: Path | str | None = None) -> Path | None:
    resolved_dir = _resolve_model_artifact_dir(settings, model_artifact_dir)
    if not resolved_dir.exists() or not resolved_dir.is_dir():
        return None
    missing = [filename for filename in ARTIFACT_FILENAMES if not (resolved_dir / filename).exists()]
    return None if missing else resolved_dir


def _model_params(model_dir: Path | None) -> Dict[str, str]:
    if model_dir is None:
        return {"model_artifacts_present": "false"}

    params = {
        "model_artifacts_present": "true",
        "model_artifact_path": "model",
        "model_artifact_files": ",".join(ARTIFACT_FILENAMES),
    }
    manifest_path = model_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            params["model_project"] = str(manifest.get("project", "unknown"))
            params["model_artifact_set_version"] = str(manifest.get("artifact_set_version", "unknown"))
            params["model_language_scope"] = str(manifest.get("language_scope", "unknown"))
        except Exception:
            params["model_manifest_readable"] = "false"
    return params


def _count_files(path: Path) -> int:
    if path.is_file():
        return 1
    if path.is_dir():
        return sum(1 for item in path.rglob("*") if item.is_file())
    return 0


def _create_mlflow_client(mlflow_module: object) -> object | None:
    tracking_module = getattr(mlflow_module, "tracking", None)
    if tracking_module is not None and hasattr(tracking_module, "MlflowClient"):
        return tracking_module.MlflowClient()
    if hasattr(mlflow_module, "MlflowClient"):
        return mlflow_module.MlflowClient()
    return None


def _extract_registered_model_version(model_info: object) -> str | None:
    for attr in ("registered_model_version", "version"):
        value = getattr(model_info, attr, None)
        if value is not None:
            return str(value)
    return None


def _review_insights_model_signature(mlflow_module: object) -> object | None:
    try:
        model_signature = mlflow_module.models.ModelSignature
        schema = mlflow_module.types.Schema
        col_spec = mlflow_module.types.ColSpec
        return model_signature(
            inputs=schema(
                [
                    col_spec("string", "review_id"),
                    col_spec("string", "review_text"),
                ]
            )
        )
    except Exception:
        return None


def _find_registered_model_version(
    client: object | None,
    *,
    registered_model_name: str,
    run_id: str,
) -> str | None:
    if client is None or not hasattr(client, "search_model_versions"):
        return None
    try:
        versions = client.search_model_versions(f"name='{registered_model_name}'")
    except Exception:
        return None
    matching = [
        version
        for version in versions
        if str(getattr(version, "run_id", "")) == run_id and getattr(version, "version", None) is not None
    ]
    if not matching:
        return None
    return str(getattr(matching[-1], "version"))


def _tag_registered_model_version(
    client: object | None,
    *,
    registered_model_name: str,
    registered_model_version: str | None,
    model_alias: str,
    summary: Dict,
) -> None:
    if client is None or registered_model_version is None:
        return
    tags = {
        "lifecycle_alias": model_alias,
        "training_dataset": str(summary.get("training_dataset", "unknown")),
        "backend_name": str(summary.get("backend_name", "project_models_v1")),
    }
    if hasattr(client, "set_model_version_tag"):
        for key, value in tags.items():
            client.set_model_version_tag(registered_model_name, registered_model_version, key, value)
    if hasattr(client, "set_registered_model_alias"):
        client.set_registered_model_alias(registered_model_name, model_alias, registered_model_version)


def _register_training_model(
    mlflow_module: object,
    *,
    model_dir: Path,
    registered_model_name: str,
    run_id: str,
) -> tuple[str | None, str | None]:
    from .mlflow_model import ReviewInsightsPyFuncModel

    try:
        model_info = mlflow_module.pyfunc.log_model(
            name="registered_model",
            python_model=ReviewInsightsPyFuncModel(),
            artifacts={"model_dir": str(model_dir)},
            registered_model_name=registered_model_name,
            signature=_review_insights_model_signature(mlflow_module),
        )
        return _extract_registered_model_version(model_info), None
    except Exception as exc:
        client = _create_mlflow_client(mlflow_module)
        if client is None or not hasattr(client, "create_model_version"):
            raise
        if hasattr(client, "create_registered_model"):
            try:
                client.create_registered_model(
                    registered_model_name,
                    tags={"project": "Review Insights+", "registry_alias": "candidate"},
                    description="Review Insights+ retraining candidates.",
                )
            except Exception:
                pass
        model_info = client.create_model_version(
            name=registered_model_name,
            source=f"runs:/{run_id}/model",
            run_id=run_id,
            tags={"registry_method": "logged_artifacts_fallback"},
        )
        return (
            _extract_registered_model_version(model_info),
            f"pyfunc registration failed; registered logged artifacts instead ({type(exc).__name__}).",
        )


def _log_with_mlflow_client(
    mlflow_module: object,
    *,
    tracking_uri: str,
    experiment_name: str,
    report: Dict,
    run_name: str,
    artifact_paths: Iterable[Path] | None,
    model_dir: Path | None,
) -> MLflowRunResult:
    summary = report.get("summary", {})
    mlflow_module.set_tracking_uri(tracking_uri)
    mlflow_module.set_experiment(experiment_name)
    with mlflow_module.start_run(run_name=run_name) as active_run:
        mlflow_module.log_params(
            {
                "backend_name": summary.get("backend_name", "unknown"),
                "dataset": "default_reviews",
                **_model_params(model_dir),
            }
        )
        for metric_name, metric_value in _numeric_metrics(summary).items():
            mlflow_module.log_metric(metric_name, metric_value)

        artifact_count = 0
        for artifact_path in artifact_paths or []:
            resolved_path = Path(artifact_path)
            if resolved_path.exists() and resolved_path.is_file():
                mlflow_module.log_artifact(str(resolved_path))
                artifact_count += 1

        model_logged = False
        if model_dir is not None:
            mlflow_module.log_artifacts(str(model_dir), artifact_path="model")
            artifact_count += _count_files(model_dir)
            model_logged = True

        return MLflowRunResult(
            status="logged",
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            run_id=active_run.info.run_id,
            model_logged=model_logged,
            artifact_count=artifact_count,
        )


def _log_training_with_mlflow_client(
    mlflow_module: object,
    *,
    tracking_uri: str,
    experiment_name: str,
    summary: Dict,
    run_name: str,
    model_dir: Path,
    register_model: bool,
    registered_model_name: str,
    model_alias: str,
) -> MLflowRunResult:
    mlflow_module.set_tracking_uri(tracking_uri)
    mlflow_module.set_experiment(experiment_name)
    with mlflow_module.start_run(run_name=run_name) as active_run:
        run_id = active_run.info.run_id
        params = {
            "backend_name": summary.get("backend_name", "project_models_v1"),
            "dataset": summary.get("training_dataset", "unknown"),
            "threshold": str(summary.get("threshold", "unknown")),
            "model_alias": model_alias,
            **_model_params(model_dir),
        }
        mlflow_module.log_params(params)
        if hasattr(mlflow_module, "set_tags"):
            mlflow_module.set_tags(
                {
                    "pipeline": "training",
                    "model_alias": model_alias,
                    "training_dataset": str(summary.get("training_dataset", "unknown")),
                }
            )

        for metric_name, metric_value in _numeric_metrics(summary).items():
            mlflow_module.log_metric(metric_name, metric_value)

        mlflow_module.log_artifacts(str(model_dir), artifact_path="model")
        artifact_count = _count_files(model_dir)

        registered_model_version = None
        registry_reason = None
        if register_model:
            client = _create_mlflow_client(mlflow_module)
            try:
                registered_model_version, registry_reason = _register_training_model(
                    mlflow_module,
                    model_dir=model_dir,
                    registered_model_name=registered_model_name,
                    run_id=run_id,
                )
                if registered_model_version is None:
                    registered_model_version = _find_registered_model_version(
                        client,
                        registered_model_name=registered_model_name,
                        run_id=run_id,
                    )
                _tag_registered_model_version(
                    client,
                    registered_model_name=registered_model_name,
                    registered_model_version=registered_model_version,
                    model_alias=model_alias,
                    summary=summary,
                )
            except Exception as exc:
                registry_reason = f"model registry registration failed ({type(exc).__name__})."

        return MLflowRunResult(
            status="logged",
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            run_id=run_id,
            model_logged=True,
            artifact_count=artifact_count,
            registered_model_name=registered_model_name if register_model else None,
            registered_model_version=registered_model_version,
            model_alias=model_alias if register_model else None,
            reason=registry_reason,
        )


def log_evaluation_run(
    report: Dict,
    *,
    settings: Settings | None = None,
    artifact_paths: Iterable[Path] | None = None,
    model_artifact_dir: Path | str | None = None,
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

    model_dir = _complete_model_artifact_dir(resolved_settings, model_artifact_dir)

    _configure_mlflow_console_output()
    try:
        import mlflow
    except ImportError:
        if tracking_uri.startswith(("http://", "https://")):
            return _log_evaluation_run_http(
                tracking_uri=tracking_uri,
                experiment_name=experiment_name,
                report=report,
                run_name=run_name,
                model_dir=model_dir,
            )
        return MLflowRunResult(
            status="skipped",
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            reason="mlflow package is not installed.",
        )

    return _log_with_mlflow_client(
        mlflow,
        tracking_uri=tracking_uri,
        experiment_name=experiment_name,
        report=report,
        run_name=run_name,
        artifact_paths=artifact_paths,
        model_dir=model_dir,
    )


def log_training_run(
    summary: Dict,
    *,
    model_artifact_dir: Path | str,
    settings: Settings | None = None,
    run_name: str = "model_retraining",
    register_model: bool = False,
    registered_model_name: str = "review-insights-project-models",
    model_alias: str = "candidate",
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

    model_dir = _complete_model_artifact_dir(resolved_settings, model_artifact_dir)
    if model_dir is None:
        return MLflowRunResult(
            status="skipped",
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            reason="Complete model artifacts were not found.",
        )

    _configure_mlflow_console_output()
    try:
        import mlflow
    except ImportError:
        return MLflowRunResult(
            status="skipped",
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            reason="mlflow package is not installed.",
        )

    return _log_training_with_mlflow_client(
        mlflow,
        tracking_uri=tracking_uri,
        experiment_name=experiment_name,
        summary=summary,
        run_name=run_name,
        model_dir=model_dir,
        register_model=register_model,
        registered_model_name=registered_model_name,
        model_alias=model_alias,
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
    model_dir: Path | None = None,
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
                    *[
                        {"key": key, "value": value}
                        for key, value in _model_params(model_dir).items()
                    ],
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
            model_logged=False,
            artifact_count=0,
            reason="Install the mlflow package in this runtime to upload model artifacts through the MLflow client.",
        )
    except Exception as exc:
        return MLflowRunResult(
            status="skipped",
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            reason=f"MLflow HTTP logging failed: {exc}",
        )
