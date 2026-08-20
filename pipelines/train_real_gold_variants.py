from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion, Pipeline


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.train_models import (
    MODEL_ARTIFACT_FILENAMES,
    THEME_ORDER,
    _evaluate_trained_artifacts,
    _review_texts,
    _theme_sentiment_training_data,
    _theme_targets,
    _write_manifest,
)
from src.review_insights.mlflow_tracking import log_training_run


DEFAULT_TRAIN = ROOT_DIR / "data" / "external" / "fabsa" / "gold_expanded_v1" / "train.parquet"
DEFAULT_VALIDATION = (
    ROOT_DIR / "data" / "external" / "fabsa" / "gold_expanded_v1" / "validation.parquet"
)
DEFAULT_OUTPUT_ROOT = ROOT_DIR / "artifacts" / "real_gold_models"
DEFAULT_REPORT_DIR = ROOT_DIR / "reports" / "real_gold_cycle"
THRESHOLD_GRID = tuple(float(value) for value in np.round(np.arange(0.25, 0.81, 0.05), 2))


@dataclass(frozen=True)
class Variant:
    name: str
    family: str
    c_value: float


VARIANTS = (
    Variant("word_lr_c4", "word", 4.0),
    Variant("hybrid_lr_c1", "hybrid", 1.0),
    Variant("hybrid_lr_c2", "hybrid", 2.0),
    Variant("hybrid_lr_c4", "hybrid", 4.0),
)


def _word_features() -> TfidfVectorizer:
    return TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 3),
        min_df=2,
        max_df=0.995,
        max_features=80_000,
        sublinear_tf=True,
    )


def _hybrid_features() -> FeatureUnion:
    return FeatureUnion(
        [
            ("word", _word_features()),
            (
                "char",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                    max_features=100_000,
                    sublinear_tf=True,
                ),
            ),
        ]
    )


def _model_factory(variant: Variant, *, multilabel: bool) -> Pipeline:
    features = _hybrid_features() if variant.family == "hybrid" else _word_features()
    classifier = LogisticRegression(
        C=variant.c_value,
        max_iter=2_000,
        class_weight="balanced",
        solver="liblinear",
        random_state=42,
    )
    if multilabel:
        estimator: object = OneVsRestClassifier(classifier)
    else:
        estimator = classifier
    return Pipeline([("features", features), ("clf", estimator)])


def _theme_metrics(truth: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    precisions: list[float] = []
    recalls: list[float] = []
    f1_scores: list[float] = []
    for index in range(truth.shape[1]):
        actual = truth[:, index]
        guess = predicted[:, index]
        tp = int(((actual == 1) & (guess == 1)).sum())
        fp = int(((actual == 0) & (guess == 1)).sum())
        fn = int(((actual == 1) & (guess == 0)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1_scores.append(f1)
    return {
        "exact_match": float((truth == predicted).all(axis=1).mean()),
        "precision_macro": float(np.mean(precisions)),
        "recall_macro": float(np.mean(recalls)),
        "f1_macro": float(np.mean(f1_scores)),
        "minimum_theme_f1": float(min(f1_scores)),
    }


def tune_joint_thresholds(
    probabilities: np.ndarray,
    truth: np.ndarray,
) -> tuple[np.ndarray, dict[str, float]]:
    best_thresholds: tuple[float, ...] | None = None
    best_metrics: dict[str, float] | None = None
    best_rank: tuple[float, ...] | None = None
    for thresholds in product(THRESHOLD_GRID, repeat=truth.shape[1]):
        predicted = (probabilities >= np.asarray(thresholds)).astype(int)
        metrics = _theme_metrics(truth, predicted)
        score = (
            0.50 * metrics["exact_match"]
            + 0.30 * metrics["f1_macro"]
            + 0.12 * metrics["precision_macro"]
            + 0.08 * metrics["recall_macro"]
        )
        rank = (
            score,
            metrics["exact_match"],
            metrics["minimum_theme_f1"],
            metrics["f1_macro"],
            metrics["precision_macro"],
            -sum(abs(value - 0.5) for value in thresholds),
        )
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_thresholds = thresholds
            best_metrics = {**metrics, "selection_score": float(score)}
    if best_thresholds is None or best_metrics is None:
        raise RuntimeError("Threshold tuning did not evaluate any candidates.")
    return np.asarray(best_thresholds, dtype=float), best_metrics


def _train_variant(
    variant: Variant,
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    output_dir: Path,
    *,
    train_path: Path = DEFAULT_TRAIN,
    validation_path: Path = DEFAULT_VALIDATION,
    run_name_prefix: str = "real_gold",
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    theme_model = _model_factory(variant, multilabel=True)
    theme_model.fit(_review_texts(train_df), _theme_targets(train_df))
    probabilities = np.asarray(
        theme_model.predict_proba(_review_texts(validation_df)),
        dtype=float,
    )
    thresholds, threshold_metrics = tune_joint_thresholds(
        probabilities,
        _theme_targets(validation_df),
    )
    joblib.dump(theme_model, output_dir / "themes_clf.joblib")
    np.save(output_dir / "themes_thresholds.npy", thresholds)

    sentiment_supervision: dict[str, str] = {}
    for theme in THEME_ORDER:
        texts, targets, supervision = _theme_sentiment_training_data(train_df, theme)
        sentiment_model = _model_factory(variant, multilabel=False)
        sentiment_model.fit(texts, targets)
        joblib.dump(sentiment_model, output_dir / f"sent_{theme}.joblib")
        sentiment_supervision[theme] = supervision

    tuning_report = {
        theme: {
            "threshold": round(float(thresholds[index]), 4),
            "validation_f1": None,
        }
        for index, theme in enumerate(THEME_ORDER)
    }
    manifest_path = _write_manifest(
        output_dir=output_dir,
        thresholds=thresholds,
        threshold_strategy="joint_validation_exact_f1_tuned",
        threshold_tuning_report=tuning_report,
        training_dataset=str(train_path),
        validation_dataset=str(validation_path),
        evaluation_dataset=None,
        training_rows=len(train_df),
        sentiment_supervision=sentiment_supervision,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["training"]["model_variant"] = asdict(variant)
    manifest["theme_model"]["joint_threshold_metrics"] = {
        key: round(value, 6) for key, value in threshold_metrics.items()
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    validation_metrics = _evaluate_trained_artifacts(output_dir, validation_df)
    training_seconds = time.perf_counter() - started
    summary: dict[str, object] = {
        **validation_metrics,
        "training_dataset": str(train_path),
        "training_rows": int(len(train_df)),
        "validation_dataset": str(validation_path),
        "threshold": float(np.median(thresholds)),
        "variant_name": variant.name,
        "variant_family": variant.family,
        "variant_c": variant.c_value,
        "training_seconds": round(training_seconds, 4),
        "joint_selection_score": round(float(threshold_metrics["selection_score"]), 6),
        "model_size_bytes": int(
            sum((output_dir / name).stat().st_size for name in MODEL_ARTIFACT_FILENAMES)
        ),
    }
    mlflow_result = log_training_run(
        summary,
        model_artifact_dir=output_dir,
        run_name=f"{run_name_prefix}_{variant.name}",
        register_model=False,
    )
    summary["mlflow"] = asdict(mlflow_result)
    summary["model_dir"] = str(output_dir)
    return summary


def run_benchmark(
    train_path: Path = DEFAULT_TRAIN,
    validation_path: Path = DEFAULT_VALIDATION,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    report_dir: Path = DEFAULT_REPORT_DIR,
    variants: tuple[Variant, ...] = VARIANTS,
) -> dict[str, object]:
    train_df = pd.read_parquet(train_path)
    validation_df = pd.read_parquet(validation_path)
    results = [
        _train_variant(
            variant,
            train_df,
            validation_df,
            output_root / variant.name,
            train_path=train_path,
            validation_path=validation_path,
            run_name_prefix=output_root.name,
        )
        for variant in variants
    ]
    ranked = sorted(
        results,
        key=lambda item: (
            float(item["theme_exact_match"]),
            float(item["theme_f1_macro"]),
            float(item["sentiment_macro_f1"]),
            -float(item["training_seconds"]),
        ),
        reverse=True,
    )
    report = {
        "schema_version": "1.0.0",
        "train_path": str(train_path),
        "validation_path": str(validation_path),
        "test_status": "sealed_not_evaluated",
        "variants": results,
        "selected_validation_candidate": ranked[0],
        "selection_rule": [
            "theme_exact_match descending",
            "theme_f1_macro descending",
            "sentiment_macro_f1 descending",
            "training_seconds ascending",
        ],
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "validation_benchmark.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and compare real-gold text model variants on validation only."
    )
    parser.add_argument("--train-path", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--validation-path", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument(
        "--variants",
        default=",".join(variant.name for variant in VARIANTS),
        help="Comma-separated variant names.",
    )
    args = parser.parse_args()
    requested = {name.strip() for name in args.variants.split(",") if name.strip()}
    variants = tuple(variant for variant in VARIANTS if variant.name in requested)
    unknown = requested.difference(variant.name for variant in VARIANTS)
    if unknown or not variants:
        parser.error(f"Unknown or empty variants: {sorted(unknown or requested)}")
    print(
        json.dumps(
            run_benchmark(
                train_path=args.train_path,
                validation_path=args.validation_path,
                output_root=args.output_root,
                report_dir=args.report_dir,
                variants=variants,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
