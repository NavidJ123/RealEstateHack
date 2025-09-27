"""Pydantic schemas for property analysis responses."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator



class AnalysisMetrics(BaseModel):
    current_est_value: float
    appreciation_5y: Optional[float]
    cap_rate_est: Optional[float]
    rent_growth_3y: Optional[float]
    market_strength: Optional[float]
    zip_income: Optional[float] = None
    zip_vacancy_rate: Optional[float] = None


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


class AnalysisResponse(BaseModel):
    property_id: str
    address: str
    zip: str
    metrics: AnalysisMetrics
    score: int
    decision: str
    zip_trends: ZipTrends
    comps: List[Comp]
    provenance: Provenance

    @validator("decision")
    def validate_decision(cls, value: str) -> str:
        allowed = {"Buy", "Hold", "Sell"}
        if value not in allowed:
            raise ValueError(f"decision must be one of {allowed}")
        return value


class AnalyzeRequest(BaseModel):
    id: Optional[str]
    address: Optional[str]

    @validator("address")
    def strip_address(cls, value: Optional[str]) -> Optional[str]:
        if value:
            return value.strip()
        return value


class BrokerRequest(BaseModel):
    analysis_json: AnalysisResponse
    question: Optional[str]


class BrokerMessage(BaseModel):
    role: str
    content: str


class BrokerResponse(BaseModel):
    messages: List[BrokerMessage]


class ExportResponse(BaseModel):
    filename: str
    content_type: str

