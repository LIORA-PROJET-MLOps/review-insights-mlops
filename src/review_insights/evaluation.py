from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


THEME_COLUMNS = {
    "livraison": "theme_livraison",
    "sav": "theme_sav",
    "produit": "theme_produit",
}
SENTIMENT_LABELS = ("negative", "neutral", "positive")


@dataclass
class EvaluationSummary:
    rows: int
    sentiment_accuracy: float
    sentiment_macro_precision: float
    sentiment_macro_recall: float
    sentiment_macro_f1: float
    sentiment_evaluated_rows: int
    sentiment_per_class: Dict[str, Dict[str, float | int]]
    sentiment_confusion_matrix: Dict[str, Dict[str, int]]
    theme_exact_match: float
    theme_precision_macro: float
    theme_recall_macro: float
    theme_f1_macro: float
    theme_metrics: Dict[str, Dict[str, float | int]]
    human_review_rate: float
    backend_name: str

    def to_dict(self) -> Dict:
        return {
            "rows": self.rows,
            "sentiment_accuracy": self.sentiment_accuracy,
            "sentiment_macro_precision": self.sentiment_macro_precision,
            "sentiment_macro_recall": self.sentiment_macro_recall,
            "sentiment_macro_f1": self.sentiment_macro_f1,
            "sentiment_evaluated_rows": self.sentiment_evaluated_rows,
            "sentiment_per_class": self.sentiment_per_class,
            "sentiment_confusion_matrix": self.sentiment_confusion_matrix,
            "theme_exact_match": self.theme_exact_match,
            "theme_precision_macro": self.theme_precision_macro,
            "theme_recall_macro": self.theme_recall_macro,
            "theme_f1_macro": self.theme_f1_macro,
            "theme_metrics": self.theme_metrics,
            "human_review_rate": self.human_review_rate,
            "backend_name": self.backend_name,
        }


def _safe_div(num: float, den: float) -> float:
    return round(num / den, 4) if den else 0.0


def _f1(precision: float, recall: float) -> float:
    return _safe_div(2 * precision * recall, precision + recall)


def _macro_average(items: List[Dict[str, float | int]], key: str) -> float:
    active_items = [
        item
        for item in items
        if int(item.get("support", 0)) > 0 or int(item.get("predicted", 0)) > 0
    ]
    if not active_items:
        return 0.0
    return round(sum(float(item[key]) for item in active_items) / len(active_items), 4)


def _classification_report(
    y_true: List[str],
    y_pred: List[str],
    labels: tuple[str, ...],
) -> tuple[Dict[str, Dict[str, float | int]], Dict[str, Dict[str, int]], float, float, float]:
    observed_labels = tuple(sorted(set(labels) | set(y_true) | set(y_pred)))
    per_class: Dict[str, Dict[str, float | int]] = {}
    confusion = {
        true_label: {pred_label: 0 for pred_label in observed_labels}
        for true_label in observed_labels
    }

    for true_label, pred_label in zip(y_true, y_pred):
        confusion.setdefault(true_label, {label: 0 for label in observed_labels})
        if pred_label not in confusion[true_label]:
            confusion[true_label][pred_label] = 0
        confusion[true_label][pred_label] += 1

    for label in observed_labels:
        tp = sum(1 for truth, pred in zip(y_true, y_pred) if truth == label and pred == label)
        fp = sum(1 for truth, pred in zip(y_true, y_pred) if truth != label and pred == label)
        fn = sum(1 for truth, pred in zip(y_true, y_pred) if truth == label and pred != label)
        support = sum(1 for truth in y_true if truth == label)
        predicted = sum(1 for pred in y_pred if pred == label)
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": _f1(precision, recall),
            "support": support,
            "predicted": predicted,
        }

    metrics = list(per_class.values())
    return (
        per_class,
        confusion,
        _macro_average(metrics, "precision"),
        _macro_average(metrics, "recall"),
        _macro_average(metrics, "f1"),
    )


def _binary_report(y_true: pd.Series, y_pred: pd.Series) -> Dict[str, float | int]:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    support = int((y_true == 1).sum())
    predicted = int((y_pred == 1).sum())
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    return {
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "support": support,
        "predicted": predicted,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def evaluate_predictions(df: pd.DataFrame, backend_name: str) -> EvaluationSummary:
    working = df.copy()
    rows = len(working)

    sentiment_accuracy = 0.0
    sentiment_evaluated_rows = 0
    sentiment_per_class: Dict[str, Dict[str, float | int]] = {}
    sentiment_confusion_matrix: Dict[str, Dict[str, int]] = {}
    sentiment_macro_precision = 0.0
    sentiment_macro_recall = 0.0
    sentiment_macro_f1 = 0.0
    if "sentiment_label" in working.columns and "global_sentiment" in working.columns:
        true_sentiment = working["sentiment_label"].astype(str).str.lower().str.strip()
        pred_sentiment = working["global_sentiment"].astype(str).str.lower().str.strip()
        comparable = working[true_sentiment != "unknown"].copy()
        if len(comparable):
            comparable_true = true_sentiment.loc[comparable.index]
            comparable_pred = pred_sentiment.loc[comparable.index]
            sentiment_evaluated_rows = int(len(comparable))
            sentiment_accuracy = round(
                (comparable_true == comparable_pred).mean(),
                4,
            )
            (
                sentiment_per_class,
                sentiment_confusion_matrix,
                sentiment_macro_precision,
                sentiment_macro_recall,
                sentiment_macro_f1,
            ) = _classification_report(
                comparable_true.tolist(),
                comparable_pred.tolist(),
                SENTIMENT_LABELS,
            )

    exact_match_hits = 0
    theme_metrics: Dict[str, Dict[str, float | int]] = {}
    for _, row in working.iterrows():
        truth = [
            int(row.get(f"true_{column}", row.get(column, 0)))
            for column in THEME_COLUMNS.values()
        ]
        pred = [int(row.get(f"theme_{theme}", 0)) for theme in THEME_COLUMNS]
        if truth == pred:
            exact_match_hits += 1

    for theme, column in THEME_COLUMNS.items():
        truth_column = f"true_{column}" if f"true_{column}" in working.columns else column
        y_true = working[truth_column].astype(int)
        y_pred = working[f"theme_{theme}"].astype(int)
        theme_metrics[theme] = _binary_report(y_true, y_pred)

    theme_metric_values = list(theme_metrics.values())
    human_review_rate = 0.0
    if "needs_human_review" in working.columns and rows:
        human_review_rate = round(working["needs_human_review"].astype(bool).mean(), 4)

    return EvaluationSummary(
        rows=rows,
        sentiment_accuracy=sentiment_accuracy,
        sentiment_macro_precision=sentiment_macro_precision,
        sentiment_macro_recall=sentiment_macro_recall,
        sentiment_macro_f1=sentiment_macro_f1,
        sentiment_evaluated_rows=sentiment_evaluated_rows,
        sentiment_per_class=sentiment_per_class,
        sentiment_confusion_matrix=sentiment_confusion_matrix,
        theme_exact_match=round(exact_match_hits / rows, 4) if rows else 0.0,
        theme_precision_macro=round(sum(float(item["precision"]) for item in theme_metric_values) / len(theme_metric_values), 4)
        if theme_metric_values
        else 0.0,
        theme_recall_macro=round(sum(float(item["recall"]) for item in theme_metric_values) / len(theme_metric_values), 4)
        if theme_metric_values
        else 0.0,
        theme_f1_macro=round(sum(float(item["f1"]) for item in theme_metric_values) / len(theme_metric_values), 4)
        if theme_metric_values
        else 0.0,
        theme_metrics=theme_metrics,
        human_review_rate=human_review_rate,
        backend_name=backend_name,
    )
