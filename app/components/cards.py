"""Streamlit components for property listing cards."""

from __future__ import annotations

from typing import Callable, Dict, Optional

import streamlit as st


def score_badge(score: int) -> str:
    if score >= 75:
        tone = "success"
    elif score >= 55:
        tone = "warning"
    else:
        tone = "danger"
    return f"score-badge score-{tone}"


def decision_pill(decision: str) -> str:
    return f"decision-pill decision-{decision.lower()}"


def render_property_card(property_data: Dict, summary: Dict, on_click: Callable[[], None], key: Optional[str] = None) -> None:
    key = key or property_data.get("id")
    with st.container():
        st.markdown(
            f"""
            <div class="property-card">
                <div class="property-card__header">
                    <span class="{decision_pill(summary.get('decision', 'Hold'))}">{summary.get('decision', 'Hold')}</span>
                    <span class="{score_badge(summary.get('score', 50))}">{summary.get('score', 0)}</span>
                </div>
                <h3>{property_data.get('address')}</h3>
                <p class="property-card__meta">{property_data.get('zipcode')} · {property_data.get('type') or 'Property'} · {property_data.get('sqft') or '—'} sqft</p>
                <p class="property-card__value">${float(summary.get('current_est_value') or property_data.get('current_est_value') or 0):,.0f}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.button("Open details", key=f"open-{key}", on_click=on_click)

