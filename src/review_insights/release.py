from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model_registry import DEFAULT_PROMOTION_POLICY_PATH, evaluate_promotion_gates, load_promotion_policy


@dataclass(frozen=True)
class ModelReleaseReport:
    status: str
    created_at: str
    evaluation_report_path: str
    promotion_policy_path: str
    model_manifest_path: str | None
    gate_report: dict[str, Any]
    model_manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}.")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _write_markdown(path: Path, report: ModelReleaseReport) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    gate_report = report.gate_report
    content = "\n".join(
        [
            "# Rapport release modele",
            "",
            f"- Date UTC: {report.created_at}",
            f"- Statut gates: `{gate_report.get('status', 'unknown')}`",
            f"- Evaluation: `{report.evaluation_report_path}`",
            f"- Policy: `{report.promotion_policy_path}`",
            f"- Manifest modele: `{report.model_manifest_path or 'non disponible'}`",
            "",
            "## Checks echoues",
            "",
            json.dumps(gate_report.get("failed_checks", []), indent=2, ensure_ascii=False),
            "",
            "## Candidate metrics",
            "",
            json.dumps(gate_report.get("candidate_metrics", {}), indent=2, ensure_ascii=False),
            "",
            "## Checks",
            "",
            json.dumps(gate_report.get("checks", {}), indent=2, ensure_ascii=False),
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
    return path


def build_model_release_report(
    *,
    evaluation_report_path: Path,
    promotion_policy_path: Path | None = None,
    model_manifest_path: Path | None = None,
    output_json_path: Path | None = None,
    output_markdown_path: Path | None = None,
) -> ModelReleaseReport:
    resolved_policy_path = promotion_policy_path or DEFAULT_PROMOTION_POLICY_PATH
    evaluation_report = _read_json(evaluation_report_path)
    summary = evaluation_report.get("summary", {})
    if not isinstance(summary, dict):
        raise ValueError("Evaluation report must contain a summary object.")

    policy = load_promotion_policy(resolved_policy_path)
    gate_report = evaluate_promotion_gates(
        {key: float(value) for key, value in summary.items() if isinstance(value, (int, float))},
        champion_metrics=None,
        policy=policy,
    )

    model_manifest: dict[str, Any] = {}
    if model_manifest_path is not None and model_manifest_path.exists():
        model_manifest = _read_json(model_manifest_path)

    report = ModelReleaseReport(
        status=str(gate_report["status"]),
        created_at=datetime.now(timezone.utc).isoformat(),
        evaluation_report_path=str(evaluation_report_path),
        promotion_policy_path=str(resolved_policy_path),
        model_manifest_path=str(model_manifest_path) if model_manifest_path else None,
        gate_report=gate_report,
        model_manifest=model_manifest,
    )

    if output_json_path is not None:
        _write_json(output_json_path, report.to_dict())
    if output_markdown_path is not None:
        _write_markdown(output_markdown_path, report)
    return report
