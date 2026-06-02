from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.review_insights.data_store import load_training_dataset
from src.review_insights.dataset import load_default_dataset, prepare_dataset
from src.review_insights.evaluation import evaluate_predictions
from src.review_insights.mlflow_tracking import log_training_run
from src.review_insights.model_backend import THEME_ORDER, analyze_with_project_models, load_project_model_artifacts


LABEL_TO_CLASS = {"negative": 0, "neutral": 1, "positive": 2}
CLASS_TO_LABEL = {value: key for key, value in LABEL_TO_CLASS.items()}


def _review_texts(df) -> list[str]:
    return (
        df["review_title"].astype(str).str.cat(df["review_body"].astype(str), sep=" ").str.strip().tolist()
    )


def _theme_targets(df) -> np.ndarray:
    return df[["theme_livraison", "theme_sav", "theme_produit"]].astype(int).to_numpy()


def _sentiment_targets(df) -> np.ndarray:
    return df["sentiment_label"].map(LABEL_TO_CLASS).fillna(LABEL_TO_CLASS["neutral"]).astype(int).to_numpy()


def _text_classifier() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2))),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", solver="liblinear")),
        ]
    )


def _theme_classifier() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2))),
            ("clf", OneVsRestClassifier(LogisticRegression(max_iter=1000, class_weight="balanced", solver="liblinear"))),
        ]
    )


def _write_manifest(output_dir: Path, threshold: float, training_dataset: str) -> Path:
    manifest = {
        "project": "Review Insights+",
        "artifact_set_version": "0.1.0-training-pipeline",
        "language_scope": "english_reviews_only",
        "theme_model": {
            "file": "themes_clf.joblib",
            "thresholds_file": "themes_thresholds.npy",
            "themes_order": THEME_ORDER,
            "default_threshold": threshold,
        },
        "sentiment_models": {
            "livraison": "sent_livraison.joblib",
            "sav": "sent_sav.joblib",
            "produit": "sent_produit.joblib",
        },
        "sentiment_class_map": {
            theme: {str(class_id): label for class_id, label in CLASS_TO_LABEL.items()}
            for theme in THEME_ORDER
        },
        "runtime_notes": {
            "backend_name": "project_models_v1",
            "fallback_backend": "heuristic_rules_v1",
            "training_dataset": training_dataset,
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def _evaluate_trained_artifacts(output_dir: Path, df: pd.DataFrame) -> Dict:
    artifacts = load_project_model_artifacts(str(output_dir), source="local")
    rows = []
    for _, row in df.iterrows():
        review_text = f"{row.get('review_title', '')} {row.get('review_body', '')}".strip()
        result = analyze_with_project_models(
            review_text=review_text,
            review_id=str(row.get("review_id", "training_review")),
            artifacts=artifacts,
        )
        merged = dict(row)
        merged.update(result)
        rows.append(merged)
    return evaluate_predictions(pd.DataFrame(rows), backend_name="project_models_v1").to_dict()


def build_training_artifacts(output_dir: Path, threshold: float = 0.5, dataset_path: Path | None = None) -> Dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    if dataset_path:
        df = load_training_dataset(dataset_path)
        training_dataset = str(dataset_path)
    else:
        df = prepare_dataset(load_default_dataset())
        training_dataset = "default_reviews"
    texts = _review_texts(df)

    themes_model = _theme_classifier()
    themes_model.fit(texts, _theme_targets(df))
    joblib.dump(themes_model, output_dir / "themes_clf.joblib")
    np.save(output_dir / "themes_thresholds.npy", np.full(len(THEME_ORDER), float(threshold)))

    sentiment_targets = _sentiment_targets(df)
    for theme in THEME_ORDER:
        model = _text_classifier()
        model.fit(texts, sentiment_targets)
        joblib.dump(model, output_dir / f"sent_{theme}.joblib")

    manifest_path = _write_manifest(output_dir, threshold, training_dataset)
    summary = _evaluate_trained_artifacts(output_dir, df)
    summary["output_dir"] = str(output_dir)
    summary["manifest_path"] = str(manifest_path)
    summary["training_dataset"] = training_dataset
    summary["threshold"] = float(threshold)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Review Insights+ model artifacts from the default dataset.")
    parser.add_argument("--output-dir", default=str(ROOT_DIR / "artifacts" / "trained_models"))
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--dataset-path", default=None, help="Optional validated CSV dataset to train on.")
    parser.add_argument("--mlflow-log", action="store_true", help="Log the training run and model artifacts to MLflow.")
    parser.add_argument("--register-model", action="store_true", help="Register the trained model as an MLflow candidate model version.")
    parser.add_argument("--registered-model-name", default="review-insights-project-models")
    parser.add_argument("--model-stage", default="candidate")
    args = parser.parse_args()

    dataset_path = Path(args.dataset_path) if args.dataset_path else None
    output_dir = Path(args.output_dir)
    summary = build_training_artifacts(output_dir, threshold=args.threshold, dataset_path=dataset_path)
    if args.mlflow_log or args.register_model:
        mlflow_result = log_training_run(
            summary,
            model_artifact_dir=output_dir,
            register_model=args.register_model,
            registered_model_name=args.registered_model_name,
            model_stage=args.model_stage,
        )
        summary["mlflow"] = asdict(mlflow_result)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
