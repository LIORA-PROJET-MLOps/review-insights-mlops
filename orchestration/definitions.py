import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import dagster as dg

from orchestration.alerts import send_webhook
from orchestration.control_metrics import (
    push_drift_metrics,
    push_ingestion_metrics,
    push_release_metrics,
    push_training_metrics,
)
from pipelines.train_models import build_training_artifacts
from src.review_insights.data_store import ingest_csv_dataset, latest_ready_validated_dataset
from src.review_insights.drift import (
    DEFAULT_DRIFT_POLICY_PATH,
    evaluate_drift,
    inspect_labeled_candidate_csv,
    load_drift_policy,
)
from src.review_insights.mlflow_tracking import log_training_run
from src.review_insights.model_registry import load_promotion_policy, promote_candidate
from src.review_insights.release import build_model_release_report
from src.review_insights.settings import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_CSV = os.getenv(
    "ORCHESTRATOR_DEFAULT_SOURCE_CSV",
    str(PROJECT_ROOT / "data" / "sample" / "reviews_poc_test.csv"),
)
DEFAULT_DATA_ROOT = os.getenv("ORCHESTRATOR_DATA_ROOT", str(PROJECT_ROOT / "data_store"))
DEFAULT_OUTPUT_ROOT = os.getenv(
    "ORCHESTRATOR_MODEL_OUTPUT_ROOT",
    str(PROJECT_ROOT / "artifacts" / "orchestrated_models"),
)
DEFAULT_REPORT_ROOT = os.getenv(
    "ORCHESTRATOR_REPORT_ROOT",
    str(PROJECT_ROOT / "reports" / "orchestration"),
)
DEFAULT_PREDICTION_EVENT_STORE = os.getenv(
    "PREDICTION_EVENT_STORE_PATH",
    str(PROJECT_ROOT / "predictions" / "prediction_events.jsonl"),
)
DEFAULT_FEEDBACK_STORE = os.getenv(
    "FEEDBACK_STORE_PATH",
    str(PROJECT_ROOT / "feedback" / "human_feedback.jsonl"),
)
DEFAULT_DRIFT_POLICY = os.getenv(
    "DRIFT_POLICY_PATH",
    str(DEFAULT_DRIFT_POLICY_PATH),
)
DEFAULT_DRIFT_REPORT = os.getenv(
    "DRIFT_REPORT_PATH",
    str(PROJECT_ROOT / "reports" / "drift" / "latest_drift_report.json"),
)


def _pushgateway_url() -> str | None:
    return os.getenv("PUSHGATEWAY_URL") or None


def _push_safely(context: dg.AssetExecutionContext, callback: Any, payload: dict) -> None:
    try:
        callback(payload, gateway_url=_pushgateway_url())
    except Exception as exc:
        context.log.warning("Control metric publication failed: %s", exc)


@dg.asset(
    group_name="data_pipeline",
    description="Versioned, validated review dataset and its quality report.",
    config_schema={
        "source_csv": dg.Field(dg.StringSource, default_value=DEFAULT_SOURCE_CSV),
        "data_root": dg.Field(dg.StringSource, default_value=DEFAULT_DATA_ROOT),
        "dataset_version": dg.Field(str, is_required=False),
        "quality_policy_path": dg.Field(str, is_required=False),
    },
)
def ingested_review_dataset(context: dg.AssetExecutionContext) -> dict[str, Any]:
    config = context.op_execution_context.op_config
    result = ingest_csv_dataset(
        source_path=Path(config["source_csv"]),
        data_root=Path(config["data_root"]),
        dataset_version=config.get("dataset_version"),
        quality_policy_path=(
            Path(config["quality_policy_path"])
            if config.get("quality_policy_path")
            else None
        ),
        enforce_quality_gates=False,
    )
    payload = asdict(result)
    context.add_output_metadata(
        {
            "dataset_version": result.dataset_version,
            "rows_ingested": result.rows_ingested,
            "rows_valid": result.rows_valid,
            "rows_rejected": result.rows_rejected,
            "quality_status": result.quality_status,
            "manifest": dg.MetadataValue.path(result.manifest_path),
        }
    )
    _push_safely(context, push_ingestion_metrics, payload)
    return payload


@dg.asset_check(
    asset=ingested_review_dataset,
    description="Expose the existing data quality policy as a Dagster asset check.",
)
def dataset_quality_gates(ingested_review_dataset: dict[str, Any]) -> dg.AssetCheckResult:
    failed = list(ingested_review_dataset.get("quality_failed_checks", []))
    return dg.AssetCheckResult(
        passed=ingested_review_dataset.get("quality_status") == "ready",
        severity=dg.AssetCheckSeverity.ERROR,
        metadata={
            "failed_checks": dg.MetadataValue.json(failed),
            "quality_report": dg.MetadataValue.path(
                str(ingested_review_dataset["quality_report_path"])
            ),
        },
    )


@dg.asset(
    group_name="data_pipeline",
    description="Annotation queue produced during ingestion for missing theme sentiment labels.",
)
def annotation_queue(ingested_review_dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_version": ingested_review_dataset["dataset_version"],
        "path": ingested_review_dataset["annotation_queue_path"],
        "rows": ingested_review_dataset["annotation_rows"],
    }


@dg.asset(
    group_name="model_pipeline",
    description="Trained project artifacts, independently evaluated and registered as MLflow candidate.",
    config_schema={
        "threshold": dg.Field(float, default_value=0.5),
        "output_root": dg.Field(dg.StringSource, default_value=DEFAULT_OUTPUT_ROOT),
        "registered_model_name": dg.Field(
            str,
            default_value="review-insights-project-models",
        ),
    },
)
def trained_candidate_model(
    context: dg.AssetExecutionContext,
    ingested_review_dataset: dict[str, Any],
) -> dict[str, Any]:
    if ingested_review_dataset.get("quality_status") != "ready":
        failed = ", ".join(ingested_review_dataset.get("quality_failed_checks", []))
        raise dg.Failure(
            description=f"Dataset quality gates rejected training: {failed}",
            metadata={"dataset_version": ingested_review_dataset["dataset_version"]},
        )

    config = context.op_execution_context.op_config
    version = str(ingested_review_dataset["dataset_version"])
    output_dir = Path(config["output_root"]) / version
    training_path = Path(
        ingested_review_dataset.get("train_parquet_path")
        or ingested_review_dataset["validated_parquet_path"]
    )
    validation_path = ingested_review_dataset.get("validation_parquet_path")
    evaluation_path = ingested_review_dataset.get("test_parquet_path")
    summary = build_training_artifacts(
        output_dir,
        threshold=float(config["threshold"]),
        dataset_path=training_path,
        validation_dataset_path=Path(validation_path) if validation_path else None,
        evaluation_dataset_path=Path(evaluation_path) if evaluation_path else None,
    )
    mlflow_result = log_training_run(
        summary,
        model_artifact_dir=output_dir,
        register_model=True,
        registered_model_name=str(config["registered_model_name"]),
        model_alias="candidate",
    )
    summary["mlflow"] = asdict(mlflow_result)
    context.add_output_metadata(
        {
            "dataset_version": version,
            "model_dir": dg.MetadataValue.path(str(output_dir)),
            "evaluation_status": str(summary.get("evaluation_status", "unknown")),
            "mlflow_run_id": str(mlflow_result.run_id or "not_logged"),
            "registered_model_version": str(
                mlflow_result.registered_model_version or "not_registered"
            ),
        }
    )
    _push_safely(context, push_training_metrics, summary)
    return summary


@dg.asset(
    group_name="model_pipeline",
    description="Versioned release gate report for the latest trained candidate.",
    config_schema={
        "report_root": dg.Field(dg.StringSource, default_value=DEFAULT_REPORT_ROOT),
    },
)
def model_release_report(
    context: dg.AssetExecutionContext,
    trained_candidate_model: dict[str, Any],
) -> dict[str, Any]:
    report_root = Path(context.op_execution_context.op_config["report_root"])
    report_root.mkdir(parents=True, exist_ok=True)
    version = Path(str(trained_candidate_model["output_dir"])).name
    evaluation_path = report_root / f"candidate_evaluation_{version}.json"
    evaluation_path.write_text(
        json.dumps({"summary": trained_candidate_model}, indent=2),
        encoding="utf-8",
    )
    output_json = report_root / f"model_release_{version}.json"
    output_markdown = report_root / f"model_release_{version}.md"
    release = build_model_release_report(
        evaluation_report_path=evaluation_path,
        model_manifest_path=Path(str(trained_candidate_model["manifest_path"])),
        output_json_path=output_json,
        output_markdown_path=output_markdown,
    ).to_dict()
    context.add_output_metadata(
        {
            "status": release["status"],
            "release_report": dg.MetadataValue.path(str(output_json)),
            "failed_checks": dg.MetadataValue.json(
                release["gate_report"].get("failed_checks", [])
            ),
        }
    )
    _push_safely(context, push_release_metrics, release)
    return release


@dg.op(
    config_schema={
        "dry_run": dg.Field(bool, default_value=True),
        "deploy_model_dir": dg.Field(str, is_required=False),
    }
)
def promote_candidate_op(context: dg.OpExecutionContext) -> dict[str, Any]:
    try:
        import mlflow
        from mlflow import MlflowClient
    except ImportError as exc:
        raise dg.Failure("The mlflow package is required for promotion.") from exc

    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    result = promote_candidate(
        MlflowClient(tracking_uri=settings.mlflow_tracking_uri),
        policy=load_promotion_policy(),
        deploy_model_dir=(
            Path(context.op_config["deploy_model_dir"])
            if context.op_config.get("deploy_model_dir")
            else None
        ),
        dry_run=bool(context.op_config["dry_run"]),
    )
    payload = asdict(result)
    try:
        push_release_metrics(payload, gateway_url=_pushgateway_url())
    except Exception as exc:
        context.log.warning("Control metric publication failed: %s", exc)
    return payload


@dg.job(description="Explicit promotion job; dry-run by default for production safety.")
def model_promotion_job() -> None:
    promote_candidate_op()


data_pipeline_job = dg.define_asset_job(
    "data_pipeline_job",
    selection=dg.AssetSelection.assets(ingested_review_dataset, annotation_queue),
    description="Ingest, validate, version and prepare annotation work.",
)

model_training_job = dg.define_asset_job(
    "model_training_job",
    selection=dg.AssetSelection.assets(
        ingested_review_dataset,
        annotation_queue,
        trained_candidate_model,
        model_release_report,
    ),
    description="Full data-to-candidate workflow with MLflow registration and release gates.",
)


@dg.op(
    description="Evaluate production prediction drift against the latest ready dataset.",
    config_schema={
        "event_store_path": dg.Field(
            dg.StringSource,
            default_value=DEFAULT_PREDICTION_EVENT_STORE,
        ),
        "feedback_store_path": dg.Field(
            dg.StringSource,
            default_value=DEFAULT_FEEDBACK_STORE,
        ),
        "data_root": dg.Field(dg.StringSource, default_value=DEFAULT_DATA_ROOT),
        "policy_path": dg.Field(dg.StringSource, default_value=DEFAULT_DRIFT_POLICY),
        "output_path": dg.Field(dg.StringSource, default_value=DEFAULT_DRIFT_REPORT),
    },
)
def evaluate_production_drift_op(context: dg.OpExecutionContext) -> dict[str, Any]:
    config = context.op_config
    report = evaluate_drift(
        event_store_path=Path(config["event_store_path"]),
        feedback_store_path=Path(config["feedback_store_path"]),
        data_root=Path(config["data_root"]),
        policy_path=Path(config["policy_path"]),
        output_path=Path(config["output_path"]),
    )
    try:
        push_drift_metrics(report, gateway_url=_pushgateway_url())
    except Exception as exc:
        context.log.warning("Control metric publication failed: %s", exc)
    context.add_output_metadata(
        {
            "status": str(report["status"]),
            "recommendation": str(report["recommendation"]),
            "prediction_events": int(report["window"]["prediction_events"]),
            "triggers": dg.MetadataValue.json(report.get("triggers", [])),
            "report": dg.MetadataValue.path(str(config["output_path"])),
        }
    )
    return report


@dg.job(description="Hourly production drift evaluation and retraining recommendation.")
def drift_monitoring_job() -> None:
    evaluate_production_drift_op()

def _file_run_key(path: Path) -> str:
    stat = path.stat()
    value = f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _incoming_dir() -> Path:
    return Path(
        os.getenv(
            "ORCHESTRATOR_INCOMING_DIR",
            str(Path(DEFAULT_DATA_ROOT) / "raw" / "incoming"),
        )
    )


def _latest_incoming_csv() -> Path | None:
    incoming_dir = _incoming_dir()
    candidates = list(incoming_dir.glob("*.csv")) if incoming_dir.exists() else []
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))


def _source_already_ingested(source_path: Path, data_root: Path) -> bool:
    registry_path = data_root / "registry" / "datasets_manifest.json"
    if not registry_path.is_file():
        return False
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    return any(
        entry.get("source_sha256") == digest for entry in registry.get("datasets", [])
    )


@dg.schedule(
    job=model_training_job,
    cron_schedule="0 19 * * *",
    execution_timezone="Europe/Paris",
    default_status=dg.DefaultScheduleStatus.RUNNING,
    description="Daily full data-to-candidate pipeline using the latest incoming CSV.",
)
def daily_full_pipeline_schedule(
    context: dg.ScheduleEvaluationContext,
) -> dg.RunRequest | dg.SkipReason:
    source_path = _latest_incoming_csv()
    if source_path is None:
        return dg.SkipReason(f"No CSV file found in {_incoming_dir()}")
    data_root = Path(os.getenv("ORCHESTRATOR_DATA_ROOT", DEFAULT_DATA_ROOT))
    if _source_already_ingested(source_path, data_root):
        return dg.SkipReason(f"Latest CSV {source_path.name} was already ingested")

    scheduled_at = context.scheduled_execution_time
    tick_key = scheduled_at.isoformat() if scheduled_at else "manual"
    return dg.RunRequest(
        run_key=f"daily-full-pipeline:{tick_key}:{_file_run_key(source_path)}",
        run_config={
            "ops": {
                "ingested_review_dataset": {
                    "config": {
                        "source_csv": str(source_path),
                        "data_root": str(data_root),
                    }
                }
            }
        },
        tags={
            "source_csv": source_path.name,
            "trigger": "daily_full_pipeline_schedule",
        },
    )


@dg.schedule(
    job=drift_monitoring_job,
    cron_schedule="15 * * * *",
    execution_timezone="Europe/Paris",
    default_status=dg.DefaultScheduleStatus.RUNNING,
    description="Evaluate production drift every hour at minute 15.",
)
def hourly_drift_monitoring_schedule() -> dg.RunRequest:
    return dg.RunRequest(tags={"trigger": "hourly_drift_monitoring_schedule"})


@dg.sensor(job=data_pipeline_job, minimum_interval_seconds=30)
def incoming_review_csv_sensor(context: dg.SensorEvaluationContext):
    incoming_dir = _incoming_dir()
    candidates = sorted(incoming_dir.glob("*.csv")) if incoming_dir.exists() else []
    if not candidates:
        yield dg.SkipReason(f"No CSV file found in {incoming_dir}")
        return
    for source_path in candidates:
        yield dg.RunRequest(
            run_key=_file_run_key(source_path),
            run_config={
                "ops": {
                    "ingested_review_dataset": {
                        "config": {
                            "source_csv": str(source_path),
                            "data_root": DEFAULT_DATA_ROOT,
                        }
                    }
                }
            },
            tags={"source_csv": source_path.name, "trigger": "incoming_csv_sensor"},
        )


@dg.sensor(
    job=model_training_job,
    minimum_interval_seconds=60,
    default_status=dg.DefaultSensorStatus.RUNNING,
    description="Start controlled retraining when drift and fresh labeled data are both ready.",
)
def drift_retraining_sensor(
    context: dg.SensorEvaluationContext,
) -> dg.RunRequest | dg.SkipReason:
    report_path = Path(os.getenv("DRIFT_REPORT_PATH", DEFAULT_DRIFT_REPORT))
    if not report_path.is_file():
        return dg.SkipReason(f"No drift report found at {report_path}")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return dg.SkipReason(f"Drift report is unreadable: {type(exc).__name__}")
    if not report.get("automatic_retraining_allowed"):
        return dg.SkipReason(
            f"Automatic retraining not allowed; recommendation={report.get('recommendation')}"
        )

    policy_path = Path(os.getenv("DRIFT_POLICY_PATH", DEFAULT_DRIFT_POLICY))
    try:
        policy = load_drift_policy(policy_path)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return dg.SkipReason(f"Drift policy is invalid: {type(exc).__name__}")
    if not policy.automatic_retraining_enabled:
        return dg.SkipReason("Automatic retraining is disabled by policy")

    source_path = _latest_incoming_csv()
    if source_path is None:
        return dg.SkipReason(f"No labeled CSV file found in {_incoming_dir()}")
    data_root = Path(os.getenv("ORCHESTRATOR_DATA_ROOT", DEFAULT_DATA_ROOT))
    if policy.require_new_labeled_csv and _source_already_ingested(source_path, data_root):
        return dg.SkipReason(f"Latest CSV {source_path.name} was already ingested")

    candidate = inspect_labeled_candidate_csv(
        source_path,
        minimum_rows=policy.minimum_retraining_rows,
        baseline_path=latest_ready_validated_dataset(data_root),
        minimum_changed_rows=policy.minimum_changed_labeled_rows,
    )
    if not candidate["ready"]:
        return dg.SkipReason(
            f"Latest CSV {source_path.name} is not retraining-ready: {candidate['reason']}"
        )

    source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    return dg.RunRequest(
        run_key=f"drift-retraining:{source_digest}",
        run_config={
            "ops": {
                "ingested_review_dataset": {
                    "config": {
                        "source_csv": str(source_path),
                        "data_root": str(data_root),
                    }
                }
            }
        },
        tags={
            "source_csv": source_path.name,
            "trigger": "drift_retraining_sensor",
            "drift_report_created_at": str(report.get("created_at", "unknown")),
            "drift_triggers": ",".join(map(str, report.get("triggers", []))),
        },
    )


@dg.run_failure_sensor(
    monitored_jobs=[
        data_pipeline_job,
        model_training_job,
        model_promotion_job,
        drift_monitoring_job,
    ],
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def pipeline_failure_alert(context: dg.RunFailureSensorContext) -> None:
    url = os.getenv("ALERT_WEBHOOK_URL") or None
    payload = {
        "event": "review_insights_pipeline_failure",
        "job_name": context.dagster_run.job_name,
        "run_id": context.dagster_run.run_id,
        "message": context.failure_event.message,
    }
    try:
        sent = send_webhook(url, payload)
        if not sent:
            context.log.warning("ALERT_WEBHOOK_URL is not configured; failure kept in Dagster UI.")
    except Exception as exc:
        context.log.error("Pipeline failure alert could not be sent: %s", exc)


defs = dg.Definitions(
    assets=[
        ingested_review_dataset,
        annotation_queue,
        trained_candidate_model,
        model_release_report,
    ],
    asset_checks=[dataset_quality_gates],
    jobs=[
        data_pipeline_job,
        model_training_job,
        model_promotion_job,
        drift_monitoring_job,
    ],
    schedules=[daily_full_pipeline_schedule, hourly_drift_monitoring_schedule],
    sensors=[incoming_review_csv_sensor, drift_retraining_sensor, pipeline_failure_alert],
)
