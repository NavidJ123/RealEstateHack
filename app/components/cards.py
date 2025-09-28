"""Streamlit components for property listing cards."""

from __future__ import annotations

from typing import Callable, Dict, Optional

import streamlit as st


def score_badge(score: Optional[int]) -> str:
    if score is None:
        return "score-badge score-warning"
    if score >= 75:
        tone = "success"
    elif score >= 55:
        tone = "warning"
    else:
        tone = "danger"
    return f"score-badge score-{tone}"


def decision_pill(decision: str | None) -> str:
    label = (decision or "Hold").lower()
    return f"decision-pill decision-{label}"


def render_property_card(
    property_data: Dict,
    summary: Dict,
    on_click: Callable[[], None],
    key: Optional[str] = None,
) -> None:
    key = key or property_data.get("id")
    decision = summary.get("decision") or "Hold"
    score = summary.get("score")
    current_value = summary.get("current_est_value") or property_data.get("current_est_value") or 0

    card_html = f"""
        <div class="property-card">
            <div class="property-card__header">
                <span class="{decision_pill(decision)}">{decision}</span>
                <span class="{score_badge(score)}">{score if score is not None else '-'}</span>
            </div>
            <h3>{property_data.get('address')}</h3>
            <p class="property-card__meta">{property_data.get('zipcode')} · {property_data.get('type') or 'Property'} · {property_data.get('sqft') or '-'} sqft</p>
            <p class="property-card__value">${float(current_value):,.0f}</p>
        </div>
    """
    with st.container():
        st.markdown(card_html, unsafe_allow_html=True)
        st.button("Open details", key=f"open-{key}", on_click=on_click)

