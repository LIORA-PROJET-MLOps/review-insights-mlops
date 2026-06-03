from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict

import joblib
import numpy as np
import pandas as pd
import sklearn
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
THEME_SENTIMENT_COLUMNS = {
    "livraison": "sentiment_livraison",
    "sav": "sentiment_sav",
    "produit": "sentiment_produit",
}
MODEL_ARTIFACT_FILENAMES = (
    "themes_clf.joblib",
    "themes_thresholds.npy",
    "sent_livraison.joblib",
    "sent_sav.joblib",
    "sent_produit.joblib",
)
DEFAULT_EVALUATION_DATASET = ROOT_DIR / "data" / "sample" / "reviews_poc_test.csv"


def _review_texts(df) -> list[str]:
    return (
        df["review_title"].astype(str).str.cat(df["review_body"].astype(str), sep=" ").str.strip().tolist()
    )


def _theme_targets(df) -> np.ndarray:
    return df[["theme_livraison", "theme_sav", "theme_produit"]].astype(int).to_numpy()


def _sentiment_targets(labels: pd.Series) -> np.ndarray:
    return labels.map(LABEL_TO_CLASS).fillna(LABEL_TO_CLASS["neutral"]).astype(int).to_numpy()


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _theme_sentiment_training_data(df: pd.DataFrame, theme: str) -> tuple[list[str], np.ndarray, str]:
    theme_column = f"theme_{theme}"
    explicit_column = THEME_SENTIMENT_COLUMNS[theme]
    themed = df[df[theme_column].astype(int) == 1].copy()

    if explicit_column in themed.columns:
        explicit_mask = themed[explicit_column].astype(str).str.lower().isin(LABEL_TO_CLASS)
        explicit = themed.loc[explicit_mask].copy()
        if explicit[explicit_column].nunique() >= 2:
            return (
                _review_texts(explicit),
                _sentiment_targets(explicit[explicit_column].astype(str).str.lower()),
                "explicit_theme_sentiment",
            )

    if themed["sentiment_label"].nunique() >= 2:
        return (
            _review_texts(themed),
            _sentiment_targets(themed["sentiment_label"].astype(str).str.lower()),
            "global_sentiment_for_present_theme",
        )

    if df["sentiment_label"].nunique() >= 2:
        return (
            _review_texts(df),
            _sentiment_targets(df["sentiment_label"].astype(str).str.lower()),
            "global_sentiment_all_reviews_fallback",
        )
    raise ValueError(f"At least two sentiment classes are required to train the {theme} sentiment model.")


def _write_manifest(
    output_dir: Path,
    threshold: float,
    training_dataset: str,
    evaluation_dataset: str | None,
    training_rows: int,
    sentiment_supervision: Dict[str, str],
) -> Path:
    manifest = {
        "project": "Review Insights+",
        "artifact_set_version": "0.1.0-training-pipeline",
        "manifest_schema_version": "1.0.0",
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
        "artifact_sha256": {
            filename: _sha256(output_dir / filename)
            for filename in MODEL_ARTIFACT_FILENAMES
        },
        "training": {
            "training_dataset": training_dataset,
            "evaluation_dataset": evaluation_dataset,
            "training_rows": training_rows,
            "sentiment_supervision": sentiment_supervision,
            "python_version": platform.python_version(),
            "library_versions": {
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "scikit_learn": sklearn.__version__,
            },
        },
        "runtime_notes": {
            "backend_name": "project_models_v1",
            "fallback_backend": "heuristic_rules_v1",
            "training_dataset": training_dataset,
            "evaluation_dataset": evaluation_dataset,
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
        for theme in THEME_ORDER:
            column = f"theme_{theme}"
            if column in merged:
                merged[f"true_{column}"] = merged[column]
        merged.update(result)
        rows.append(merged)
    return evaluate_predictions(pd.DataFrame(rows), backend_name="project_models_v1").to_dict()


def build_training_artifacts(
    output_dir: Path,
    threshold: float = 0.5,
    dataset_path: Path | None = None,
    evaluation_dataset_path: Path | None = None,
) -> Dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    if dataset_path:
        df = load_training_dataset(dataset_path)
        training_dataset = str(dataset_path)
    else:
        df = prepare_dataset(load_default_dataset())
        training_dataset = "default_reviews"
    if evaluation_dataset_path:
        evaluation_df = load_training_dataset(evaluation_dataset_path)
        evaluation_dataset = str(evaluation_dataset_path)
    elif dataset_path is None and DEFAULT_EVALUATION_DATASET.exists():
        evaluation_df = load_training_dataset(DEFAULT_EVALUATION_DATASET)
        evaluation_dataset = str(DEFAULT_EVALUATION_DATASET)
    else:
        evaluation_df = None
        evaluation_dataset = None
    texts = _review_texts(df)

    themes_model = _theme_classifier()
    themes_model.fit(texts, _theme_targets(df))
    joblib.dump(themes_model, output_dir / "themes_clf.joblib")
    np.save(output_dir / "themes_thresholds.npy", np.full(len(THEME_ORDER), float(threshold)))

    sentiment_supervision: Dict[str, str] = {}
    for theme in THEME_ORDER:
        sentiment_texts, sentiment_targets, supervision = _theme_sentiment_training_data(df, theme)
        model = _text_classifier()
        model.fit(sentiment_texts, sentiment_targets)
        joblib.dump(model, output_dir / f"sent_{theme}.joblib")
        sentiment_supervision[theme] = supervision

    manifest_path = _write_manifest(
        output_dir,
        threshold,
        training_dataset,
        evaluation_dataset,
        len(df),
        sentiment_supervision,
    )
    if evaluation_df is not None:
        summary = _evaluate_trained_artifacts(output_dir, evaluation_df)
        summary["evaluation_status"] = "completed"
    else:
        summary = {
            "rows": 0,
            "backend_name": "project_models_v1",
            "evaluation_status": "not_run",
        }
    summary["output_dir"] = str(output_dir)
    summary["manifest_path"] = str(manifest_path)
    summary["training_dataset"] = training_dataset
    summary["training_rows"] = int(len(df))
    summary["evaluation_dataset"] = evaluation_dataset
    summary["threshold"] = float(threshold)
    summary["sentiment_supervision"] = sentiment_supervision
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Review Insights+ model artifacts from the default dataset.")
    parser.add_argument("--output-dir", default=str(ROOT_DIR / "artifacts" / "trained_models"))
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--dataset-path", default=None, help="Optional validated CSV or Parquet dataset to train on.")
    parser.add_argument("--evaluation-dataset-path", default=None, help="Optional independent validated CSV or Parquet dataset for evaluation.")
    parser.add_argument("--mlflow-log", action="store_true", help="Log the training run and model artifacts to MLflow.")
    parser.add_argument("--register-model", action="store_true", help="Register the trained model as an MLflow candidate model version.")
    parser.add_argument("--registered-model-name", default="review-insights-project-models")
    parser.add_argument("--model-alias", default="candidate")
    args = parser.parse_args()

    dataset_path = Path(args.dataset_path) if args.dataset_path else None
    evaluation_dataset_path = Path(args.evaluation_dataset_path) if args.evaluation_dataset_path else None
    output_dir = Path(args.output_dir)
    summary = build_training_artifacts(
        output_dir,
        threshold=args.threshold,
        dataset_path=dataset_path,
        evaluation_dataset_path=evaluation_dataset_path,
    )
    if args.mlflow_log or args.register_model:
        mlflow_result = log_training_run(
            summary,
            model_artifact_dir=output_dir,
            register_model=args.register_model,
            registered_model_name=args.registered_model_name,
            model_alias=args.model_alias,
        )
        summary["mlflow"] = asdict(mlflow_result)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
