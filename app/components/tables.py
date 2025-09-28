"""Tabular components for stats and comps."""

from __future__ import annotations

from typing import List, Optional

import pandas as pd
import streamlit as st


def _fmt_percent(value: Optional[float]) -> str:
    if value is None:
        return "Insufficient data"
    return f"{value * 100:.1f}%"


def _fmt_currency(value: Optional[float]) -> str:
    if value is None:
        return "Insufficient data"
    return f"${value:,.0f}"


def _fmt_number(value: Optional[float], precision: int = 0) -> str:
    if value is None:
        return "Insufficient data"
    return f"{value:.{precision}f}"


def render_metrics_table(metrics: dict) -> None:
    data = [
        {"Metric": "Current Value", "Value": _fmt_currency(metrics.get("current_est_value"))},
        {"Metric": "Cap Rate (Market)", "Value": _fmt_percent(metrics.get("cap_rate_market_now"))},
        {"Metric": "Projected Rent Growth (12m)", "Value": _fmt_percent(metrics.get("rent_growth_proj_12m"))},
        {"Metric": "Median Income", "Value": _fmt_currency(metrics.get("income_median_now"))},
        {"Metric": "Income Growth (3y)", "Value": _fmt_percent(metrics.get("income_growth_3y"))},
        {"Metric": "Vacancy Rate", "Value": _fmt_percent(metrics.get("vacancy_rate_now"))},
        {"Metric": "Days on Market", "Value": _fmt_number(metrics.get("dom_now"))},
        {"Metric": "Affordability Index", "Value": _fmt_percent(metrics.get("affordability_index"))},
        {"Metric": "Rent-to-Income", "Value": _fmt_percent(metrics.get("rent_to_income_ratio"))},
        {"Metric": "Market Strength Index", "Value": _fmt_number(metrics.get("market_strength_index"), precision=2)},
        {"Metric": "Appreciation (5y)", "Value": _fmt_percent(metrics.get("appreciation_5y"))},
    ]
    df = pd.DataFrame(data)
    st.dataframe(df, hide_index=True, width="stretch")


def render_comps_table(comps: List[dict]) -> None:
    if not comps:
        st.info("No comparable sales available for this property.")
        return
    df = pd.DataFrame(comps)
    df = df.rename(
        columns={
            "address": "Address",
            "sale_price": "Sale Price",
            "sale_date": "Sale Date",
            "sqft": "Sqft",
            "distance_mi": "Distance (mi)",
        }
    )
    if "Sale Price" in df:
        df["Sale Price"] = df["Sale Price"].apply(lambda x: f"${x:,.0f}")
    if "Sqft" in df:
        df["Sqft"] = df["Sqft"].fillna("—")
    if "Distance (mi)" in df:
        df["Distance (mi)"] = df["Distance (mi)"].apply(lambda x: f"{x:.2f}" if x is not None else "—")
    st.dataframe(df[["Address", "Sale Date", "Sale Price", "Sqft", "Distance (mi)"]], hide_index=True, width="stretch")
