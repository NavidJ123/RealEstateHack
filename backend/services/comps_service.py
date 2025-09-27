"""Comparable sales selection logic."""

from __future__ import annotations

import pandas as pd

from ..models.property import Comp, Property
from ..utils.logging import get_logger

LOGGER = get_logger("services.comps")


class CompsService:
    def __init__(self, repository):
        self.repository = repository

    def get_ranked_comps(self, property_obj: Property, limit: int = 6) -> list[Comp]:
        df = self.repository.get_comps(property_obj.id)
        if df.empty:
            return []
        df = df.copy()
        df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
        df = df.dropna(subset=["sale_date"])

        sqft = property_obj.sqft or df["sqft"].median()
        sqft_lower = sqft * 0.75
        sqft_upper = sqft * 1.25
        df = df[(df["sqft"].fillna(sqft).between(sqft_lower, sqft_upper))]
        cutoff = pd.Timestamp.today() - pd.DateOffset(years=5)
        df = df[df["sale_date"] >= cutoff]
        if df.empty:
            return []

        df["recency_score"] = 1 / (1 + (pd.Timestamp.today() - df["sale_date"]).dt.days / 365)
        df["distance_score"] = 1 / (1 + df["distance_mi"].fillna(0.5))
        df["rank_score"] = 0.6 * df["recency_score"] + 0.4 * df["distance_score"]
        df = df.sort_values("rank_score", ascending=False).head(limit)

        return [
            Comp(
                comp_id=row["comp_id"],
                property_id=row["property_id"],
                address=row["address"],
                sale_price=float(row["sale_price"]),
                sale_date=row["sale_date"].date().isoformat(),
                sqft=int(row["sqft"]) if pd.notna(row["sqft"]) else None,
                distance_mi=float(row["distance_mi"]) if pd.notna(row["distance_mi"]) else None,
            )
            for _, row in df.iterrows()
        ]

