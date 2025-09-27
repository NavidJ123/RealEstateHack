import os, json, google.generativeai as genai

MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

SYSTEM = (
  "You are an AI Real Estate Broker. Do NOT compute numbers—"
  "use the provided JSON exactly. Be concise and decisive. "
  "1) State Buy/Hold/Sell and score. 2) Cite 2–3 key metrics. "
  "3) Mention 1 risk or data gap. 4) If missing data, say 'insufficient data'."
)

def explain(analysis_json: dict) -> str:
    prompt = f"{SYSTEM}\n\nJSON:\n```json\n{json.dumps(analysis_json)[:20000]}\n```"
    try:
        resp = genai.GenerativeModel(MODEL).generate_content(prompt)
        return resp.text.strip()
    except Exception:
        # deterministic fallback (no key / rate limit)
        m = analysis_json.get("metrics", {})
        score = analysis_json.get("score", "—")
        decision = analysis_json.get("decision","—")
        return (f"{decision} (score {score}). "
                f"Appreciation {m.get('appreciation_5y','—')}, "
                f"Cap rate {m.get('cap_rate_est','—')}, "
                f"Rent growth {m.get('rent_growth_3y','—')}. "
                f"Risk: data coverage or forecast uncertainty.")
        
def qa(analysis_json: dict, question: str) -> str:
    prompt = (
      f"{SYSTEM}\nUser question: {question}\n\n"
      f"JSON:\n```json\n{json.dumps(analysis_json)[:20000]}\n```"
    )
    try:
        resp = genai.GenerativeModel(MODEL).generate_content(prompt)
        return resp.text.strip()
    except Exception:
        return "Using template mode. Key metrics are shown on the page; ask about price trend, rent growth, or comps."
