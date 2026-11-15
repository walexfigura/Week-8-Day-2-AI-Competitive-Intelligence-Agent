# Scope and Authority

## In scope
- Monitoring the fictional competitor watchlist (`competitors/watchlist.json`).
- Comparing stored product-page snapshots and the current page fixture.
- Analyzing supplied customer reviews and competitor announcements.
- Comparing competitor products with Northstar's documented products.
- Prioritizing findings and writing a brief to `reports/`.

## Out of scope
- Any action outside reading data and saving a report: no price changes, no catalog or
  copy edits, no publishing, no outreach, no external alerts.
- Legal, financial-forecasting, or market-share claims.
- Statements about competitors' internal decisions, costs, or motives.
- Data about individual reviewers beyond what the review record shows.

## Data mode
Unless told otherwise, the data is **fictional mock data** from local files. Never
present findings as real market research.

## Run budget
Each run has a limited number of model turns and tool calls (see `.env.example`).
Prioritize the investigations that could change your conclusions, and save the report
before the budget runs out.
