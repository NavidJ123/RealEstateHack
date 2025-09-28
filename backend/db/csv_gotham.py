
"""Helpers for loading Gotham CSV datasets for market analytics."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

DATA_DIR = Path(os.getenv("GOTHAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

MARKET_STATS_FILE = DATA_DIR / "x_ai_prop_market_stats_gotham.csv"


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing Gotham CSV: {path}")
    df = pd.read_csv(path)
    return df


@lru_cache(maxsize=1)
def _market_stats() -> pd.DataFrame:
    df = _load_csv(MARKET_STATS_FILE)
    # Normalise column names
    df = df.rename(
        columns={
            "month": "date",
            "avg_eff_rent_usd": "median_rent",
            "market_cap_rate": "cap_rate_market_now",
        }
    )
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def get_market_series(submarket: str, months: int = 60) -> List[Dict[str, Optional[float]]]:
    df = _market_stats()
    mask = df["submarket_name"].astype(str).str.lower() == str(submarket).lower()
    subset = df[mask].copy()
    if subset.empty and str(submarket).isdigit():
        mask = df.get("zip", df.get("zipcode", pd.Series([]))).astype(str) == str(submarket)
        subset = df[mask].copy()
    subset = subset.sort_values("date")
    if months:
        subset = subset.tail(months)
    numeric_cols = [
        "median_rent",
        "rent_yoy",
        "vacancy_rate",
        "availability_rate",
        "absorption_units",
        "deliveries_units",
        "under_construction_units",
        "pipeline_12m_units",
        "sale_price_per_unit_usd",
        "cap_rate_market_now",
        "transactions_count",
    ]
    for col in numeric_cols:
        if col in subset.columns:
            subset[col] = pd.to_numeric(subset[col], errors="coerce")
    records: List[Dict[str, Optional[float]]] = []
    for _, row in subset.iterrows():
        record: Dict[str, Optional[float]] = {
            "submarket": row.get("submarket_name"),
            "date": row.get("date").date().isoformat() if pd.notna(row.get("date")) else None,
            "median_rent": row.get("median_rent"),
            "rent_yoy": row.get("rent_yoy"),
            "vacancy_rate": row.get("vacancy_rate"),
            "cap_rate_market_now": row.get("cap_rate_market_now"),
            "availability_rate": row.get("availability_rate"),
            "pipeline_12m_units": row.get("pipeline_12m_units"),
            "sale_price_per_unit_usd": row.get("sale_price_per_unit_usd"),
        }
        records.append(record)
    return records


def get_distribution_dataset() -> List[Dict[str, Optional[float]]]:
    df = _market_stats()
    numeric_cols = [
        "cap_rate_market_now",
        "rent_yoy",
        "vacancy_rate",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    dataset: List[Dict[str, Optional[float]]] = []
    for _, row in df.iterrows():
        dataset.append(
            {
                "cap_rate_market_now": row.get("cap_rate_market_now"),
                "rent_growth_proj_12m": row.get("rent_yoy"),
                "market_strength_index": _compute_strength_proxy(row),
                "dscr_proj": None,
            }
        )
    return dataset


def _compute_strength_proxy(row: pd.Series) -> Optional[float]:
    rent_yoy = row.get("rent_yoy")
    vacancy = row.get("vacancy_rate")
    if pd.isna(rent_yoy) and pd.isna(vacancy):
        return None
    rent_component = 0.0 if pd.isna(rent_yoy) else (float(rent_yoy) - 0.02) / 0.02
    vacancy_component = 0.0 if pd.isna(vacancy) else -(float(vacancy) - 0.06) / 0.03
    return rent_component + vacancy_component
