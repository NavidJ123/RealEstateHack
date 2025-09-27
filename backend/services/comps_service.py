"""Comparable sales selection logic."""

from __future__ import annotations

import pandas as pd

from ..models.analysis import Comp
from ..utils.logging import get_logger

LOGGER = get_logger("services.comps")


class CompsService:
    def __init__(self, repository):
        self.repository = repository

    def get_ranked_comps(self, property_obj: dict, limit: int = 6) -> list[Comp]:
        records = self.repository.get_comps(property_obj["id"])
        if not records:
            return []

        df = pd.DataFrame(records)
        if df.empty:
            return []

        df["sale_date"] = pd.to_datetime(df.get("sale_date"), errors="coerce")
        df["sqft"] = pd.to_numeric(df.get("sqft"), errors="coerce")
        df["sale_price"] = pd.to_numeric(df.get("sale_price"), errors="coerce")
        df["distance_mi"] = pd.to_numeric(df.get("distance_mi"), errors="coerce")
        df = df.dropna(subset=["sale_date"])
        if df.empty:
            return []

        sqft_target = property_obj.get("sqft")
        if not sqft_target or pd.isna(sqft_target):
            sqft_target = df["sqft"].median()
        if not sqft_target or pd.isna(sqft_target):
            sqft_target = float(df["sqft"].fillna(0).median() or 1000)

        sqft_lower = sqft_target * 0.75
        sqft_upper = sqft_target * 1.25
        df = df[df["sqft"].fillna(sqft_target).between(sqft_lower, sqft_upper)]
        cutoff = pd.Timestamp.today() - pd.DateOffset(years=5)
        df = df[df["sale_date"] >= cutoff]
        if df.empty:
            return []

        df["recency_score"] = 1 / (1 + (pd.Timestamp.today() - df["sale_date"]).dt.days / 365)
        df["distance_score"] = 1 / (1 + df["distance_mi"].fillna(0.5))
        df["rank_score"] = 0.6 * df["recency_score"] + 0.4 * df["distance_score"]
        df = df.sort_values("rank_score", ascending=False).head(limit)

        comps: list[Comp] = []
        for _, row in df.iterrows():
            comps.append(
                Comp(
                    comp_id=str(row.get("comp_id")),
                    property_id=str(row.get("property_id")),
                    address=str(row.get("address")),
                    sale_price=float(row.get("sale_price", 0.0)),
                    sale_date=row["sale_date"].date().isoformat(),
                    sqft=int(row["sqft"]) if pd.notna(row.get("sqft")) else None,
                    distance_mi=float(row.get("distance_mi")) if pd.notna(row.get("distance_mi")) else None,
                )
            )
        return comps

