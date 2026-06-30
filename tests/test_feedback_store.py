from src.review_insights.feedback_store import read_feedback


def test_feedback_reader_returns_latest_valid_records(tmp_path):
    path = tmp_path / "feedback.jsonl"
    path.write_text(
        '{"review_id":"r1"}\nnot-json\n{"review_id":"r2"}\n',
        encoding="utf-8",
    )

    assert [record["review_id"] for record in read_feedback(path, limit=2)] == ["r1", "r2"]
    assert read_feedback(path, limit=0) == []
