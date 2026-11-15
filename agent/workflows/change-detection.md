# Workflow: Change Detection

`compare_product_snapshots` does the deterministic work. Your job is to interpret it.

## What the tool returns
- `status`: `changes_detected`, `no_meaningful_change`, `not_comparable`, or
  `incomplete_data`.
- `comparability.issues`: reasons a pair is unsafe to compare (variant, currency,
  storefront, missing price, wrong order).
- `events`: one per meaningful change, with `event_id`, `change_type`, old/new values,
  `magnitude` (computed in Python), `caveats`, and `evidence`.
- `unchanged_fields` and `formatting_only`.

## Change types and how to read them
| change_type | Meaning | Typical interpretation |
|---|---|---|
| `price_decrease` / `price_increase` | Same variant, currency, storefront | Check `caveats` for promotion/permanence |
| `promotion_started` | Page labels a sale | Temporary by definition; note end date |
| `promotion_ended` | Sale label gone, price back to prior regular price | Usually **no alert** |
| `availability_change` | e.g. `in_stock` → `out_of_stock` | Opportunity or noise? Check duration |
| `feature_added` / `feature_removed` | Normalized feature list changed | Does it target our differentiators? |
| `messaging_change` | Headline or marketing copy changed | Interpret audience/positioning shift |
| `product_name_change` | Product renamed | Usually low |

## Rules
1. `not_comparable` or `incomplete_data` → **do not report a change**. Put it under
   verification needed with the specific issue (for example "the 2026-11-12 snapshot
   captured the 24 oz variant; the tracked variant is 32 oz").
2. `formatting_only: true` → record under `no_alert_decisions`.
3. Quote `magnitude.pct_display` exactly; never recompute.
4. For price decreases with the caveat "no promotion label", say the permanence is
   unknown, and suggest collecting further observations.
5. Messaging changes are interpretation: label them Medium confidence at most and
   quote the old and new text.
