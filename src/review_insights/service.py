from __future__ import annotations

from typing import Dict

import pandas as pd

from .dataset import flatten_results
from .engine import analyze_review
from .evaluation import evaluate_predictions
from .model_backend import analyze_with_project_models, load_project_model_artifacts
from .monitoring import MonitoringStore
from .schemas import AnalyzeReviewResponse
from .settings import get_settings


class ReviewAnalysisService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.backend_name = "heuristic_rules_v1"
        self.model_source = self.settings.model_source
        self._artifacts = None
        self.monitoring = MonitoringStore()
        self._load_real_models_if_available()

    def _load_real_models_if_available(self) -> None:
        try:
            self._artifacts = load_project_model_artifacts(self.settings.models_dir)
            self.backend_name = "project_models_v1"
        except Exception:
            self._artifacts = None
            self.backend_name = "heuristic_rules_v1"

    def analyze(self, review_text: str, review_id: str, threshold: float | None = None) -> AnalyzeReviewResponse:
        effective_threshold = threshold if threshold is not None else self.settings.theme_threshold
        if self._artifacts is not None:
            result = analyze_with_project_models(
                review_text=review_text,
                review_id=review_id,
                artifacts=self._artifacts,
                threshold_override=effective_threshold,
            )
        else:
            result = analyze_review(review_text, review_id=review_id, threshold=effective_threshold)
        self.monitoring.record_prediction(result, self.backend_name)
        return AnalyzeReviewResponse(**result)

    def analyze_dataframe(self, df: pd.DataFrame, threshold: float | None = None) -> pd.DataFrame:
        rows = []
        for _, row in df.iterrows():
            review_text = f"{row.get('review_title', '')} {row.get('review_body', '')}".strip()
            result = self.analyze(
                review_text=review_text,
                review_id=str(row.get("review_id", "manual_review")),
                threshold=threshold,
            ).model_dump()
            merged: Dict = dict(row)
            merged.update(result)
            rows.append(merged)
        return pd.DataFrame(rows)

    def export_dataframe(self, df: pd.DataFrame, threshold: float | None = None) -> pd.DataFrame:
        return flatten_results(self.analyze_dataframe(df, threshold=threshold))

    def evaluate_dataframe(self, df: pd.DataFrame, threshold: float | None = None) -> Dict:
        predictions = self.analyze_dataframe(df, threshold=threshold)
        summary = evaluate_predictions(predictions, backend_name=self.backend_name)
        return {
            "summary": summary.to_dict(),
            "rows_preview": flatten_results(predictions.head(20)).to_dict(orient="records"),
        }

    def get_monitoring_metrics(self) -> Dict:
        return self.monitoring.snapshot()


def get_review_analysis_service() -> ReviewAnalysisService:
    return ReviewAnalysisService()
