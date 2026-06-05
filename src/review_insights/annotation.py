from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .data_store import DatasetIngestionResult, default_data_root, ingest_csv_dataset


@dataclass(frozen=True)
class AnnotationBatchResult:
    dataset_version: str
    annotation_queue_path: str
    annotation_queue_rows: int
    readiness_report_path: str
    quality_status: str
    quality_failed_checks: list[str]
    source_manifest_path: str

    def to_dict(self) -> dict:
        return asdict(self)


def _read_quality_report(ingestion: DatasetIngestionResult) -> dict:
    return json.loads(Path(ingestion.quality_report_path).read_text(encoding="utf-8"))


def _write_readiness_report(
    *,
    ingestion: DatasetIngestionResult,
    quality_report: dict,
    annotation_queue_rows: int,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    profile = quality_report.get("profile", {})
    content = "\n".join(
        [
            "# Rapport readiness dataset",
            "",
            f"- Dataset version: `{ingestion.dataset_version}`",
            f"- Statut qualite: `{ingestion.quality_status}`",
            f"- Lignes ingerees: {ingestion.rows_ingested}",
            f"- Lignes valides: {ingestion.rows_valid}",
            f"- Lignes rejetees: {ingestion.rows_rejected}",
            f"- Lignes a annoter: {annotation_queue_rows}",
            f"- Splits: train={ingestion.split_rows.get('train', 0)}, validation={ingestion.split_rows.get('validation', 0)}, test={ingestion.split_rows.get('test', 0)}",
            f"- Contrat data SHA-256: `{ingestion.dataset_contract_sha256}`",
            f"- Politique qualite SHA-256: `{ingestion.quality_policy_sha256}`",
            f"- Commit Git: `{ingestion.git_commit}`",
            "",
            "## Checks echoues",
            "",
            json.dumps(ingestion.quality_failed_checks, indent=2, ensure_ascii=False),
            "",
            "## Profil qualite",
            "",
            json.dumps(profile, indent=2, ensure_ascii=False),
            "",
            "## Usage annotation",
            "",
            "Completer la colonne `sentiment_label` dans la file d'annotation avec une des valeurs: `negative`, `neutral`, `positive`.",
            "Ne pas inventer de label quand le texte ne permet pas de trancher: marquer `neutral` si le signal du theme est ambigu.",
            "",
        ]
    )
    output_path.write_text(content, encoding="utf-8")
    return output_path


def prepare_annotation_batch(
    source_csv: Path,
    *,
    output_dir: Path,
    data_root: Path | None = None,
    dataset_version: str | None = None,
    quality_policy_path: Path | None = None,
) -> AnnotationBatchResult:
    resolved_data_root = data_root or default_data_root()
    ingestion = ingest_csv_dataset(
        source_path=source_csv,
        data_root=resolved_data_root,
        dataset_version=dataset_version,
        quality_policy_path=quality_policy_path,
        enforce_quality_gates=False,
    )
    quality_report = _read_quality_report(ingestion)
    output_dir.mkdir(parents=True, exist_ok=True)

    annotation_queue = pd.read_csv(ingestion.annotation_queue_path)
    annotation_queue_path = output_dir / f"annotation_queue_{ingestion.dataset_version}.csv"
    shutil.copy2(ingestion.annotation_queue_path, annotation_queue_path)

    readiness_report_path = _write_readiness_report(
        ingestion=ingestion,
        quality_report=quality_report,
        annotation_queue_rows=int(len(annotation_queue)),
        output_path=output_dir / f"dataset_readiness_{ingestion.dataset_version}.md",
    )

    return AnnotationBatchResult(
        dataset_version=ingestion.dataset_version,
        annotation_queue_path=str(annotation_queue_path),
        annotation_queue_rows=int(len(annotation_queue)),
        readiness_report_path=str(readiness_report_path),
        quality_status=ingestion.quality_status,
        quality_failed_checks=list(ingestion.quality_failed_checks),
        source_manifest_path=ingestion.manifest_path,
    )
