"""Plotly chart helpers for Streamlit UI."""

from __future__ import annotations

from typing import List, Sequence

import plotly.graph_objects as go


def _extract_series(points: Sequence[dict]) -> tuple[list[str], list[float]]:
    dates = [p.get("date") for p in points]
    values = [p.get("value") for p in points]
    return dates, values


def _forecast_band(points: Sequence[dict]) -> tuple[list[str], list[float], list[float]]:
    dates = [p.get("date") for p in points]
    lowers = [p.get("lower", p.get("value")) for p in points]
    uppers = [p.get("upper", p.get("value")) for p in points]
    return dates, lowers, uppers


def render_trend_chart(history: List[dict], forecast: List[dict], title: str, yaxis_title: str) -> go.Figure:
    hist_x, hist_y = _extract_series(history)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hist_x,
            y=hist_y,
            name="History",
            mode="lines",
            line=dict(color="#1565C0", width=3),
        )
    )
    if forecast:
        fc_x, fc_y = _extract_series(forecast)
        fig.add_trace(
            go.Scatter(
                x=fc_x,
                y=fc_y,
                name="Forecast",
                mode="lines",
                line=dict(color="#42A5F5", dash="dash"),
            )
        )
        band_x, band_lower, band_upper = _forecast_band(forecast)
        fig.add_trace(
            go.Scatter(
                x=band_x,
                y=band_upper,
                name="Upper",
                mode="lines",
                line=dict(width=0),
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=band_x,
                y=band_lower,
                name="80% Interval",
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(66, 165, 245, 0.2)",
                showlegend=True,
            )
        )
    fig.update_layout(
        title=title,
        margin=dict(l=10, r=10, t=40, b=30),
        height=360,
        yaxis_title=yaxis_title,
        xaxis_title="Date",
        template="plotly_white",
    )
    return fig

