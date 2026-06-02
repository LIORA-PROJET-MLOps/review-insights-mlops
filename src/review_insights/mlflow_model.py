from __future__ import annotations

from typing import Any

import pandas as pd

try:
    from mlflow.pyfunc import PythonModel
except Exception:
    PythonModel = object


class ReviewInsightsPyFuncModel(PythonModel):
    def load_context(self, context: Any) -> None:
        from .model_backend import load_project_model_artifacts

        self.artifacts = load_project_model_artifacts(context.artifacts["model_dir"], source="local")

    def predict(self, context: Any, model_input: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
        from .model_backend import analyze_with_project_models

        rows = []
        for idx, row in model_input.reset_index(drop=True).iterrows():
            review_id = str(row.get("review_id", f"mlflow_review_{idx + 1}"))
            if "review_text" in row:
                review_text = str(row.get("review_text", ""))
            else:
                review_text = f"{row.get('review_title', '')} {row.get('review_body', '')}".strip()
            rows.append(
                analyze_with_project_models(
                    review_text=review_text,
                    review_id=review_id,
                    artifacts=self.artifacts,
                )
            )
        return pd.DataFrame(rows)
