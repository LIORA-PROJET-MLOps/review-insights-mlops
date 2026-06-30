from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


_FEEDBACK_LOCK = Lock()


@dataclass(frozen=True)
class HumanFeedbackRecord:
    review_id: str
    theme: str
    corrected_theme_present: int
    corrected_sentiment: str
    reviewer: str = "anonymous"
    notes: str = ""
    source: str = "manual"
    created_at: str = ""

    def normalized(self) -> "HumanFeedbackRecord":
        return HumanFeedbackRecord(
            review_id=str(self.review_id).strip(),
            theme=str(self.theme).strip().lower(),
            corrected_theme_present=int(self.corrected_theme_present),
            corrected_sentiment=str(self.corrected_sentiment).strip().lower(),
            reviewer=str(self.reviewer or "anonymous").strip() or "anonymous",
            notes=str(self.notes or "").strip(),
            source=str(self.source or "manual").strip() or "manual",
            created_at=self.created_at or datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_feedback(record: HumanFeedbackRecord) -> HumanFeedbackRecord:
    normalized = record.normalized()
    if not normalized.review_id:
        raise ValueError("review_id is required.")
    if normalized.theme not in {"livraison", "sav", "produit"}:
        raise ValueError("theme must be one of: livraison, sav, produit.")
    if normalized.corrected_theme_present not in {0, 1}:
        raise ValueError("corrected_theme_present must be 0 or 1.")
    if normalized.corrected_sentiment not in {"negative", "neutral", "positive"}:
        raise ValueError("corrected_sentiment must be one of: negative, neutral, positive.")
    return normalized


def append_feedback(record: HumanFeedbackRecord, store_path: Path) -> HumanFeedbackRecord:
    normalized = validate_feedback(record)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(normalized.to_dict(), ensure_ascii=False)
    with _FEEDBACK_LOCK:
        with store_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return normalized


def read_feedback(store_path: Path, *, limit: int = 100) -> list[dict[str, Any]]:
    if not store_path.exists():
        return []
    if limit <= 0:
        return []
    with store_path.open("r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]
    records: list[dict[str, Any]] = []
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
        if len(records) == limit:
            break
    return list(reversed(records))
