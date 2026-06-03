from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import joblib
import numpy as np
from huggingface_hub import hf_hub_download
from sklearn.exceptions import InconsistentVersionWarning

from .config import THEMES
from .engine import actionable_text, analyze_review
from .settings import get_settings


THEME_ORDER = ["livraison", "sav", "produit"]

SENTIMENT_CALIBRATION_TEXTS = {
    "livraison": {
        "positive": "the delivery was fast and arrived on time",
        "negative": "the delivery was late and the package arrived damaged",
    },
    "sav": {
        "positive": "customer support was helpful and solved my issue quickly",
        "negative": "customer support never answered my refund request",
    },
    "produit": {
        "positive": "the product quality is great and the fit is perfect",
        "negative": "the product has cheap material and the wrong size",
    },
}


@dataclass
class ProjectModelArtifacts:
    themes_model: object
    thresholds: np.ndarray
    sentiment_models: Dict[str, object]
    sentiment_class_map: Dict[str, Dict[int, str]]
    artifact_set_version: str
    manifest: Dict


MODEL_ARTIFACT_FILENAMES = (
    "themes_clf.joblib",
    "themes_thresholds.npy",
    "sent_livraison.joblib",
    "sent_sav.joblib",
    "sent_produit.joblib",
)
ARTIFACT_FILENAMES = MODEL_ARTIFACT_FILENAMES + ("manifest.json",)


def _patch_pipeline_for_predict_proba(model: object) -> object:
    if hasattr(model, "named_steps"):
        last_step = list(model.named_steps.values())[-1]
        if hasattr(last_step, "estimators_"):
            for estimator in last_step.estimators_:
                if not hasattr(estimator, "multi_class"):
                    estimator.multi_class = "ovr"
        elif not hasattr(last_step, "multi_class"):
            last_step.multi_class = "ovr"
    return model


def _load_joblib(path: Path) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InconsistentVersionWarning)
        model = joblib.load(path)
    return _patch_pipeline_for_predict_proba(model)


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(base_dir: Path) -> Dict:
    manifest_path = base_dir / "manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Model manifest must contain a JSON object.")
    return manifest


def _verify_artifact_checksums(base_dir: Path, manifest: Dict) -> None:
    expected_checksums = manifest.get("artifact_sha256", {})
    if not isinstance(expected_checksums, dict):
        raise ValueError("Model manifest artifact_sha256 must be a JSON object.")
    for filename, expected_checksum in expected_checksums.items():
        if filename not in MODEL_ARTIFACT_FILENAMES:
            continue
        artifact_path = base_dir / filename
        actual_checksum = _sha256(artifact_path)
        if actual_checksum != str(expected_checksum):
            raise ValueError(f"Checksum mismatch for model artifact: {filename}")


def _build_sentiment_class_map(theme: str, model: object) -> Dict[int, str]:
    positive_pred = int(model.predict([SENTIMENT_CALIBRATION_TEXTS[theme]["positive"]])[0])
    negative_pred = int(model.predict([SENTIMENT_CALIBRATION_TEXTS[theme]["negative"]])[0])
    remaining = [cls for cls in list(getattr(model, "classes_", [0, 1, 2])) if cls not in {positive_pred, negative_pred}]
    neutral_pred = int(remaining[0]) if remaining else positive_pred
    return {
        positive_pred: "positive",
        negative_pred: "negative",
        neutral_pred: "neutral",
    }


def _load_manifest_sentiment_class_map(base_dir: Path, sentiment_models: Dict[str, object]) -> Dict[str, Dict[int, str]] | None:
    manifest_path = base_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw_mapping = manifest.get("sentiment_class_map", {})
        resolved_mapping = {
            theme: {int(class_id): str(label) for class_id, label in raw_mapping.get(theme, {}).items()}
            for theme in sentiment_models
        }
    except Exception:
        return None
    if any(not mapping for mapping in resolved_mapping.values()):
        return None
    return resolved_mapping


def _resolve_sentiment_class_map(base_dir: Path, sentiment_models: Dict[str, object]) -> Dict[str, Dict[int, str]]:
    manifest_mapping = _load_manifest_sentiment_class_map(base_dir, sentiment_models)
    if manifest_mapping is not None:
        return manifest_mapping
    return {
        theme: _build_sentiment_class_map(theme, model)
        for theme, model in sentiment_models.items()
    }


def download_hf_model_artifacts(
    repo_id: str,
    local_dir: str,
    revision: str | None = None,
    token: str | None = None,
    cache_dir: str | None = None,
) -> Path:
    target_dir = Path(local_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in ARTIFACT_FILENAMES:
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="model",
            revision=revision,
            token=token,
            cache_dir=cache_dir,
            local_dir=target_dir,
        )
    return target_dir


def load_project_model_artifacts(models_dir: str | None = None, *, source: str | None = None) -> ProjectModelArtifacts:
    settings = get_settings()
    resolved_source = (source or settings.model_source).strip().lower()
    if resolved_source not in {"local", "hf_hub"}:
        raise ValueError(f"Unsupported model source: {resolved_source}")
    if resolved_source == "hf_hub":
        if not settings.hf_model_repo_id:
            raise ValueError("HF_MODEL_REPO_ID must be configured when MODEL_SOURCE=hf_hub.")
        base_dir = download_hf_model_artifacts(
            repo_id=settings.hf_model_repo_id,
            local_dir=settings.hf_artifacts_dir,
            revision=settings.hf_model_revision,
            token=settings.hf_token,
            cache_dir=settings.hf_cache_dir,
        )
    else:
        base_dir = Path(models_dir or settings.models_dir)
    manifest = _load_manifest(base_dir)
    _verify_artifact_checksums(base_dir, manifest)
    themes_model = _load_joblib(base_dir / "themes_clf.joblib")
    thresholds = np.load(base_dir / "themes_thresholds.npy", allow_pickle=True)
    if len(thresholds) != len(THEME_ORDER):
        raise ValueError("Theme thresholds length does not match the configured theme order.")
    sentiment_models = {
        "livraison": _load_joblib(base_dir / "sent_livraison.joblib"),
        "sav": _load_joblib(base_dir / "sent_sav.joblib"),
        "produit": _load_joblib(base_dir / "sent_produit.joblib"),
    }
    sentiment_class_map = _resolve_sentiment_class_map(base_dir, sentiment_models)
    return ProjectModelArtifacts(
        themes_model=themes_model,
        thresholds=thresholds,
        sentiment_models=sentiment_models,
        sentiment_class_map=sentiment_class_map,
        artifact_set_version=str(manifest.get("artifact_set_version", "unknown")),
        manifest=manifest,
    )


def _join_text(review_text: str) -> str:
    return str(review_text or "").strip()


def _predicted_class_probability(model: object, probabilities: np.ndarray, predicted_class: int) -> float:
    classes = np.asarray(getattr(model, "classes_", np.arange(len(probabilities))))
    matches = np.where(classes == predicted_class)[0]
    if len(matches):
        return float(probabilities[int(matches[0])])
    return float(np.max(probabilities))


def analyze_with_project_models(review_text: str, review_id: str, artifacts: ProjectModelArtifacts, threshold_override: float | None = None) -> Dict:
    text = _join_text(review_text)
    if not text:
        return analyze_review(review_text, review_id)

    theme_proba = np.asarray(artifacts.themes_model.predict_proba([text])[0], dtype=float)
    thresholds = np.asarray(artifacts.thresholds, dtype=float)
    if threshold_override is not None:
        thresholds = np.full_like(thresholds, fill_value=float(threshold_override))

    theme_results: Dict[str, Dict] = {}
    detected_themes: List[str] = []
    insights: List[Dict] = []
    theme_confidences: List[float] = []

    for idx, theme_key in enumerate(THEME_ORDER):
        confidence = float(np.clip(theme_proba[idx], 0.0, 1.0))
        present = int(confidence >= thresholds[idx])
        theme_results[theme_key] = {
            "present": present,
            "confidence": round(confidence, 2),
            "sentiment": None,
            "evidence": [],
        }
        if present:
            detected_themes.append(theme_key)

    positive_terms: List[str] = []
    negative_terms: List[str] = []
    theme_label_fr = {theme.key: theme.label_fr for theme in THEMES}

    for theme_key in detected_themes:
        model = artifacts.sentiment_models[theme_key]
        probabilities = np.asarray(model.predict_proba([text])[0], dtype=float)
        predicted_class = int(model.predict([text])[0])
        sentiment = artifacts.sentiment_class_map[theme_key].get(predicted_class, "neutral")
        sentiment_confidence = float(
            np.clip(_predicted_class_probability(model, probabilities, predicted_class), 0.0, 1.0)
        )
        combined_confidence = round(min(theme_results[theme_key]["confidence"] * 0.6 + sentiment_confidence * 0.4, 0.99), 2)
        theme_results[theme_key]["sentiment"] = sentiment
        theme_results[theme_key]["confidence"] = combined_confidence
        theme_results[theme_key]["evidence"] = [f"{theme_label_fr[theme_key]} model"]
        theme_confidences.append(combined_confidence)
        if sentiment == "positive":
            positive_terms.append(theme_key)
        elif sentiment == "negative":
            negative_terms.append(theme_key)
        insights.append(
            {
                "topic": theme_key,
                "sentiment": sentiment,
                "confidence": combined_confidence,
                "evidence": theme_results[theme_key]["evidence"],
                "actionable_text": actionable_text(theme_key, sentiment),
            }
        )

    if insights:
        negative_scores = [item["confidence"] for item in insights if item["sentiment"] == "negative"]
        positive_scores = [item["confidence"] for item in insights if item["sentiment"] == "positive"]
        if negative_scores and max(negative_scores) >= max(positive_scores or [0]):
            global_sentiment = "negative"
        elif positive_scores:
            global_sentiment = "positive"
        else:
            global_sentiment = "neutral"
    else:
        heuristic = analyze_review(review_text, review_id, threshold=float(thresholds.min()))
        global_sentiment = heuristic["global_sentiment"]
        positive_terms = heuristic["positive_terms"]
        negative_terms = heuristic["negative_terms"]

    score_global = round(sum(theme_confidences) / len(theme_confidences), 2) if theme_confidences else 0.5
    needs_human_review = not detected_themes or any(theme_results[theme]["confidence"] < 0.45 for theme in detected_themes)

    result = {
        "review_id": review_id,
        "review_text": review_text,
        "global_sentiment": global_sentiment,
        "score_global": score_global,
        "positive_terms": positive_terms,
        "negative_terms": negative_terms,
        "themes_detected": detected_themes,
        "needs_human_review": needs_human_review,
        "insights": insights,
    }

    for theme_key in THEME_ORDER:
        result[f"theme_{theme_key}"] = theme_results[theme_key]["present"]
        result[f"sent_{theme_key}"] = theme_results[theme_key]["sentiment"]
        result[f"conf_{theme_key}"] = theme_results[theme_key]["confidence"]
        result[f"evidence_{theme_key}"] = theme_results[theme_key]["evidence"]

    return result
