# Demo Script – AI Real Estate Broker (DC)

Use this 3–4 minute flow for judging or stakeholder demos.

1. **Launch**
   - `make api` in one terminal, `make app` in another (or `make all`).
   - Open http://localhost:8501; confirm the footer disclaimer.

2. **Listings Overview**
   - Filter the home grid by ZIP (e.g., type `20001`).
   - Point out the fallback decision/score chips (deterministic) and card styling.

3. **Deep Dive on `P20001-01`**
   - Open the “125 New Jersey Ave NW” card.
   - Highlight the Gemini-powered score + decision pill and the rationale section.

4. **Explain the Score**
   - Show the factor contribution bars (cap rate, rent growth, MSI, affordability).
   - Mention fallback score displayed for transparency.

5. **Broker Chat**
   - Ask “Should I sell in 2 years?” in the right-rail chat.
   - Open the popup chat modal and ask “What risks should I watch?”
   - Emphasise that responses cite provided metrics only.

6. **Market Context & Comps**
   - Scroll through the rent/price charts and the comps table.
   - Call out MSI ingredients (income growth, vacancy, DOM) in the metrics table.

7. **Export the Report**
   - Click “Export CoStar-Style PDF” and open the download to showcase the executive summary, metrics, charts, comps, and factor breakdown.

8. **Wrap-up**
   - Mention `DB_MODE=csv` for offline demos vs. `DB_MODE=servicenow` for live data.
   - Note Gemini scoring (set `GOOGLE_API_KEY`) with deterministic fallback when absent.

