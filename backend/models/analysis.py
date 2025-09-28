"""Pydantic schemas for property analysis responses."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AnalysisMetrics(BaseModel):
    current_est_value: Optional[float]
    cap_rate_market_now: Optional[float]
    rent_growth_proj_12m: Optional[float]
    income_median_now: Optional[float]
    income_growth_3y: Optional[float]
    vacancy_rate_now: Optional[float]
    dom_now: Optional[float]
    affordability_index: Optional[float]
    rent_to_income_ratio: Optional[float]
    market_strength_index: Optional[float]
    dscr_proj: Optional[float]
    appreciation_5y: Optional[float]


class TrendPoint(BaseModel):
    date: str
    value: float
    lower: Optional[float] = None
    upper: Optional[float] = None


class ZipTrends(BaseModel):
    price_history: List[TrendPoint]
    rent_history: List[TrendPoint]
    price_forecast: List[TrendPoint]
    rent_forecast: List[TrendPoint]


class Provenance(BaseModel):
    sources: List[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Comp(BaseModel):
    comp_id: str
    property_id: str
    address: str
    sale_price: float
    sale_date: str
    sqft: Optional[int]
    distance_mi: Optional[float]


class FactorPayload(BaseModel):
    name: str
    key: str
    weight: float
    value: Optional[float]
    norm: Optional[float]
    contrib: float


class Explanations(BaseModel):
    factors: List[FactorPayload]
    fallback_total_score: int


class AnalysisResponse(BaseModel):
    property_id: str
    address: str
    zip: str
    metrics: AnalysisMetrics
    score: Optional[int] = None
    decision: Optional[str] = None
    explanations: Explanations
    zip_trends: ZipTrends
    comps: List[Comp]
    provenance: Provenance


class AnalyzeRequest(BaseModel):
    id: Optional[str]
    address: Optional[str]


class ScoreRequest(BaseModel):
    analysis_json: AnalysisResponse


class Contributor(BaseModel):
    name: str
    effect: str


class ScoreResponse(BaseModel):
    score: int
    decision: str
    rationale: str
    top_contributors: List[Contributor]


class BrokerRequest(BaseModel):
    mode: Literal["thesis", "qa"] = "qa"
    analysis_json: AnalysisResponse
    question: Optional[str]


class BrokerMessage(BaseModel):
    role: str
    content: str


class BrokerResponse(BaseModel):
    messages: List[BrokerMessage]


class BrokerQAResponse(BaseModel):
    text: str


class ExportResponse(BaseModel):
    filename: str
    content_type: str

