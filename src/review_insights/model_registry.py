from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model_backend import ARTIFACT_FILENAMES, load_project_model_artifacts


DEFAULT_PROMOTION_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "model_promotion_policy_v1.json"
)


@dataclass(frozen=True)
class PromotionPolicy:
    policy_version: str
    registered_model_name: str
    candidate_alias: str
    champion_alias: str
    previous_champion_alias: str
    required_metrics: dict[str, float]
    max_metric_regression: dict[str, float]
    maximum_metrics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RegistryActionResult:
    action: str
    status: str
    registered_model_name: str
    policy_version: str
    candidate_version: str | None
    champion_version: str | None
    previous_champion_version: str | None
    failed_checks: list[str]
    report_path: str | None
    deployed_model_dir: str | None
    created_at: str


def load_promotion_policy(path: Path | None = None) -> PromotionPolicy:
    policy_path = path or DEFAULT_PROMOTION_POLICY_PATH
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    return PromotionPolicy(
        policy_version=str(payload["policy_version"]),
        registered_model_name=str(payload["registered_model_name"]),
        candidate_alias=str(payload["candidate_alias"]),
        champion_alias=str(payload["champion_alias"]),
        previous_champion_alias=str(payload["previous_champion_alias"]),
        required_metrics={
            str(name): float(value)
            for name, value in payload["required_metrics"].items()
        },
        max_metric_regression={
            str(name): float(value)
            for name, value in payload["max_metric_regression"].items()
        },
        maximum_metrics={
            str(name): float(value)
            for name, value in payload.get("maximum_metrics", {}).items()
        },
    )


def evaluate_promotion_gates(
    candidate_metrics: dict[str, float],
    champion_metrics: dict[str, float] | None,
    policy: PromotionPolicy,
) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    for metric_name, threshold in policy.required_metrics.items():
        actual = candidate_metrics.get(metric_name)
        checks[f"minimum_{metric_name}"] = {
            "passed": actual is not None and float(actual) >= threshold,
            "actual": actual,
            "operator": ">=",
            "threshold": threshold,
        }

    for metric_name, threshold in policy.maximum_metrics.items():
        actual = candidate_metrics.get(metric_name)
        checks[f"maximum_{metric_name}"] = {
            "passed": actual is not None and float(actual) <= threshold,
            "actual": actual,
            "operator": "<=",
            "threshold": threshold,
        }

    if champion_metrics is not None:
        for metric_name, max_regression in policy.max_metric_regression.items():
            candidate_value = candidate_metrics.get(metric_name)
            champion_value = champion_metrics.get(metric_name)
            passed = (
                candidate_value is not None
                and champion_value is not None
                and float(candidate_value) >= float(champion_value) - max_regression
            )
            checks[f"max_regression_{metric_name}"] = {
                "passed": passed,
                "candidate": candidate_value,
                "champion": champion_value,
                "operator": ">=",
                "threshold": (
                    float(champion_value) - max_regression
                    if champion_value is not None
                    else None
                ),
                "max_regression": max_regression,
            }

    failed_checks = sorted(name for name, check in checks.items() if not check["passed"])
    return {
        "status": "approved" if not failed_checks else "rejected",
        "failed_checks": failed_checks,
        "checks": checks,
        "candidate_metrics": candidate_metrics,
        "champion_metrics": champion_metrics,
        "bootstrap_promotion": champion_metrics is None,
    }


def _safe_model_version_by_alias(client: object, model_name: str, alias: str) -> object | None:
    try:
        return client.get_model_version_by_alias(model_name, alias)
    except Exception:
        return None


def _get_model_version(client: object, model_name: str, version: str | None, alias: str) -> object:
    if version is not None:
        return client.get_model_version(model_name, str(version))
    resolved = _safe_model_version_by_alias(client, model_name, alias)
    if resolved is None:
        raise ValueError(f"Model alias '{alias}' was not found for '{model_name}'.")
    return resolved


def _run_metrics(client: object, model_version: object) -> dict[str, float]:
    run_id = str(getattr(model_version, "run_id", "") or "")
    if not run_id:
        raise ValueError("Registered model version is not linked to an MLflow run.")
    run = client.get_run(run_id)
    metrics = getattr(getattr(run, "data", None), "metrics", {})
    return {
        str(name): float(value)
        for name, value in dict(metrics).items()
        if isinstance(value, (int, float))
    }


def _set_version_tags(client: object, model_name: str, version: str, tags: dict[str, str]) -> None:
    for key, value in tags.items():
        client.set_model_version_tag(model_name, version, key, value)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def _default_report_path(action: str, reports_root: Path | None = None) -> Path:
    root = reports_root or Path("reports") / "model_registry"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return root / f"{action}_{timestamp}.json"


def _artifact_source_dir(client: object, run_id: str, download_root: Path) -> Path:
    downloaded = Path(client.download_artifacts(run_id, "model", str(download_root)))
    missing = [filename for filename in ARTIFACT_FILENAMES if not (downloaded / filename).exists()]
    if missing:
        raise ValueError(f"Downloaded MLflow model artifacts are incomplete: {', '.join(missing)}")
    load_project_model_artifacts(str(downloaded), source="local")
    return downloaded


def deploy_run_model_artifacts(client: object, run_id: str, target_dir: Path) -> Path:
    target_dir = target_dir.resolve()
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = target_dir.parent / f".{target_dir.name}.staging-{uuid.uuid4().hex}"
    backup_dir = target_dir.parent / f".{target_dir.name}.backup-{uuid.uuid4().hex}"

    with tempfile.TemporaryDirectory(prefix="review-insights-mlflow-") as temporary:
        source_dir = _artifact_source_dir(client, run_id, Path(temporary))
        shutil.copytree(source_dir, staging_dir)

    try:
        if target_dir.exists():
            target_dir.replace(backup_dir)
        staging_dir.replace(target_dir)
    except Exception:
        if target_dir.exists() and backup_dir.exists():
            shutil.rmtree(target_dir)
        if backup_dir.exists():
            backup_dir.replace(target_dir)
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        raise
    if backup_dir.exists():
        try:
            shutil.rmtree(backup_dir)
        except OSError:
            # The deployment already committed successfully. On bind-mounted
            # Windows filesystems directory cleanup can lag; keep the recoverable
            # backup instead of rolling back a valid model swap.
            pass
    return target_dir


def promote_candidate(
    client: object,
    *,
    policy: PromotionPolicy,
    registered_model_name: str | None = None,
    candidate_version: str | None = None,
    report_path: Path | None = None,
    deploy_model_dir: Path | None = None,
    dry_run: bool = False,
) -> RegistryActionResult:
    model_name = registered_model_name or policy.registered_model_name
    candidate = _get_model_version(client, model_name, candidate_version, policy.candidate_alias)
    candidate_version_value = str(getattr(candidate, "version"))
    candidate_metrics = _run_metrics(client, candidate)

    champion = _safe_model_version_by_alias(client, model_name, policy.champion_alias)
    champion_version_value = str(getattr(champion, "version")) if champion is not None else None
    champion_metrics = _run_metrics(client, champion) if champion is not None else None
    gate_report = evaluate_promotion_gates(candidate_metrics, champion_metrics, policy)
    created_at = datetime.now(timezone.utc).isoformat()
    resolved_report_path = report_path or _default_report_path("promotion")
    status = str(gate_report["status"])
    deployed_model_dir: str | None = None

    if status == "approved" and champion_version_value == candidate_version_value:
        status = "already_champion"
    elif status == "approved" and dry_run:
        status = "approved_dry_run"
    elif status == "approved":
        previous_alias_version = champion_version_value
        try:
            if champion_version_value is not None:
                client.set_registered_model_alias(
                    model_name,
                    policy.previous_champion_alias,
                    champion_version_value,
                )
                _set_version_tags(
                    client,
                    model_name,
                    champion_version_value,
                    {
                        "lifecycle_status": "previous_champion",
                        "superseded_at": created_at,
                    },
                )
            client.set_registered_model_alias(
                model_name,
                policy.champion_alias,
                candidate_version_value,
            )
            _set_version_tags(
                client,
                model_name,
                candidate_version_value,
                {
                    "lifecycle_status": "champion",
                    "promotion_status": "promoted",
                    "promotion_policy_version": policy.policy_version,
                    "promoted_at": created_at,
                },
            )
            client.set_registered_model_tag(model_name, "champion_version", candidate_version_value)
            client.set_registered_model_tag(model_name, "promotion_policy_version", policy.policy_version)
            if deploy_model_dir is not None:
                deployed = deploy_run_model_artifacts(
                    client,
                    str(getattr(candidate, "run_id")),
                    deploy_model_dir,
                )
                deployed_model_dir = str(deployed)
            status = "promoted"
        except Exception:
            if previous_alias_version is not None:
                client.set_registered_model_alias(
                    model_name,
                    policy.champion_alias,
                    previous_alias_version,
                )
                _set_version_tags(
                    client,
                    model_name,
                    previous_alias_version,
                    {"lifecycle_status": "champion"},
                )
            elif hasattr(client, "delete_registered_model_alias"):
                client.delete_registered_model_alias(model_name, policy.champion_alias)
            _set_version_tags(
                client,
                model_name,
                candidate_version_value,
                {
                    "lifecycle_status": "candidate",
                    "promotion_status": "deployment_failed",
                },
            )
            raise
    elif not dry_run:
        _set_version_tags(
            client,
            model_name,
            candidate_version_value,
            {
                "promotion_status": "rejected",
                "promotion_policy_version": policy.policy_version,
                "promotion_failed_checks": ",".join(gate_report["failed_checks"]),
                "promotion_evaluated_at": created_at,
            },
        )

    payload = {
        "action": "promotion",
        "status": status,
        "registered_model_name": model_name,
        "policy": asdict(policy),
        "candidate_version": candidate_version_value,
        "champion_version_before": champion_version_value,
        "champion_version_after": (
            candidate_version_value if status in {"promoted", "already_champion"} else champion_version_value
        ),
        "deployed_model_dir": deployed_model_dir,
        "dry_run": dry_run,
        "gate_report": gate_report,
        "created_at": created_at,
    }
    _write_json_atomic(resolved_report_path, payload)
    return RegistryActionResult(
        action="promotion",
        status=status,
        registered_model_name=model_name,
        policy_version=policy.policy_version,
        candidate_version=candidate_version_value,
        champion_version=payload["champion_version_after"],
        previous_champion_version=champion_version_value,
        failed_checks=list(gate_report["failed_checks"]),
        report_path=str(resolved_report_path),
        deployed_model_dir=deployed_model_dir,
        created_at=created_at,
    )


def rollback_champion(
    client: object,
    *,
    policy: PromotionPolicy,
    registered_model_name: str | None = None,
    report_path: Path | None = None,
    deploy_model_dir: Path | None = None,
    dry_run: bool = False,
) -> RegistryActionResult:
    model_name = registered_model_name or policy.registered_model_name
    champion = _safe_model_version_by_alias(client, model_name, policy.champion_alias)
    previous = _safe_model_version_by_alias(client, model_name, policy.previous_champion_alias)
    if champion is None or previous is None:
        raise ValueError("Rollback requires both champion and previous_champion aliases.")

    champion_version_value = str(getattr(champion, "version"))
    previous_version_value = str(getattr(previous, "version"))
    created_at = datetime.now(timezone.utc).isoformat()
    resolved_report_path = report_path or _default_report_path("rollback")
    deployed_model_dir: str | None = None
    status = "approved_dry_run" if dry_run else "rolled_back"

    if not dry_run:
        client.set_registered_model_alias(model_name, policy.champion_alias, previous_version_value)
        try:
            if deploy_model_dir is not None:
                deployed = deploy_run_model_artifacts(
                    client,
                    str(getattr(previous, "run_id")),
                    deploy_model_dir,
                )
                deployed_model_dir = str(deployed)
        except Exception:
            client.set_registered_model_alias(model_name, policy.champion_alias, champion_version_value)
            raise
        client.set_registered_model_alias(
            model_name,
            policy.previous_champion_alias,
            champion_version_value,
        )
        _set_version_tags(
            client,
            model_name,
            previous_version_value,
            {
                "lifecycle_status": "champion",
                "rollback_promoted_at": created_at,
            },
        )
        _set_version_tags(
            client,
            model_name,
            champion_version_value,
            {
                "lifecycle_status": "previous_champion",
                "rolled_back_at": created_at,
            },
        )
        client.set_registered_model_tag(model_name, "champion_version", previous_version_value)

    payload = {
        "action": "rollback",
        "status": status,
        "registered_model_name": model_name,
        "policy_version": policy.policy_version,
        "champion_version_before": champion_version_value,
        "champion_version_after": previous_version_value,
        "previous_champion_version_after": champion_version_value,
        "deployed_model_dir": deployed_model_dir,
        "dry_run": dry_run,
        "created_at": created_at,
    }
    _write_json_atomic(resolved_report_path, payload)
    return RegistryActionResult(
        action="rollback",
        status=status,
        registered_model_name=model_name,
        policy_version=policy.policy_version,
        candidate_version=None,
        champion_version=previous_version_value,
        previous_champion_version=champion_version_value,
        failed_checks=[],
        report_path=str(resolved_report_path),
        deployed_model_dir=deployed_model_dir,
        created_at=created_at,
    )
