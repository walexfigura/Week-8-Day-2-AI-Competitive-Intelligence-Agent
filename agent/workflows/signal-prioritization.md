# Workflow: Signal Prioritization

## Criteria (see `competitive-priorities`)
| Factor | Question |
|---|---|
| Business relevance | Does it affect a product mapped `direct` to a Northstar product? |
| Magnitude | How large is the change (Python-computed)? |
| Evidence quality | Comparable, complete, primary-source observations? |
| Customer impact | Do reviews or segments suggest customers will notice? |
| Urgency | Does waiting a week cost us anything? |
| Confidence | Direct observation (high) vs interpretation (medium) vs partial (low) |

`assess_signal_priority(event_id, ...)` returns each factor's level, a suggested tier,
and its reasons. It is a **heuristic baseline**. You may raise or lower it with a stated
reason, except that the application will not accept `high` for an event the rubric
marks `insufficient_evidence` or `no_alert`.

## Tiers
- **High** — act this week: e.g. a 17.9% price decrease on the direct competitor to our
  best seller, observed on two comparable snapshots.
- **High** can also fit a new competing feature that targets our differentiators on a
  direct comparable — e.g. a commuter competitor adds a leak-proof lid where our
  comparable Commute tumbler has none.
- **Medium** — investigate soon: e.g. a premium brand shifts messaging toward commuters
  (the rubric cannot judge audience shifts from text; that interpretation is your job),
  or a partially comparable product sells out.
- **Low** — record only: small or non-comparable changes, availability of partial comparables.
- **Insufficient evidence** — cannot conclude: variant/currency mismatch, partial data,
  rumors.
- **No alert** — formatting-only changes, promotions that ended as stated.

Always explain the tier in one or two sentences tied to the criteria.
