# Demo Script – AI Real Estate Broker (DC)

Follow this click path for a 3–4 minute walkthrough:

1. **Launch the app**
   - Start the FastAPI backend (`make api`) and Streamlit frontend (`make app`).
   - Open http://localhost:8501 in the browser.

2. **Explore Listings**
   - Scroll the home grid and point out coverage across ZIPs 20001–20003.
   - Mention score badges and Buy/Hold/Sell decisions on each card.

3. **Open Property `P20001-01`**
   - Click *Open details* on the “125 New Jersey Ave NW” card.
   - Highlight the hero banner (decision + score) and the key metrics table.

4. **Discuss Trends & Comps**
   - Show the median price and rent Plotly charts (history + forecast band).
   - Scroll to the comps table and note recency/distance sorting.

5. **Broker Chat Q&A**
   - Ask: “Should I sell in 2 years?”
   - Follow up: “What risks should I watch?”
   - Ensure the responses cite score and at least two metrics.

6. **Export the Investor Report**
   - Click *Export Investor PDF*; open the generated PDF to show layout.

7. **Closing**
   - Mention CSV vs. Postgres toggle, risk disclaimer in footer, and optional LLM API key for richer copy.

