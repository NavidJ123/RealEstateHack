"""Pydantic models representing property domain objects."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Property(BaseModel):
    id: str
    address: str
    zipcode: str = Field(..., min_length=5, max_length=5)
    sqft: Optional[int]
    type: Optional[str]
    last_sale_price: Optional[float]
    last_sale_date: Optional[str]
    current_est_value: Optional[float]
    est_monthly_rent: Optional[float]
    image_url: Optional[str]


class MarketStat(BaseModel):
    zipcode: str
    date: str
    median_price: float
    median_rent: float
    inventory: Optional[float]
    dom: Optional[float]
    income: Optional[float]
    vacancy_rate: Optional[float]


class Comp(BaseModel):
    comp_id: str
    property_id: str
    address: str
    sale_price: float
    sale_date: str
    sqft: Optional[int]
    distance_mi: Optional[float]


class PropertyListResponse(BaseModel):
    items: List[Property]
    total: int

