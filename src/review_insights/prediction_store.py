from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


_PREDICTION_LOCK = Lock()
THEMES = ("livraison", "sav", "produit")


@dataclass(frozen=True)
class PredictionEvent:
    event_id: str
    created_at: str
    review_id: str
    backend_name: str
    model_version: str
    global_sentiment: str
    global_confidence: float
    themes_detected: list[str]
    theme_predictions: dict[str, dict[str, Any]]
    needs_human_review: bool
    sentiment_conflict: bool
    review_length: int
    schema_version: str = "1.0.0"

    @classmethod
    def from_prediction(
        cls,
        result: dict[str, Any],
        *,
        review_text: str,
        backend_name: str,
        model_version: str,
        created_at: str | None = None,
    ) -> "PredictionEvent":
        theme_predictions = {
            theme: {
                "present": bool(result.get(f"theme_{theme}", 0)),
                "sentiment": result.get(f"sent_{theme}"),
                "confidence": float(result.get(f"conf_{theme}", 0.0) or 0.0),
            }
            for theme in THEMES
        }
        return cls(
            event_id=uuid4().hex,
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
            review_id=str(result.get("review_id", "unknown")).strip() or "unknown",
            backend_name=str(backend_name),
            model_version=str(model_version),
            global_sentiment=str(result.get("global_sentiment", "unknown")),
            global_confidence=float(result.get("score_global", 0.0) or 0.0),
            themes_detected=[str(theme) for theme in result.get("themes_detected", [])],
            theme_predictions=theme_predictions,
            needs_human_review=bool(result.get("needs_human_review")),
            sentiment_conflict=bool(result.get("sentiment_conflict")),
            review_length=len(review_text),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def append_prediction_event(event: PredictionEvent, store_path: Path) -> PredictionEvent:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event.to_dict(), ensure_ascii=False)
    with _PREDICTION_LOCK:
        with store_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return event


def read_prediction_events(store_path: Path, *, limit: int = 500) -> list[dict[str, Any]]:
    if not store_path.is_file():
        return []
    if limit <= 0:
        return []
    with store_path.open("r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]
    events: list[dict[str, Any]] = []
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
        if len(events) == limit:
            break
    return list(reversed(events))
