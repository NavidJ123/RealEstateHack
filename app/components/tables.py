"""Tabular components for stats and comps."""

from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st


def _fmt_percent(value):
    if value is None:
        return "Insufficient data"
    return f"{value * 100:.1f}%"


def render_metrics_table(metrics: dict) -> None:
    data = [
        {"Metric": "Current Value", "Value": f"${metrics.get('current_est_value', 0):,.0f}"},
        {"Metric": "Appreciation (5y)", "Value": _fmt_percent(metrics.get("appreciation_5y"))},
        {"Metric": "Cap Rate", "Value": _fmt_percent(metrics.get("cap_rate_est"))},
        {"Metric": "Rent Growth (3y)", "Value": _fmt_percent(metrics.get("rent_growth_3y"))},
        {
            "Metric": "Market Strength",
            "Value": f"{metrics.get('market_strength', 0):+.2f}" if metrics.get("market_strength") is not None else "Insufficient data",
        },
        {
            "Metric": "Median Income",
            "Value": f"${metrics.get('zip_income', 0):,.0f}" if metrics.get("zip_income") else "Insufficient data",
        },
        {
            "Metric": "Vacancy Rate",
            "Value": _fmt_percent(metrics.get("zip_vacancy_rate")),
        },
    ]
    df = pd.DataFrame(data)
    st.dataframe(df, hide_index=True, use_container_width=True)


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
    st.dataframe(df[["Address", "Sale Date", "Sale Price", "Sqft", "Distance (mi)"]], hide_index=True, use_container_width=True)

