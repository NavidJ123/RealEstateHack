"""LLM interface for scoring and broker explanations using Gemini."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover - optional dependency
    genai = None

from ..models.analysis import AnalysisResponse
from ..utils.logging import get_logger
from .scoring import decision_from_score

LOGGER = get_logger("services.broker_llm")

SCORE_PROMPT = """You are an AI Real Estate Broker. Use the provided JSON analysis to produce an investment decision.
Do NOT invent numbers. If a metric is missing, state 'insufficient data' in the rationale and use the fallback score provided.

SCORING RULE:
- Consider Market Cap Rate (weight ~0.35), Projected Rent Growth 12m (~0.35), and Market Strength Index (~0.30; built from income level/growth up, vacancy down, DOM down).
- Score 0-100. Decision: Buy >=75, Hold 55-74, Sell <55.

When you answer, produce a structured thesis in the following format (plain text, no markdown headings):
"Investment Score: <score>/100 – Decision: <Buy|Hold|Sell>"
- Bullet paragraph on submarket positioning and competitive standing (reference cap rate, income strength, vacancy).
- Bullet paragraph on cash-flow outlook (rent growth, NOI indicators, affordability cues).
- Bullet paragraph on forward-looking upside or watch items (vacancy trend, supply pipeline, DOM).
- Bullet paragraph on a key risk or mitigation focus.
End with a single line noting if the fallback score was used.

Return STRICT JSON with keys:
{"score": int, "decision": "Buy|Hold|Sell", "rationale": "...", "top_contributors": [{"name": "...", "effect": "+|-"}]}

Here is the analysis JSON:
```json
{analysis_json}
```
Use the provided "explanations.factors" when listing top_contributors."""

QA_PROMPT = """You are an AI Real Estate Broker answering investor questions about a property.
Use ONLY the provided JSON analysis and scoring summary. Do not fabricate numbers.
"""


class BrokerLLM:
    # in broker_llm.py
    # broker_llm.py
    def __init__(self, model: Optional[str] = None) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY")
        preferred = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
        # normalize: strip 'models/' prefix if present
        self.model_name = preferred.split("/", 1)[-1] if preferred.startswith("models/") else preferred
        self._model = None
        if self.api_key and genai is not None:
            try:
                genai.configure(api_key=self.api_key)
                try:
                    self._model = genai.GenerativeModel(self.model_name)
                except Exception:
                    # auto-pick a supported 2.x model
                    avail = [m for m in genai.list_models()
                            if "generateContent" in getattr(m, "supported_generation_methods", [])]
                    names = [getattr(m, "name", "") for m in avail]
                    for cand in ("models/gemini-2.5-flash","models/gemini-2.5-pro","gemini-2.5-flash","gemini-2.5-pro"):
                        if cand in names or cand.replace("models/","") in names:
                            self.model_name = cand.replace("models/","")
                            self._model = genai.GenerativeModel(self.model_name)
                            break
            except Exception as exc:
                LOGGER.warning("Failed to initialise Gemini client: %s", exc)
                self._model = None



    def score_and_explain(self, analysis: AnalysisResponse | Dict[str, Any]) -> Dict[str, Any]:
        payload = self._ensure_dict(analysis)
        fallback_score = payload.get("explanations", {}).get("fallback_total_score") or 0
        fallback = self._fallback_result(payload, fallback_score)
        if not self._model:
            return fallback
        prompt = SCORE_PROMPT.replace("{analysis_json}", json.dumps(payload, indent=2))
        try:
            response = self._model.generate_content(
                prompt,
                generation_config={"temperature": 0.2, "response_mime_type": "application/json"},
            )
            text = self._extract_text(response)
            scored = self._load_json(text)
            if not self._validate_score_payload(scored):
                raise ValueError("Invalid JSON payload returned by Gemini")
            return self._enforce_thresholds(scored)
        except Exception as exc:  # pragma: no cover - robustness path
            LOGGER.warning("Gemini scoring failed: %s", exc)
            return fallback

    def qa(self, analysis: AnalysisResponse | Dict[str, Any], question: str, scoring_result: Optional[Dict[str, Any]] = None) -> str:
        payload = self._ensure_dict(analysis)
        scoring = scoring_result or self.score_and_explain(payload)
        if not self._model:
            return self._fallback_qa(payload, scoring, question)
        context = {
            "analysis": payload,
            "scoring": scoring,
            "question": question,
        }
        prompt = QA_PROMPT + "\nJSON CONTEXT:\n" + json.dumps(context, indent=2) + "\nAnswer in 3-5 sentences, citing metrics from the JSON."
        try:
            response = self._model.generate_content(prompt, generation_config={"temperature": 0.4})
            return self._extract_text(response).strip()
        except Exception as exc:  # pragma: no cover - fallback path
            LOGGER.warning("Gemini QA failed: %s", exc)
            return self._fallback_qa(payload, scoring, question)

    def _fallback_result(self, payload: Dict[str, Any], fallback_score: int) -> Dict[str, Any]:
        decision = decision_from_score(fallback_score)
        metrics = payload.get("metrics", {})
        cap_rate = metrics.get("cap_rate_market_now")
        rent_growth = metrics.get("rent_growth_proj_12m")
        msi = metrics.get("market_strength_index")
        vacancy = metrics.get("vacancy_rate_now")
        rationale_lines = [
            f"Investment Score: {fallback_score}/100 – Decision: {decision}",
            f"- Market position: cap rate {cap_rate:.2%} and MSI {msi:.2f} signal relative strength." if cap_rate is not None and msi is not None else "- Market position: evaluating cap rate and MSI indicates mixed signals (insufficient data).",
            f"- Cash flow outlook: projected rent growth {rent_growth:.2%} with vacancy {vacancy:.2%}." if rent_growth is not None and vacancy is not None else "- Cash flow outlook: rent growth or vacancy data unavailable; monitor stabilized occupancy.",
            "- Affordability: monitor rent-to-income ratios and expense drift against peers for resilience.",
            "- Forward view: affordability and DOM trends suggest monitoring tenant demand resilience.",
            "- Key risk: rely on fallback score due to incomplete Gemini response." if not self._model else "- Key risk: monitor supply pipeline and expense creep relative to peers.",
            "Fallback score applied due to Gemini unavailability." if not self._model else "Fallback score included for transparency.",
        ]
        rationale = "\n".join(rationale_lines)
        factors = payload.get("explanations", {}).get("factors", [])
        sorted_factors = sorted(factors, key=lambda f: abs(f.get("contrib", 0.0)), reverse=True)
        top = []
        for item in sorted_factors[:2]:
            effect = "+" if item.get("contrib", 0.0) >= 0 else "-"
            top.append({"name": item.get("name", "Factor"), "effect": effect})
        return {
            "score": fallback_score,
            "decision": decision,
            "rationale": rationale,
            "top_contributors": top,
        }

    def _fallback_qa(self, payload: Dict[str, Any], scoring: Dict[str, Any], question: str) -> str:
        metrics = payload.get("metrics", {})
        lines = [
            f"Decision: {scoring['decision']} with score {scoring['score']} (fallback response).",
            f"- Cap rate {self._fmt_percent(metrics.get('cap_rate_market_now'))} and projected rent growth {self._fmt_percent(metrics.get('rent_growth_proj_12m'))}.",
        ]
        if metrics.get("market_strength_index") is not None:
            lines.append(f"- Market strength index {metrics['market_strength_index']:.2f} with vacancy {self._fmt_percent(metrics.get('vacancy_rate_now'))}.")
        lines.append(f"- You asked: {question.strip() or 'general outlook'}. Based on the available metrics, monitor supply, vacancy, and affordability before adjusting strategy.")
        return "\n".join(lines)

    def _ensure_dict(self, analysis: AnalysisResponse | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(analysis, AnalysisResponse):
            return json.loads(analysis.json())
        return analysis

    def _extract_text(self, response: Any) -> str:
        if hasattr(response, "text") and response.text:
            return response.text
        if hasattr(response, "candidates"):
            for candidate in response.candidates:
                if candidate.content.parts:
                    return "".join(part.text for part in candidate.content.parts if getattr(part, "text", None))
        raise ValueError("Empty response from Gemini")

    def _load_json(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end >= 0:
            text = text[start : end + 1]
        return json.loads(text)

    def _validate_score_payload(self, data: Dict[str, Any]) -> bool:
        required = {"score", "decision", "rationale", "top_contributors"}
        return required.issubset(data.keys()) and isinstance(data.get("top_contributors"), list)

    def _enforce_thresholds(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            score = int(round(float(data["score"])))
        except Exception:
            score = 0
        score = max(0, min(100, score))
        data["score"] = score
        data["decision"] = decision_from_score(score)
        top = data.get("top_contributors") or []
        normalized = []
        for item in top:
            if isinstance(item, dict):
                name = item.get("name") or item.get("factor") or "Factor"
                effect = item.get("effect")
                if effect not in {"+", "-"}:
                    contribution = item.get("contribution", 0)
                    effect = "+" if contribution >= 0 else "-"
                normalized.append({"name": name, "effect": effect})
            else:
                normalized.append({"name": str(item), "effect": "+"})
        data["top_contributors"] = normalized
        return data

    def _fmt_percent(self, value: Optional[float]) -> str:
        if value is None:
            return "insufficient data"
        return f"{value:.2%}"
