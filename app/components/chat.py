"""Broker chat component for the property detail page."""

from __future__ import annotations

from typing import Dict

import streamlit as st


def render_chat(property_id: str, analysis: Dict, backend_client, show_header: bool = True, input_key: str | None = None) -> None:
    state = st.session_state.setdefault("chat_history", {})
    history = state.setdefault(property_id, [])

    if input_key is None:
        input_key = f"chat_input_{property_id}"

    if show_header:
        st.markdown("### Broker Chat")
    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask the AI Broker about this property", key=input_key)
    if prompt:
        history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        reply = backend_client.ask_broker(property_id, analysis, prompt)
        history.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)

