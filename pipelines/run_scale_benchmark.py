from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.train_models import _evaluate_trained_artifacts, build_training_artifacts
from src.review_insights.data_store import default_data_root, ingest_csv_dataset
from src.review_insights.mlflow_tracking import log_training_run
from src.review_insights.model_registry import evaluate_promotion_gates, load_promotion_policy
from src.review_insights.settings import get_settings


MODEL_METRICS = (
    "sentiment_accuracy",
    "sentiment_macro_precision",
    "sentiment_macro_recall",
    "sentiment_macro_f1",
    "theme_exact_match",
    "theme_precision_macro",
    "theme_recall_macro",
    "theme_f1_macro",
    "human_review_rate",
)
QUALITY_SCORE_METRICS = (
    "sentiment_accuracy",
    "sentiment_macro_f1",
    "theme_exact_match",
    "theme_precision_macro",
    "theme_recall_macro",
    "theme_f1_macro",
)


def _portable_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT_DIR.resolve()).as_posix()
    except ValueError:
        return str(candidate)


def _project_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT_DIR / candidate


def _numeric_metrics(summary: dict[str, Any]) -> dict[str, float]:
    return {
        key: float(summary[key])
        for key in MODEL_METRICS
        if isinstance(summary.get(key), (int, float))
    }


def _quality_score(metrics: dict[str, float]) -> float:
    values = [metrics[name] for name in QUALITY_SCORE_METRICS if name in metrics]
    if not values:
        return 0.0
    return mean(values) - 0.10 * float(metrics.get("human_review_rate", 0.0))


def select_champion_candidate(
    candidates: list[dict[str, Any]],
    policy,
) -> dict[str, Any] | None:
    eligible: list[dict[str, Any]] = []
    for candidate in candidates:
        aggregate = candidate["aggregate_metrics"]
        aggregate_gate = evaluate_promotion_gates(aggregate, None, policy)
        profile_gates = {
            name: evaluate_promotion_gates(metrics, None, policy)
            for name, metrics in candidate["profile_metrics"].items()
        }
        candidate["aggregate_gate"] = aggregate_gate
        candidate["profile_gates"] = profile_gates
        candidate["eligible"] = aggregate_gate["status"] == "approved" and all(
            gate["status"] == "approved" for gate in profile_gates.values()
        )
        profile_scores = [
            _quality_score(metrics) for metrics in candidate["profile_metrics"].values()
        ]
        candidate["robustness_score"] = round(
            0.65 * _quality_score(aggregate)
            + 0.35 * min(profile_scores or [0.0]),
            6,
        )
        if candidate["eligible"]:
            eligible.append(candidate)

    if not eligible:
        return None
    return max(
        eligible,
        key=lambda candidate: (
            candidate["robustness_score"],
            -float(candidate.get("training_seconds", 0.0)),
        ),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Review Insights scale benchmark",
        "",
        f"Generated at: `{report['created_at']}`",
        f"Datasets: {len(report['datasets'])}; total source rows: {report['total_source_rows']}",
        "",
        "## Data quality",
        "",
        "| Dataset | Rows | Quality | Train | Validation | Test | Duplicate text leakage |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for dataset in report["datasets"]:
        split = dataset["split_rows"]
        lines.append(
            f"| {dataset['profile']} | {dataset['rows_valid']} | {dataset['quality_status']} | "
            f"{split.get('train', 0)} | {split.get('validation', 0)} | {split.get('test', 0)} | "
            f"{dataset['exact_text_leakage']} |"
        )

    lines.extend(
        [
            "",
            "## Model comparison",
            "",
            "| Candidate | Eligible | Robustness | Sentiment accuracy | Sentiment macro F1 | Theme exact match | Theme macro F1 | Human review | Training s | MLflow version |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for candidate in report["candidates"]:
        metrics = candidate["aggregate_metrics"]
        version = (candidate.get("mlflow") or {}).get("registered_model_version") or "-"
        lines.append(
            f"| {candidate['name']} | {candidate['eligible']} | {candidate['robustness_score']:.4f} | "
            f"{metrics.get('sentiment_accuracy', 0):.4f} | {metrics.get('sentiment_macro_f1', 0):.4f} | "
            f"{metrics.get('theme_exact_match', 0):.4f} | {metrics.get('theme_f1_macro', 0):.4f} | "
            f"{metrics.get('human_review_rate', 0):.4f} | {candidate['training_seconds']:.2f} | {version} |"
        )

    selected = report.get("selected_candidate")
    lines.extend(["", "## Decision", ""])
    if selected:
        lines.append(
            f"Selected candidate: **{selected['name']}** with robustness score "
            f"**{selected['robustness_score']:.4f}**."
        )
        lines.append(
            "The candidate passed the versioned promotion policy on the aggregate benchmark "
            "and on every dataset profile."
        )
    else:
        lines.append(
            "No candidate passed the promotion policy on both the aggregate benchmark and every profile."
        )
    lines.extend(
        [
            "",
            "## Methodology caveat",
            "",
            "These datasets are deterministic synthetic scalability fixtures, not a substitute for a frozen, human-labeled production corpus. "
            "Promotion proves pipeline readiness and controlled generalization across the three fixtures; production readiness still requires real labeled reviews and live drift monitoring.",
            "",
        ]
    )
    return "\n".join(lines)


def _set_selected_candidate_alias(
    *,
    tracking_uri: str,
    registered_model_name: str,
    version: str,
) -> None:
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)
    client.set_registered_model_alias(registered_model_name, "candidate", version)
    client.set_model_version_tag(
        registered_model_name,
        version,
        "benchmark_selection",
        "selected",
    )


def run_benchmark(
    *,
    generation_manifest_path: Path,
    data_root: Path,
    artifacts_root: Path,
    report_dir: Path,
    register_model: bool,
    tracking_uri: str | None,
    registered_model_name: str,
) -> dict[str, Any]:
    generated = json.loads(generation_manifest_path.read_text(encoding="utf-8"))
    policy = load_promotion_policy()
    datasets: list[dict[str, Any]] = []
    test_frames: dict[str, pd.DataFrame] = {}

    for generated_dataset in generated["datasets"]:
        spec = generated_dataset["spec"]
        profile = str(spec["name"])
        source_path = _project_path(generated_dataset["path"])
        version = f"scale_{profile}_{int(spec['rows'])}_v1"
        ingestion = ingest_csv_dataset(
            source_path,
            data_root,
            dataset_version=version,
            enforce_quality_gates=True,
        )
        train = pd.read_parquet(ingestion.train_parquet_path)
        test = pd.read_parquet(ingestion.test_parquet_path)
        train_text = train["review_title"].astype(str).str.cat(train["review_body"].astype(str), sep=" ")
        test_text = test["review_title"].astype(str).str.cat(test["review_body"].astype(str), sep=" ")
        exact_text_leakage = len(set(train_text).intersection(set(test_text)))
        test_frames[profile] = test
        datasets.append(
            {
                "profile": profile,
                "dataset_version": version,
                "source_path": _portable_path(source_path),
                "source_sha256": generated_dataset["sha256"],
                "rows_valid": ingestion.rows_valid,
                "rows_rejected": ingestion.rows_rejected,
                "quality_status": ingestion.quality_status,
                "quality_failed_checks": ingestion.quality_failed_checks,
                "split_rows": ingestion.split_rows,
                "exact_text_leakage": exact_text_leakage,
                "manifest_path": _portable_path(ingestion.manifest_path),
                "quality_report_path": _portable_path(ingestion.quality_report_path),
                "train_path": _portable_path(ingestion.train_parquet_path),
                "validation_path": _portable_path(ingestion.validation_parquet_path),
                "test_path": _portable_path(ingestion.test_parquet_path),
            }
        )

    all_test = pd.concat(
        [frame.assign(benchmark_profile=profile) for profile, frame in test_frames.items()],
        ignore_index=True,
    )
    composite_test_path = report_dir / "benchmark_composite_test.parquet"
    composite_test_path.parent.mkdir(parents=True, exist_ok=True)
    all_test.to_parquet(composite_test_path, index=False, compression="zstd")

    settings = get_settings()
    if register_model:
        settings = replace(
            settings,
            mlflow_tracking_enabled=True,
            mlflow_tracking_uri=tracking_uri or settings.mlflow_tracking_uri,
            mlflow_experiment_name="review-insights-scale-benchmark",
        )

    candidates: list[dict[str, Any]] = []
    for dataset in datasets:
        name = dataset["profile"]
        model_dir = artifacts_root / name
        if model_dir.exists():
            shutil.rmtree(model_dir)
        started = time.perf_counter()
        summary = build_training_artifacts(
            model_dir,
            dataset_path=_project_path(dataset["train_path"]),
            validation_dataset_path=_project_path(dataset["validation_path"]),
            evaluation_dataset_path=composite_test_path,
        )
        training_seconds = time.perf_counter() - started
        aggregate_metrics = {"rows": float(summary.get("rows", 0)), **_numeric_metrics(summary)}
        profile_metrics: dict[str, dict[str, float]] = {}
        for profile, test_df in test_frames.items():
            profile_summary = _evaluate_trained_artifacts(model_dir, test_df)
            profile_metrics[profile] = {
                "rows": float(profile_summary.get("rows", 0)),
                **_numeric_metrics(profile_summary),
            }
            for metric_name, value in profile_metrics[profile].items():
                summary[f"benchmark_{profile}_{metric_name}"] = value
        summary["benchmark_training_seconds"] = training_seconds
        summary["benchmark_model_size_bytes"] = sum(
            path.stat().st_size for path in model_dir.rglob("*") if path.is_file()
        )

        mlflow_result = None
        if register_model:
            mlflow_result = asdict(
                log_training_run(
                    summary,
                    model_artifact_dir=model_dir,
                    settings=settings,
                    run_name=f"scale_benchmark_{name}",
                    register_model=True,
                    registered_model_name=registered_model_name,
                    model_alias="candidate",
                )
            )
            if mlflow_result["status"] != "logged":
                raise RuntimeError(f"MLflow registration failed for {name}: {mlflow_result}")

        candidates.append(
            {
                "name": name,
                "training_dataset": dataset["dataset_version"],
                "model_dir": _portable_path(model_dir),
                "manifest_path": _portable_path(summary["manifest_path"]),
                "training_rows": summary["training_rows"],
                "training_seconds": round(training_seconds, 4),
                "model_size_bytes": int(summary["benchmark_model_size_bytes"]),
                "theme_thresholds": summary["theme_thresholds"],
                "threshold_tuning_report": summary["threshold_tuning_report"],
                "aggregate_metrics": aggregate_metrics,
                "profile_metrics": profile_metrics,
                "mlflow": mlflow_result,
            }
        )

    selected = select_champion_candidate(candidates, policy)
    if register_model and selected:
        selected_version = str(selected["mlflow"]["registered_model_version"])
        _set_selected_candidate_alias(
            tracking_uri=settings.mlflow_tracking_uri,
            registered_model_name=registered_model_name,
            version=selected_version,
        )

    report = {
        "schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generation_manifest_path": _portable_path(generation_manifest_path),
        "promotion_policy": asdict(policy),
        "total_source_rows": int(generated["total_rows"]),
        "composite_test_path": _portable_path(composite_test_path),
        "composite_test_rows": int(len(all_test)),
        "datasets": datasets,
        "candidates": candidates,
        "selected_candidate": (
            {
                "name": selected["name"],
                "robustness_score": selected["robustness_score"],
                "model_dir": selected["model_dir"],
                "mlflow": selected.get("mlflow"),
            }
            if selected
            else None
        ),
        "overall_status": "approved" if selected else "rejected",
        "limitations": [
            "Synthetic fixtures validate scale and pipeline behavior but do not replace real human-labeled reviews.",
            "All generated reviews are English because the versioned dataset contract is English-only.",
        ],
    }
    json_path = report_dir / "benchmark_report.json"
    markdown_path = report_dir / "README.md"
    _write_json(json_path, report)
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    return {
        **report,
        "report_json_path": _portable_path(json_path),
        "report_markdown_path": _portable_path(markdown_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest three generated datasets, train three candidates and select the robust winner."
    )
    parser.add_argument(
        "--generation-manifest",
        default=str(ROOT_DIR / "data" / "generated" / "generation_manifest.json"),
    )
    parser.add_argument("--data-root", default=str(default_data_root(ROOT_DIR)))
    parser.add_argument(
        "--artifacts-root",
        default=str(ROOT_DIR / "artifacts" / "scale_benchmark_models"),
    )
    parser.add_argument(
        "--report-dir",
        default=str(ROOT_DIR / "reports" / "scale_benchmark"),
    )
    parser.add_argument("--register-model", action="store_true")
    parser.add_argument("--tracking-uri", default=None)
    parser.add_argument("--registered-model-name", default="review-insights-project-models")
    args = parser.parse_args()

    report = run_benchmark(
        generation_manifest_path=Path(args.generation_manifest),
        data_root=Path(args.data_root),
        artifacts_root=Path(args.artifacts_root),
        report_dir=Path(args.report_dir),
        register_model=args.register_model,
        tracking_uri=args.tracking_uri,
        registered_model_name=args.registered_model_name,
    )
    print(
        json.dumps(
            {
                "overall_status": report["overall_status"],
                "selected_candidate": report["selected_candidate"],
                "report_json_path": report["report_json_path"],
                "report_markdown_path": report["report_markdown_path"],
            },
            indent=2,
        )
    )
    if report["overall_status"] != "approved":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
