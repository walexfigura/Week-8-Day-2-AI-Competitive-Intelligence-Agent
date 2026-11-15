# Workflow: Briefing Generation

The final step of every run is one call to `save_intelligence_report`. The application
validates it, adds computed facts and a sources list, and saves Markdown + JSON to
`reports/`.

## Fields
- `executive_summary` — 3–5 sentences: the most important finding first.
- `signals[]` — `title`, `priority`, `competitor_id`, `product_id`, `variant_id`,
  `change_type`, `event_ids` (from `compare_product_snapshots`), `what_changed`,
  `previous_observation`, `new_observation`, `why_it_matters`, `evidence_ids`,
  `confidence`, `uncertainty`, `priority_rationale`, `recommended_next_step`.
- `sentiment_findings[]` — `product_id`, `aspect`, `sentiment`, `interpretation`,
  `review_ids`. Counts and sample sizes are filled in by Python from your analysis run.
- `no_alert_decisions[]` — changes you deliberately did not escalate, and why.
- `verification_needed[]` — `item`, `why`, `suggested_check`.
- `open_questions[]` — hypotheses (for example about motives), clearly unconfirmed.

## Validation (enforced in code)
- Cited IDs must have been returned by a tool in this run.
- Sentiment findings must come from `analyze_review_sentiment` results in this run.
- No population claims from samples ("X% of customers", "most customers").
- No asserted competitor motives outside `open_questions`.
- `high` priority is rejected for events the rubric marks `no_alert` or
  `insufficient_evidence`.

## Writing style
Plain language. Lead with what changed and what to do. Name dates and IDs. Keep each
recommendation a concrete next step for a human ("Head of Ecommerce: review Summit 32 oz
pricing against PeakTrail's $32 listing; capture two more observations first").
