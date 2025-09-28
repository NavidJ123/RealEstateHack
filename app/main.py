"""Streamlit UI for the AI Real Estate Broker."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import sys

import plotly.graph_objects as go
import streamlit as st

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if load_dotenv is not None:
    load_dotenv(dotenv_path=ROOT_DIR / ".env", override=False)

from app.backend_client import BackendClient
from app.components.cards import render_property_card
from app.components.charts import render_trend_chart
from app.components.chat import render_chat
from app.components.tables import render_comps_table, render_metrics_table

st.set_page_config(page_title="AI Real Estate Broker (Gotham)", layout="wide", page_icon="🏙️")

DISCLAIMER_HTML = (
    "<p class='disclaimer'>Demo using public/synthetic data for Washington, DC. Informational only; not financial advice.</p>"
)


@st.cache_resource(show_spinner=False)
def get_backend_client() -> BackendClient:
    return BackendClient()


def load_styles() -> None:
    css_path = Path(__file__).resolve().parent / "assets" / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def navigate_to(property_id: str) -> None:
    st.query_params = {"property_id": property_id}


def navigate_home() -> None:
    st.query_params = {}


def decision_from_score(score: Optional[int]) -> str:
    if score is None:
        return "Hold"
    if score >= 75:
        return "Buy"
    if score >= 55:
        return "Hold"
    return "Sell"


def property_summaries(backend: BackendClient, properties: List[Dict]) -> Dict[str, Dict]:
    summaries: Dict[str, Dict] = {}
    with st.spinner("Loading analysis..."):
        for prop in properties:
            pid = prop["id"]
            analysis = backend.get_analysis(pid)
            fallback_score = analysis.get("score") or analysis.get("explanations", {}).get("fallback_total_score")
            decision = analysis.get("decision") or decision_from_score(fallback_score)
            summaries[pid] = {
                "fallback_score": fallback_score,
                "decision": decision,
                "current_est_value": analysis.get("metrics", {}).get("current_est_value"),
                "analysis": analysis,
            }
    return summaries


def render_explain_panel(explanations: Dict, scoring: Dict) -> None:
    with st.expander("Explain score", expanded=True):
        allowed_keys = {"cap_rate_market_now", "rent_growth_proj_12m", "market_strength_index"}
        factors = [
            factor
            for factor in explanations.get("factors", [])
            if factor.get("key") in allowed_keys and factor.get("contrib") is not None
        ]
        if not factors:
            st.info("No factor attribution available for this property.")
            return
        names = [factor.get("name", "") for factor in factors]
        contribs = [factor.get("contrib", 0.0) for factor in factors]
        colors = ["#22c55e" if value >= 0 else "#ef4444" for value in contribs]
        fig = go.Figure(
            go.Bar(x=contribs, y=names, orientation="h", marker_color=colors)
        )
        fig.update_layout(
            height=240,
            margin=dict(l=0, r=0, t=10, b=10),
            xaxis_title="Contribution (points)",
        )
        st.plotly_chart(fig, use_container_width=True)
        if scoring.get("top_contributors"):
            chips = ", ".join(
                f"{item['name']} ({item['effect']})" for item in scoring["top_contributors"]
            )
            st.caption(f"Top contributors: {chips}")


def render_listing_page() -> None:
    st.title("AI Real Estate Broker · Washington, DC")
    backend = get_backend_client()

    max_results = st.slider("Max listings", min_value=10, max_value=200, value=30, step=10)

    fetch_limit = 200
    properties = backend.list_properties(limit=fetch_limit)

    if not properties:
        st.warning("No properties available for the selected filter.")
        st.markdown(DISCLAIMER_HTML, unsafe_allow_html=True)
        return

    def safe_float(value: object) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    price_values = [val for prop in properties if (val := safe_float(prop.get("current_est_value"))) is not None]
    sqft_values = [val for prop in properties if (val := safe_float(prop.get("sqft"))) is not None]
    unit_values = [val for prop in properties if (val := safe_float(prop.get("num_units"))) is not None]
    submarket_values = {
        str(prop.get("submarket") or prop.get("submarket_name") or "").strip()
        for prop in properties
        if prop.get("submarket") or prop.get("submarket_name")
    }

    price_floor = int(min(price_values)) if price_values else 0
    price_ceiling = int(max(price_values)) if price_values else 5_000_000
    if price_floor == price_ceiling:
        price_ceiling = price_floor + 100_000

    sqft_floor = int(min(sqft_values)) if sqft_values else 0
    sqft_ceiling = int(max(sqft_values)) if sqft_values else 5_000
    if sqft_floor == sqft_ceiling:
        sqft_ceiling = sqft_floor + 100

    unit_floor = int(min(unit_values)) if unit_values else 0
    unit_ceiling = int(max(unit_values)) if unit_values else 100
    if unit_floor == unit_ceiling:
        unit_ceiling = unit_floor + 5

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    price_min, price_max = filter_col1.slider(
        "Price range ($)",
        min_value=price_floor,
        max_value=price_ceiling,
        value=(price_floor, price_ceiling),
        step=10_000,
    )
    zip_options = sorted({str(prop.get("zipcode") or "").strip() for prop in properties if prop.get("zipcode")})
    selected_zips = filter_col2.multiselect("ZIP code", options=zip_options, default=[])
    submarket_options = sorted(val for val in submarket_values if val)
    selected_submarkets = filter_col3.multiselect("Submarket", options=submarket_options, default=[])

    filter_col4, filter_col5 = st.columns(2)
    sqft_min, sqft_max = filter_col4.slider(
        "Square footage",
        min_value=sqft_floor,
        max_value=sqft_ceiling,
        value=(sqft_floor, sqft_ceiling),
        step=50,
    )
    units_min, units_max = filter_col5.slider(
        "Unit count",
        min_value=unit_floor,
        max_value=unit_ceiling,
        value=(unit_floor, unit_ceiling),
        step=1,
    )

    def within_range(value: object, lower: float, upper: float) -> bool:
        coerced = safe_float(value)
        if coerced is None:
            return False
        return lower <= coerced <= upper

    price_active = price_min > price_floor or price_max < price_ceiling
    sqft_active = sqft_min > sqft_floor or sqft_max < sqft_ceiling
    units_active = units_min > unit_floor or units_max < unit_ceiling
    submarket_active = bool(selected_submarkets)
    submarket_selected_normalized = {value.lower() for value in selected_submarkets}

    filtered = []
    for prop in properties:
        price = prop.get("current_est_value")
        sqft = prop.get("sqft")
        units = prop.get("num_units")
        zipcode = str(prop.get("zipcode") or "").strip()
        submarket = str(prop.get("submarket") or prop.get("submarket_name") or "").strip()

        if price is None:
            if price_active:
                continue
        elif not within_range(price, price_min, price_max):
            continue

        if sqft is None:
            if sqft_active:
                continue
        elif not within_range(sqft, sqft_min, sqft_max):
            continue

        if units is None:
            if units_active:
                continue
        elif not within_range(units, units_min, units_max):
            continue
        if selected_zips and zipcode not in selected_zips:
            continue
        if submarket_active and submarket.lower() not in submarket_selected_normalized:
            continue
        filtered.append(prop)

    if not filtered:
        st.info("No properties match the selected filters. Try widening the ranges.")
        st.markdown(DISCLAIMER_HTML, unsafe_allow_html=True)
        return

    limited_properties = filtered[:max_results]
    summaries = property_summaries(backend, limited_properties)
    columns = st.columns(3)
    for idx, prop in enumerate(limited_properties):
        summary = summaries[prop["id"]]
        with columns[idx % 3]:
            render_property_card(
                prop,
                {
                    "decision": summary["decision"],
                    "score": summary.get("fallback_score"),
                    "current_est_value": summary.get("current_est_value"),
                },
                on_click=lambda pid=prop["id"]: navigate_to(pid),
                key=prop["id"],
            )

    st.markdown(DISCLAIMER_HTML, unsafe_allow_html=True)


def render_detail_page(property_id: str) -> None:
    backend = get_backend_client()
    analysis = backend.get_analysis(property_id)
    thesis = backend.score_analysis(analysis)
    metrics = analysis.get("metrics", {})

    st.button("← Back to listings", on_click=navigate_home)

    header_col, score_col = st.columns([3, 1])
    with header_col:
        st.markdown(f"## {analysis['address']}")
        decision = thesis.get("decision", analysis.get("decision", "Hold"))
        st.markdown(
            f"<span class='decision-pill decision-{decision.lower()}'>Decision: {decision}</span>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"LLM score powered by Gemini; fallback {analysis.get('score', '—')} if unavailable."
        )
    with score_col:
        st.metric("Score", thesis.get("score"))
        st.metric("Zip Code", analysis.get("zip"))

    explain_col, chat_col = st.columns([3, 1])
    with explain_col:
        render_explain_panel(analysis.get("explanations", {}), thesis)
        st.markdown("### Investment Thesis")
        st.write(thesis.get("rationale", "No rationale available."))
    with chat_col:
        st.markdown("### Broker Chat")
        render_chat(
            property_id,
            analysis,
            backend,
            show_header=False,
            input_key=f"chat_{property_id}_inline",
        )
        if st.button("Open Chat Window"):
            st.session_state["chat_modal_open"] = True

    if st.session_state.get("chat_modal_open"):
        with st.container():
            st.markdown(
                "<div class='chat-modal-backdrop'></div><div class='chat-modal'>",
                unsafe_allow_html=True,
            )
            if st.button("Close", key="close-chat-modal"):
                st.session_state["chat_modal_open"] = False
            else:
                render_chat(
                    property_id,
                    analysis,
                    backend,
                    show_header=False,
                    input_key=f"chat_{property_id}_modal",
                )
            st.markdown("</div>", unsafe_allow_html=True)

    price_chart = render_trend_chart(
        analysis.get("zip_trends", {}).get("price_history", []),
        analysis.get("zip_trends", {}).get("price_forecast", []),
        "Median Price Trend + Forecast",
        "Price ($)",
    )
    rent_chart = render_trend_chart(
        analysis.get("zip_trends", {}).get("rent_history", []),
        analysis.get("zip_trends", {}).get("rent_forecast", []),
        "Median Rent Trend + Forecast",
        "Rent ($)",
    )

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(price_chart, use_container_width=True)
    with chart_col2:
        st.plotly_chart(rent_chart, use_container_width=True)

    st.subheader("Key Metrics")
    render_metrics_table(metrics)

    st.subheader("Comparable Sales")
    render_comps_table(analysis.get("comps", []))

    pdf_key = f"pdf_{property_id}"
    if pdf_key not in st.session_state:
        st.session_state[pdf_key] = backend.export_pdf(property_id)
    st.download_button(
        "Export CoStar-Style PDF",
        data=st.session_state[pdf_key],
        file_name=f"{property_id}_investor_brief.pdf",
        mime="application/pdf",
        width="content",
    )

    st.markdown(DISCLAIMER_HTML, unsafe_allow_html=True)


load_styles()
params = st.query_params
property_id = params.get("property_id")
if isinstance(property_id, list):
    property_id = property_id[0] if property_id else None

if property_id:
    render_detail_page(property_id)
else:
    render_listing_page()
