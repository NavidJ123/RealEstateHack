"""CSV-backed repository implementation."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from ..utils.io import load_csv


class CSVRepository:
    def __init__(self) -> None:
        self._properties = load_csv("properties.csv")
        self._market_stats = load_csv("market_stats.csv")
        self._comps = load_csv("comps.csv")

    def list_properties(self, zipcode: Optional[str] = None, limit: Optional[int] = 24) -> List[Dict]:
        df = self._properties
        if zipcode:
            df = df[df["zipcode"].astype(str) == str(zipcode)]
        df = df.sort_values("current_est_value", ascending=False)
        if limit is not None:
            df = df.head(limit)
        df = df.where(pd.notnull(df), None)
        records = df.to_dict("records")
        # Convert zipcode to string
        for record in records:
            if record.get("zipcode") is not None:
                record["zipcode"] = str(int(record["zipcode"]))
        return records

    def get_property(self, property_id: str) -> Optional[Dict]:
        df = self._properties
        row = df[df["id"] == property_id]
        if row.empty:
            return None
        record = row.iloc[0].to_dict()
        record = {k: (None if pd.isna(v) else v) for k, v in record.items()}
        # Convert zipcode to string
        if record.get("zipcode") is not None:
            record["zipcode"] = str(int(record["zipcode"]))
        return record

    def get_market_stats(self, zipcode: str, start: Optional[date] = None, end: Optional[date] = None) -> List[Dict]:
        df = self._market_stats
        subset = df[df["zipcode"].astype(str) == str(zipcode)].copy()
        subset["date"] = pd.to_datetime(subset["date"])
        if start:
            subset = subset[subset["date"] >= pd.Timestamp(start)]
        if end:
            subset = subset[subset["date"] <= pd.Timestamp(end)]
        subset = subset.sort_values("date")
        subset["date"] = subset["date"].dt.date.astype(str)
        subset = subset.where(pd.notnull(subset), None)
        return subset.to_dict("records")

    def get_comps(self, property_id: str) -> List[Dict]:
        df = self._comps
        subset = df[df["property_id"] == property_id].copy()
        subset = subset.where(pd.notnull(subset), None)
        return subset.to_dict("records")

