# AI Real Estate Broker (DC)

Investor-focused MVP for Washington, DC that pairs Streamlit, FastAPI, and dual data sources (CSV or ServiceNow) with Gemini-led scoring. The backend computes market analytics, the Gemini model produces the final Buy/Hold/Sell decision and rationale, and the UI highlights factor attributions, chat, and a CoStar-style PDF report.

## What’s Inside
- **Streamlit front end** – Home grid with ZIP filter, decision badges (fallback based on deterministic score), detail page with right-rail chat + popup modal, score explanation bars, and PDF export.
- **FastAPI backend** – REST endpoints for listings, per-property analysis payloads, `/api/score` (Gemini final decision), `/api/broker` chat, and PDF export; includes `/api/health` for status checks.
- **AI-first scoring** – Python computes market cap rate, projected rent growth, MSI components, and affordability. Gemini (via `google-generativeai`) receives the structured payload + factor attributions and returns score/decision/rationale/top contributors. A deterministic fallback mirrors the rubric when Gemini is unavailable.
- **Analytics toolkit** – pandas feature engineering, Prophet/ARIMA rent forecasts, market strength index (income/vacancy/DOM), affordability ratios, and ranked comps.
- **Dual data modes** – `DB_MODE=csv` runs from bundled synthetic datasets; `DB_MODE=servicenow` pulls the same schema via the ServiceNow Table API with numeric coercion and optional seeding script.
- **CoStar-style PDF** – ReportLab one-pager with executive summary (LLM text), key metrics, rent/price charts, comps snapshot, factor breakdown, and risks/provenance banner.
- **Quality guardrails** – Ruff linting, pytest suite (scoring monotonicity + API schema), GitHub Actions workflow, Docker/Compose support, and `.env` templates.

## Project Layout
```
ai-broker-dc/
├── app/                      # Streamlit app, components, assets
├── backend/                  # FastAPI app, analytics services, Gemini client, data access
├── data/                     # Synthetic DC datasets (CSV mode)
├── tests/                    # Pytest suite
├── .github/workflows/ci.yml  # Lint + test pipeline
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
├── README.md
└── DEMO.md
```

## Quick Start (CSV mode)
```bash
make venv
cp .env.example .env  # set GOOGLE_API_KEY if you want live Gemini scoring
make api               # http://localhost:8000
make app               # http://localhost:8501
```
`make all` launches API + Streamlit together (press Ctrl+C to stop both).

Without a Gemini key the system uses deterministic fallback scoring but everything else (analysis, UI, PDF) works.

## ServiceNow Mode
```env
DB_MODE=servicenow
SERVICENOW_INSTANCE=https://your-instance.service-now.com
SERVICENOW_USER=...
SERVICENOW_PASS=...
SERVICENOW_PROPERTIES_TABLE=u_properties
SERVICENOW_MARKET_TABLE=u_market_stats
SERVICENOW_COMPS_TABLE=u_comps
```
1. `make seed_sn` (optional) posts the bundled CSV data into ServiceNow tables.
2. Restart `make api`; the repository automatically routes API calls through ServiceNow.

## Docker & Compose
```bash
docker-compose up --build
```
- `api` runs FastAPI (port 8000) honouring `DB_MODE`, Gemini, and ServiceNow env vars.
- `app` runs Streamlit (port 8501) against `api`.

Provide env vars through `.env` or the compose file (e.g., `GOOGLE_API_KEY` for Gemini).

## Testing & Linting
```bash
make lint
make test
```
Pytests cover deterministic scoring monotonicity and REST contract (`/api/properties/{id}`, `/api/score`). CI (`.github/workflows/ci.yml`) installs dependencies and runs the same steps with `DB_MODE=csv`.

## Data & Analytics Notes
- `data/market_stats.csv` includes cap rate proxies, median income, vacancy, and DOM per month (60 months across ZIPs 20001–20003). The same schema is expected in ServiceNow (`x_ai_prop_market_stats`).
- Analytics compute cap rate, 12-month rent growth (Prophet → ARIMA → naive), MSI (income level + growth − vacancy − DOM), affordability (rent to income), and appreciation (display only).
- Factor attributions normalise each metric across the DC dataset (robust 5–95 percentile) for transparency and fallback scoring.
- No raw PII or vendor-licensed data is sent to Gemini—only the aggregated analysis JSON.

## Key Services & Modules
- `backend/services/analysis_service.py` – Builds the analysis payload, metrics, factor attributions, and fallback score.
- `backend/services/broker_llm.py` – Gemini interface with strict JSON output; deterministic fallback when Gemini is unavailable.
- `backend/services/forecast_service.py` – Produces rent/price histories and 36‑month forecasts plus projected rent growth (12m).
- `backend/services/pdf_service.py` – CoStar-style single-page PDF with executive summary, metrics, charts, comps, factors, and provenance.
- `app/main.py` – Streamlit flows (ZIP listings, score explanation bars, right-rail chat + popup modal, PDF export).

## Demo Flow (abridged)
1. Filter the home grid by ZIP (e.g., 20001) and note fallback decisions on each card.
2. Open property `P20001-01` (“125 New Jersey Ave NW”).
3. Detail page auto-calls `/api/score`, updates decision/score, and visualises factor contributions.
4. Use the right-rail chat or open the popup modal to ask “Should I sell in 2 years?” and “What risks should I watch?”.
5. Export the CoStar-style PDF to show the executive summary, charts, comps, and factor breakdown.

See `DEMO.md` for the full scripted walk-through.

## Assumptions & Limitations
- Financing costs, tax impacts, permits, and renovation budgets are out of scope for the MVP.
- Affordability uses rent-to-income from median rent when property rent is missing.
- Prophet/pmdarima are optional; the app gracefully falls back to ARIMA or naive projections.
- Gemini output is deterministic with the provided temperature settings, but the fallback path guarantees behaviour if the API key is absent.

## Disclaimer
The app and PDF automatically display: *“Demo using public/synthetic data for Washington, DC. Informational only; not financial advice.”*

## Troubleshooting
- **ServiceNow creds missing**: the API logs a warning and falls back to CSV mode. Ensure `SERVICENOW_INSTANCE`, `SERVICENOW_USER`, `SERVICENOW_PASS`, and the `SN_TABLE_*` variables are set.
- **Gemini unavailable**: the UI and PDF fall back to deterministic scoring; broker chat responses explain the fallback.
- **Prophet not installed**: rent forecasts automatically fall back to ARIMA or a naive trend.
