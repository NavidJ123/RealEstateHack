"""Streamlit UI for the AI Real Estate Broker MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import sys

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.backend_client import BackendClient
from app.components.cards import render_property_card
from app.components.charts import render_trend_chart
from app.components.chat import render_chat
from app.components.tables import render_comps_table, render_metrics_table

st.set_page_config(page_title="AI Real Estate Broker (DC)", layout="wide", page_icon="🏙️")

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
    st.experimental_set_query_params(property_id=property_id)


def navigate_home() -> None:
    st.experimental_set_query_params()


def property_summaries(backend: BackendClient, properties: List[Dict]) -> Dict[str, Dict]:
    summaries = {}
    with st.spinner("Computing investor analytics..."):
        for prop in properties:
            pid = prop["id"]
            analysis = backend.get_analysis(pid)
            summaries[pid] = {
                "score": analysis.get("score"),
                "decision": analysis.get("decision"),
                "current_est_value": analysis.get("metrics", {}).get("current_est_value"),
                "analysis": analysis,
            }
    return summaries


def render_listing_page() -> None:
    st.title("AI Real Estate Broker · Washington, DC")
    st.write("Browse curated DC properties with investor-grade analytics.")

    backend = get_backend_client()

    zip_query = st.text_input("Filter by ZIP (20001–20003)", "")
    zip_filter = zip_query.strip() if zip_query.strip().isdigit() and len(zip_query.strip()) == 5 else None
    if zip_query and not zip_filter:
        st.info("Enter a 5-digit DC ZIP such as 20001 to filter listings.")

    properties = backend.list_properties(zipcode=zip_filter, limit=24)

    if not properties:
        st.warning("No properties available for the selected ZIP.")
        return

    summaries = property_summaries(backend, properties)

    columns = st.columns(3)
    for idx, prop in enumerate(properties):
        summary = summaries[prop["id"]]
        with columns[idx % 3]:
            render_property_card(
                prop,
                summary,
                on_click=lambda pid=prop["id"]: navigate_to(pid),
                key=prop["id"],
            )

    st.markdown(DISCLAIMER_HTML, unsafe_allow_html=True)


def render_detail_page(property_id: str) -> None:
    backend = get_backend_client()
    analysis = backend.get_analysis(property_id)
    metrics = analysis.get("metrics", {})

    st.button("← Back to listings", on_click=navigate_home)

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"## {analysis['address']}")
        st.markdown(
            f"<span class='decision-pill decision-{analysis['decision'].lower()}'>Decision: {analysis['decision']}</span>",
            unsafe_allow_html=True,
        )
    with col2:
        st.metric("Score", analysis.get("score"), help="0–100 investor score based on appreciation, income, rent growth, and market strength")
        st.metric("Zip Code", analysis.get("zip"))

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
    pdf_bytes = st.session_state[pdf_key]
    st.download_button(
        "Export Investor PDF",
        data=pdf_bytes,
        file_name=f"{property_id}_investor_brief.pdf",
        mime="application/pdf",
        use_container_width=False,
    )

    render_chat(property_id, analysis, backend)

    st.markdown(DISCLAIMER_HTML, unsafe_allow_html=True)


load_styles()
params = st.experimental_get_query_params()
property_id = params.get("property_id", [None])[0]

if property_id:
    render_detail_page(property_id)
else:
    render_listing_page()

