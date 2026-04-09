from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


THEME_COLUMNS = {
    "livraison": "theme_livraison",
    "sav": "theme_sav",
    "produit": "theme_produit",
}


@dataclass
class EvaluationSummary:
    rows: int
    sentiment_accuracy: float
    theme_exact_match: float
    theme_precision_macro: float
    theme_recall_macro: float
    backend_name: str

    def to_dict(self) -> Dict:
        return {
            "rows": self.rows,
            "sentiment_accuracy": self.sentiment_accuracy,
            "theme_exact_match": self.theme_exact_match,
            "theme_precision_macro": self.theme_precision_macro,
            "theme_recall_macro": self.theme_recall_macro,
            "backend_name": self.backend_name,
        }


def _safe_div(num: float, den: float) -> float:
    return round(num / den, 4) if den else 0.0


def evaluate_predictions(df: pd.DataFrame, backend_name: str) -> EvaluationSummary:
    working = df.copy()
    rows = len(working)

    sentiment_accuracy = 0.0
    if "sentiment_label" in working.columns and "global_sentiment" in working.columns:
        comparable = working[working["sentiment_label"].astype(str) != "unknown"]
        if len(comparable):
            sentiment_accuracy = round(
                (comparable["sentiment_label"].astype(str) == comparable["global_sentiment"].astype(str)).mean(),
                4,
            )

    exact_match_hits = 0
    precisions: List[float] = []
    recalls: List[float] = []
    for _, row in working.iterrows():
        truth = [int(row.get(column, 0)) for column in THEME_COLUMNS.values()]
        pred = [int(row.get(f"theme_{theme}", 0)) for theme in THEME_COLUMNS]
        if truth == pred:
            exact_match_hits += 1

    for theme, column in THEME_COLUMNS.items():
        y_true = working[column].astype(int)
        y_pred = working[f"theme_{theme}"].astype(int)
        tp = int(((y_true == 1) & (y_pred == 1)).sum())
        fp = int(((y_true == 0) & (y_pred == 1)).sum())
        fn = int(((y_true == 1) & (y_pred == 0)).sum())
        precisions.append(_safe_div(tp, tp + fp))
        recalls.append(_safe_div(tp, tp + fn))

    return EvaluationSummary(
        rows=rows,
        sentiment_accuracy=sentiment_accuracy,
        theme_exact_match=round(exact_match_hits / rows, 4) if rows else 0.0,
        theme_precision_macro=round(sum(precisions) / len(precisions), 4) if precisions else 0.0,
        theme_recall_macro=round(sum(recalls) / len(recalls), 4) if recalls else 0.0,
        backend_name=backend_name,
    )
