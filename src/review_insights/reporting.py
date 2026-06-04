from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json_report(report: Dict, output_path: Path) -> Path:
    ensure_directory(output_path.parent)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def write_markdown_report(report: Dict, output_path: Path) -> Path:
    ensure_directory(output_path.parent)
    summary = report.get("summary", {})
    content = "\n".join(
        [
            "# Rapport d'evaluation",
            "",
            f"- Date UTC: {datetime.now(timezone.utc).isoformat()}",
            f"- Backend: {summary.get('backend_name', 'unknown')}",
            f"- Lignes evaluees: {summary.get('rows', 0)}",
            f"- Accuracy sentiment: {summary.get('sentiment_accuracy', 0.0)}",
            f"- F1 macro sentiment: {summary.get('sentiment_macro_f1', 0.0)}",
            f"- Theme exact match: {summary.get('theme_exact_match', 0.0)}",
            f"- Theme precision macro: {summary.get('theme_precision_macro', 0.0)}",
            f"- Theme recall macro: {summary.get('theme_recall_macro', 0.0)}",
            f"- Theme F1 macro: {summary.get('theme_f1_macro', 0.0)}",
            f"- Taux human review: {summary.get('human_review_rate', 0.0)}",
            "",
            "## Sentiment par classe",
            "",
            json.dumps(summary.get("sentiment_per_class", {}), indent=2, ensure_ascii=False),
            "",
            "## Themes par classe",
            "",
            json.dumps(summary.get("theme_metrics", {}), indent=2, ensure_ascii=False),
            "",
            "## Preview",
            "",
            json.dumps(report.get("rows_preview", []), indent=2, ensure_ascii=False),
            "",
        ]
    )
    output_path.write_text(content, encoding="utf-8")
    return output_path
