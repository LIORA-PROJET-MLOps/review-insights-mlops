from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ThemeInsight(BaseModel):
    topic: str
    sentiment: str
    confidence: float
    evidence: List[str] = Field(default_factory=list)
    actionable_text: str


class AnalyzeReviewRequest(BaseModel):
    review_text: str = Field(min_length=1, max_length=10000)
    review_id: str = Field(default="manual_review")
    threshold: Optional[float] = None


class AnalyzeReviewResponse(BaseModel):
    review_id: str
    review_text: str
    global_sentiment: str
    score_global: float
    positive_terms: List[str] = Field(default_factory=list)
    negative_terms: List[str] = Field(default_factory=list)
    themes_detected: List[str] = Field(default_factory=list)
    needs_human_review: bool
    insights: List[ThemeInsight] = Field(default_factory=list)
    theme_livraison: int
    sent_livraison: Optional[str] = None
    conf_livraison: float
    evidence_livraison: List[str] = Field(default_factory=list)
    theme_sav: int
    sent_sav: Optional[str] = None
    conf_sav: float
    evidence_sav: List[str] = Field(default_factory=list)
    theme_produit: int
    sent_produit: Optional[str] = None
    conf_produit: float
    evidence_produit: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_version: str
    environment: str
    inference_backend: str
    model_source: str
    models_manifest_present: bool
    protected_endpoints: bool


class MetricsResponse(BaseModel):
    total_requests: int
    human_review_requests: int
    human_review_rate: float
    sentiment_distribution: dict = Field(default_factory=dict)
    theme_distribution: dict = Field(default_factory=dict)
    backend_distribution: dict = Field(default_factory=dict)


class EvaluationResponse(BaseModel):
    summary: dict
    rows_preview: List[dict] = Field(default_factory=list)
