# Demo Script – AI Real Estate Broker (DC)

Use this 3–4 minute flow for hackathon judging or stakeholder demos.

1. **Launch**
   - `make api` in one terminal, `make app` in another (or `make all`).
   - Navigate to http://localhost:8501; confirm the footer disclaimer is visible.

2. **Listings Overview**
   - Point out the ZIP filter (enter 20001) and show how the grid refreshes.
   - Highlight the card styling (photo, decision pill, score badge, value) and mention data comes from ServiceNow or CSV fallback.

3. **Deep Dive on `P20001-01`**
   - Open the “125 New Jersey Ave NW” card.
   - Call out the hero section with Buy/Hold/Sell decision and score, plus the quick metrics.

4. **Markets & Comps**
   - Walk through the Plotly charts (median price and rent with 36‑month forecasts).
   - Review the comparables, noting recency/distance scoring.

5. **Broker Chat**
   - Ask “Should I sell in 2 years?”
   - Follow up with “What risks should I watch?”
   - Emphasize that the response cites score and metrics without recomputing.

6. **PDF Export**
   - Click *Export Investor PDF*, open the download, and point to the summary, charts, and disclaimer.

7. **Wrap-up**
   - Mention `DB_MODE=csv` for offline demos vs. `DB_MODE=servicenow` for live data.
   - Note optional `OPENAI_API_KEY` for richer broker copy, and the deterministic fallback when absent.

