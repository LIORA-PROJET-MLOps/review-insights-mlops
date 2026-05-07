import shutil
from pathlib import Path

from src.review_insights.model_backend import (
    ARTIFACT_FILENAMES,
    _load_manifest_sentiment_class_map,
    download_hf_model_artifacts,
)


def test_download_hf_model_artifacts_requests_all_files(monkeypatch):
    calls = []
    work_dir = Path("tests_runtime/hf_stub")
    if work_dir.exists():
        shutil.rmtree(work_dir)

    def fake_hf_hub_download(**kwargs):
        calls.append(kwargs)
        target = Path(kwargs["local_dir"]) / kwargs["filename"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("stub", encoding="utf-8")
        return str(target)

    monkeypatch.setattr("src.review_insights.model_backend.hf_hub_download", fake_hf_hub_download)

    target_dir = download_hf_model_artifacts(
        repo_id="LIORA-PROJET-MLOps/review-insights-models",
        local_dir=str(work_dir / "artifacts"),
        revision="main",
        token="secret",
        cache_dir=str(work_dir / "cache"),
    )

    assert target_dir.exists()
    assert len(calls) == len(ARTIFACT_FILENAMES)
    assert {call["filename"] for call in calls} == set(ARTIFACT_FILENAMES)

    shutil.rmtree(work_dir)


def test_manifest_sentiment_class_map_is_loaded():
    work_dir = Path("tests_runtime/manifest_stub")
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    (work_dir / "manifest.json").write_text(
        """
        {
          "sentiment_class_map": {
            "livraison": {"0": "negative", "1": "neutral", "2": "positive"},
            "sav": {"0": "neutral", "1": "negative", "2": "positive"},
            "produit": {"0": "negative", "1": "neutral", "2": "positive"}
          }
        }
        """,
        encoding="utf-8",
    )

    mapping = _load_manifest_sentiment_class_map(
        work_dir,
        {"livraison": object(), "sav": object(), "produit": object()},
    )

    assert mapping == {
        "livraison": {0: "negative", 1: "neutral", 2: "positive"},
        "sav": {0: "neutral", 1: "negative", 2: "positive"},
        "produit": {0: "negative", 1: "neutral", 2: "positive"},
    }

    shutil.rmtree(work_dir)
