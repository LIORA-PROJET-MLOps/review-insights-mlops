from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import joblib
import numpy as np
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


def load_project_model_artifacts(models_dir: str | None = None) -> ProjectModelArtifacts:
    settings = get_settings()
    base_dir = Path(models_dir or settings.models_dir)
    themes_model = _load_joblib(base_dir / "themes_clf.joblib")
    thresholds = np.load(base_dir / "themes_thresholds.npy", allow_pickle=True)
    sentiment_models = {
        "livraison": _load_joblib(base_dir / "sent_livraison.joblib"),
        "sav": _load_joblib(base_dir / "sent_sav.joblib"),
        "produit": _load_joblib(base_dir / "sent_produit.joblib"),
    }
    sentiment_class_map = {
        theme: _build_sentiment_class_map(theme, model)
        for theme, model in sentiment_models.items()
    }
    return ProjectModelArtifacts(
        themes_model=themes_model,
        thresholds=thresholds,
        sentiment_models=sentiment_models,
        sentiment_class_map=sentiment_class_map,
    )


def _join_text(review_text: str) -> str:
    return str(review_text or "").strip()


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
        sentiment_confidence = float(np.clip(probabilities[predicted_class], 0.0, 1.0))
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
