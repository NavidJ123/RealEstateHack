"""Pydantic models representing property listings."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PropertyCard(BaseModel):
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
    score: Optional[int] = None
    decision: Optional[str] = None


class PropertyListResponse(BaseModel):
    items: List[PropertyCard]
    total: int

