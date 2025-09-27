"""LLM interface for transforming analysis JSON into explanations."""

from __future__ import annotations

import json
import os
from typing import Optional

from ..models.analysis import AnalysisResponse, BrokerMessage
from ..utils.logging import get_logger

LOGGER = get_logger("services.broker_llm")

_SYSTEM_PROMPT = """You are an AI Real Estate Broker. You DO NOT perform calculations.\nYou receive a JSON payload with property metrics, trends, comps, and a score.\nTask:\n1) Summarize Buy/Hold/Sell, stating the numeric score and top 3 drivers.\n2) Mention 1–2 key risks (data gaps, volatility, taxes if high vacancy).\n3) If asked follow-ups, cite the numbers from JSON.\n4) Be concise, professional, and avoid hedging language.\n5) Never invent data; if missing, say \"insufficient data\"."""


class BrokerLLM:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY")
        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI  # type: ignore

                self._client = OpenAI(api_key=self.api_key)
            except Exception as exc:  # pragma: no cover - optional dependency
                LOGGER.warning("Failed to init OpenAI client: %s", exc)
                self._client = None

    def build_context(self, analysis: AnalysisResponse) -> str:
        payload = analysis.dict()
        return json.dumps(payload, indent=2)

    def invoke(self, analysis: AnalysisResponse, question: Optional[str] = None) -> list[BrokerMessage]:
        context_json = self.build_context(analysis)
        assistant_context = f"```json\n{context_json}\n```"
        if not self._client:
            LOGGER.info("OPENAI_API_KEY not configured; using templated fallback response")
            return [self._fallback_message(analysis, question)]

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": assistant_context},
        ]
        if question:
            messages.append({"role": "user", "content": question})
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
            )
            content = completion.choices[0].message.content or ""
            return [BrokerMessage(role="assistant", content=content.strip())]
        except Exception as exc:  # pragma: no cover - degrade gracefully
            LOGGER.warning("LLM call failed: %s", exc)
            return [self._fallback_message(analysis, question)]

    def _fallback_message(self, analysis: AnalysisResponse, question: Optional[str]) -> BrokerMessage:
        metrics = analysis.metrics
        drivers = [
            f"Appreciation 5y: {metrics.appreciation_5y:.1%}" if metrics.appreciation_5y is not None else None,
            f"Cap rate: {metrics.cap_rate_est:.1%}" if metrics.cap_rate_est is not None else None,
            f"Rent growth 3y: {metrics.rent_growth_3y:.1%}" if metrics.rent_growth_3y is not None else None,
        ]
        drivers = [d for d in drivers if d]
        risks = []
        if metrics.market_strength is not None and metrics.market_strength < 0:
            risks.append("Local vacancy pressure remains above peers")
        if metrics.appreciation_5y is not None and metrics.appreciation_5y < 0:
            risks.append("Recent price performance is negative")
        if not risks:
            risks.append("Monitor tax changes and maintenance reserves")
        summary = [
            f"Decision: {analysis.decision} (Score {analysis.score}).",
            "Key drivers: " + ", ".join(drivers[:3]) if drivers else "Drivers: insufficient data.",
            "Risks: " + ", ".join(risks[:2]),
        ]
        if question:
            summary.append(f"Follow-up response: Based on the score {analysis.score} and metrics above, {question.strip()}")
        return BrokerMessage(role="assistant", content=" ".join(summary))

