from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any


MODEL_METRICS = (
    "sentiment_accuracy",
    "sentiment_macro_f1",
    "theme_exact_match",
    "theme_precision_macro",
    "theme_recall_macro",
    "theme_f1_macro",
    "human_review_rate",
)


def _push(registry: Any, *, gateway_url: str | None, job: str) -> bool:
    if not gateway_url:
        return False
    from prometheus_client import push_to_gateway

    push_to_gateway(gateway_url, job=job, registry=registry, timeout=5)
    return True


def push_ingestion_metrics(
    ingestion: Mapping[str, Any],
    *,
    gateway_url: str | None,
) -> bool:
    from prometheus_client import CollectorRegistry, Gauge

    registry = CollectorRegistry()
    rows = Gauge(
        "review_insights_data_rows",
        "Rows handled by the latest dataset ingestion.",
        ["status"],
        registry=registry,
    )
    rows.labels("ingested").set(float(ingestion.get("rows_ingested", 0)))
    rows.labels("valid").set(float(ingestion.get("rows_valid", 0)))
    rows.labels("rejected").set(float(ingestion.get("rows_rejected", 0)))
    rows.labels("annotation_queue").set(float(ingestion.get("annotation_rows", 0)))

    quality = Gauge(
        "review_insights_data_quality_ready",
        "Whether the latest dataset passed all quality gates.",
        registry=registry,
    )
    quality.set(1 if ingestion.get("quality_status") == "ready" else 0)

    check = Gauge(
        "review_insights_data_quality_check",
        "Status of each quality gate for the latest dataset.",
        ["check"],
        registry=registry,
    )
    failed = set(ingestion.get("quality_failed_checks", []))
    for name in sorted(failed):
        check.labels(str(name)).set(0)

    timestamp = Gauge(
        "review_insights_data_last_ingestion_timestamp_seconds",
        "Unix timestamp of the latest successful ingestion execution.",
        registry=registry,
    )
    timestamp.set(time.time())
    return _push(registry, gateway_url=gateway_url, job="review_insights_data_pipeline")


def push_training_metrics(
    summary: Mapping[str, Any],
    *,
    gateway_url: str | None,
) -> bool:
    from prometheus_client import CollectorRegistry, Gauge

    registry = CollectorRegistry()
    metric = Gauge(
        "review_insights_model_metric",
        "Latest candidate model evaluation metric.",
        ["metric"],
        registry=registry,
    )
    for name in MODEL_METRICS:
        value = summary.get(name)
        if isinstance(value, (int, float)):
            metric.labels(name).set(float(value))

    training_rows = Gauge(
        "review_insights_model_training_rows",
        "Rows used by the latest model training run.",
        registry=registry,
    )
    training_rows.set(float(summary.get("training_rows", 0)))

    timestamp = Gauge(
        "review_insights_model_last_training_timestamp_seconds",
        "Unix timestamp of the latest model training run.",
        registry=registry,
    )
    timestamp.set(time.time())
    return _push(registry, gateway_url=gateway_url, job="review_insights_model_pipeline")


def push_release_metrics(
    release: Mapping[str, Any],
    *,
    gateway_url: str | None,
) -> bool:
    from prometheus_client import CollectorRegistry, Gauge

    registry = CollectorRegistry()
    status = str(release.get("status", "unknown"))
    approved = Gauge(
        "review_insights_model_release_approved",
        "Whether the latest candidate passed the release gates.",
        registry=registry,
    )
    approved.set(
        1
        if status in {"approved", "approved_dry_run", "promoted", "already_champion"}
        else 0
    )
    timestamp = Gauge(
        "review_insights_model_last_release_check_timestamp_seconds",
        "Unix timestamp of the latest model release decision.",
        registry=registry,
    )
    timestamp.set(time.time())
    return _push(registry, gateway_url=gateway_url, job="review_insights_release_pipeline")
