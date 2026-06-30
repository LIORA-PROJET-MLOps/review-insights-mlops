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


class ModelProvenance(BaseModel):
    inference_backend: str
    theme_backend: str
    theme_model_source: str
    theme_model_revision: str
    artifact_set_version: str
    sentiment_backend: str
    sentiment_model_id: Optional[str] = None
    sentiment_model_revision: Optional[str] = None


class AnalyzeReviewResponse(BaseModel):
    review_id: str
    review_text: str
    global_sentiment: str
    score_global: float
    positive_terms: List[str] = Field(default_factory=list)
    negative_terms: List[str] = Field(default_factory=list)
    themes_detected: List[str] = Field(default_factory=list)
    needs_human_review: bool
    sentiment_conflict: bool = False
    sentiment_conflict_themes: List[str] = Field(default_factory=list)
    provenance: ModelProvenance
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
    model_revision: str
    artifact_set_version: str
    models_manifest_present: bool
    protected_endpoints: bool
    security_profile: str
    security_warnings: List[str] = Field(default_factory=list)
    model_load_error: Optional[str] = None
    sentiment_backend: str
    sentiment_model_id: Optional[str] = None
    sentiment_model_revision: Optional[str] = None
    sentiment_load_error: Optional[str] = None
    prediction_event_store_enabled: bool = False


class MetricsResponse(BaseModel):
    total_requests: int
    human_review_requests: int
    human_review_rate: float
    sentiment_conflict_requests: int = 0
    sentiment_conflict_rate: float = 0.0
    inference_latency_ms_avg: float
    inference_latency_ms_p50: float
    inference_latency_ms_p95: float
    sentiment_distribution: dict = Field(default_factory=dict)
    theme_distribution: dict = Field(default_factory=dict)
    backend_distribution: dict = Field(default_factory=dict)
    sentiment_backend_distribution: dict = Field(default_factory=dict)
    http_requests_total: int = 0
    http_error_requests: int = 0
    http_error_rate: float = 0.0
    http_latency_ms_avg: float = 0.0
    http_latency_ms_p50: float = 0.0
    http_latency_ms_p95: float = 0.0
    http_status_distribution: dict = Field(default_factory=dict)
    http_endpoint_distribution: dict = Field(default_factory=dict)


class EvaluationResponse(BaseModel):
    summary: dict
    rows_preview: List[dict] = Field(default_factory=list)


class HumanFeedbackRequest(BaseModel):
    review_id: str = Field(min_length=1)
    theme: str
    corrected_theme_present: int
    corrected_sentiment: str
    reviewer: str = "anonymous"
    notes: str = ""
    source: str = "manual"
