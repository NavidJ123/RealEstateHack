# AI Real Estate Broker (DC)

Production-ready MVP that pairs DC property search with automated analytics, forecasting, and an investor-focused AI briefing. Streamlit powers the UI, FastAPI exposes the analysis services, and the backend leans on pandas/statistical packages for feature engineering.

## Highlights
- **DC-focused listings** – 30 synthetic properties across 20001, 20002, and 20003 with investor-ready metadata.
- **Dual data access** – Uses Postgres/Supabase when `USE_DB=true`; otherwise operates fully offline from CSV seed files.
- **Feature engineering** – Appreciation, cap rate, rent growth, and market strength normalization feed a 0–100 Buy/Hold/Sell score.
- **Forecasts + comps** – Prophet (or ARIMA fallback) generates 36‑month price/rent projections; comps ranked by recency and distance.
- **AI broker layer** – Structured JSON passed to OpenAI (or deterministic fallback) for summaries and Q&A. No in-flight math.
- **Investor report PDF** – One-click, single-page PDF with charts, metrics, and recommendation summary.
- **CI guardrails** – GitHub Actions runs `ruff` linting and `pytest` against the CSV demo data set.

## Repository Layout
```
ai-broker-dc/
├── app/                # Streamlit UI + components
├── backend/            # FastAPI app, analytics services, data access
├── data/               # CSV demo datasets (properties, market stats, comps)
├── tests/              # Pytest suite (scoring, analysis, API)
├── assets/             # Placeholders for screenshots / marketing collateral
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
├── README.md
└── DEMO.md
```

## Quick Start
1. **Bootstrap the environment**
   ```bash
   make venv
   cp .env.example .env  # update values as needed
   ```

2. **Run locally (CSV mode)**
   ```bash
   make api   # Terminal 1 – FastAPI at http://localhost:8000
   make app   # Terminal 2 – Streamlit at http://localhost:8501
   ```

3. **(Optional) Seed Postgres/Supabase**
   ```bash
   export USE_DB=true  # and set DATABASE_URL in .env
   make seed
   ```

4. **Combined runner**
   ```bash
   make all  # starts API + Streamlit together with automatic teardown
   ```

## Docker & Compose
```
docker-compose up --build
```
- `db`: Postgres 14 with demo credentials (`broker`/`broker`).
- `api`: FastAPI service (mapped to `localhost:8000`).
- `app`: Streamlit UI (mapped to `localhost:8501`).

## Testing & Linting
```
make lint
make test
```
Tests rely on the CSV data and do not require a running database. The test broker responses use the deterministic fallback path when `OPENAI_API_KEY` is absent.

## Data & Assumptions
- **Synthetic datasets** live in `data/`. Each file ships with realistic but fictional DC stats enabling offline demos.
- **Forecasting fallback** uses ARIMA or a naive trend if Prophet/pmdarima are unavailable, keeping the API resilient inside CI.
- **LLM usage** is limited to summarization/Q&A. If `OPENAI_API_KEY` is not provided, a templated response covers acceptance criteria.
- **Assumptions** – No property taxes or renovation budgets; metro proximity and permit data are out of scope for the MVP.

## Key Services
- `analysis_service.py` – Feature engineering, scoring, and consolidation of comps/forecasts.
- `forecast_service.py` – Prophet with ARIMA/naive fallbacks and 36‑month horizon caching.
- `broker_llm.py` – Prompt orchestration with JSON context block.
- `pdf_service.py` – ReportLab-based single page investor brief.

## Supabase / Postgres
- Schema lives in `backend/db/schema.sql`.
- Seeder (`backend/db/seed.py`) loads CSVs via psycopg, using upsert semantics for idempotency.
- Toggle DB mode with `USE_DB=true` and set `DATABASE_URL`. When absent, the repo defaults to CSV reads.

## Streamlit UX Notes
- Home grid renders >12 cards with score & decision badges across the three ZIP codes.
- Detail page features price/rent charts, metrics table, ranked comps, chat, and PDF export.
- Footer displays the required disclaimer on every page.

## LLM Safety and Ops
- All outbound calls strip calculations from prompts; JSON is passed verbatim.
- No secrets are logged, and `.env.example` documents required values.
- Broker fallback ensures consistent copy for demos when API keys are missing.

## Screenshots & Demo Assets
Place PNG screenshots in `assets/` using the following naming convention (referenced in DEMO.md):
- `assets/home.png`
- `assets/detail.png`
- `assets/report.png`

## Assumptions
- Recommendations exclude financing, tax, or renovation considerations.
- CSV datasets emulate DC trends but are synthetic; deploy with verified data before production use.
- Streamlit and FastAPI run on the same host in local/demo environments.

## License
Licensed for demo purposes only. Replace data and API keys before production deployment.

