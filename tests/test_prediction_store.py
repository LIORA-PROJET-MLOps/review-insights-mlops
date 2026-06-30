import json

from src.review_insights.prediction_store import (
    PredictionEvent,
    append_prediction_event,
    read_prediction_events,
)


def _prediction() -> dict:
    return {
        "review_id": "review-private-1",
        "global_sentiment": "negative",
        "score_global": 0.82,
        "themes_detected": ["sav"],
        "theme_livraison": 0,
        "sent_livraison": "neutral",
        "conf_livraison": 0.2,
        "theme_sav": 1,
        "sent_sav": "negative",
        "conf_sav": 0.91,
        "theme_produit": 0,
        "sent_produit": "neutral",
        "conf_produit": 0.3,
        "needs_human_review": True,
        "sentiment_conflict": False,
    }


def test_prediction_event_never_stores_raw_review_text():
    raw_text = "Private customer review that must not be persisted."
    event = PredictionEvent.from_prediction(
        _prediction(),
        review_text=raw_text,
        backend_name="project_models_v1",
        model_version="candidate-3",
    )

    payload = event.to_dict()

    assert payload["review_length"] == len(raw_text)
    assert raw_text not in json.dumps(payload)
    assert "review_text" not in payload


def test_prediction_store_appends_reads_latest_and_skips_malformed_lines(tmp_path):
    path = tmp_path / "prediction_events.jsonl"
    for review_id in ("r1", "r2"):
        prediction = _prediction() | {"review_id": review_id}
        append_prediction_event(
            PredictionEvent.from_prediction(
                prediction,
                review_text="Safe only in memory",
                backend_name="test",
                model_version="v1",
            ),
            path,
        )
    with path.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")

    events = read_prediction_events(path, limit=2)

    assert [event["review_id"] for event in events] == ["r1", "r2"]
    assert read_prediction_events(tmp_path / "missing.jsonl") == []
