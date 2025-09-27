"""Pydantic schemas for property analysis responses."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator

from .property import Comp


class AnalysisMetrics(BaseModel):
    current_est_value: float
    appreciation_5y: Optional[float]
    cap_rate_est: Optional[float]
    rent_growth_3y: Optional[float]
    market_strength: Optional[float]
    zip_income: Optional[float] = None
    zip_vacancy_rate: Optional[float] = None


class ZipTrendPoint(BaseModel):
    date: str
    value: float
    lower: float | None = None
    upper: float | None = None


class ZipTrends(BaseModel):
    price_history: List[ZipTrendPoint]
    rent_history: List[ZipTrendPoint]
    price_forecast: List[ZipTrendPoint]
    rent_forecast: List[ZipTrendPoint]


class Provenance(BaseModel):
    market_stats: Optional[str]
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Analysis(BaseModel):
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
    analysis_json: Analysis
    question: Optional[str]


class BrokerMessage(BaseModel):
    role: str
    content: str


class BrokerResponse(BaseModel):
    messages: List[BrokerMessage]


class ExportResponse(BaseModel):
    filename: str
    content_type: str

