# Northstar Supply — Competitive Priorities

> Used by the agent (and by `analysis/prioritization.py`) to decide what deserves
> attention. Fictional business context for a teaching project.

## What matters most (consider for HIGH priority)

1. **Price changes on directly comparable products.** A change of 10% or more on a
   variant mapped as `direct` in `competitors/watchlist.json` — for example a 32 oz
   bottle competing with Summit at $39. Only after confirming the same variant,
   currency, and storefront.
2. **New competing features that target our differentiators.** Especially leak-proof
   lids, insulation claims, or warranty changes on products competing with ours.
3. **Recurring customer complaints about a competitor product that our verified
   features address** (for example repeated lid-leak complaints when our lid has
   verified QA results). Recurring = mentioned in at least 3 unique reviews in the sample.

## Worth tracking (usually MEDIUM priority)

4. **Availability changes** on comparable products (sold out, discontinued, back in stock).
5. **Changes in competitor positioning or messaging** that move toward our customer
   segments (for example an expedition brand marketing to commuters).
6. **New launches** that address the same target audience.
7. Price changes of 5–10% on direct comparables, or 10%+ on partially comparable products.

## Usually LOW priority (record, do not alert)

- Price changes under 5%, or changes on products we do not compete with.
- New colors, photography, or packaging with no functional change.
- One-off reviews (a single extreme review is not a trend).
- Shipping or customer-service complaints about a competitor (relevant context, but
  not about the product itself).

## Not an alert at all

- **Formatting-only page changes** (layout, CSS, reordered feature lists, capitalization)
  where the normalized product facts are unchanged.
- The **end of a promotion that returns a price to its previously shown regular price**
  (record it; it is not a new price increase).

## Insufficient evidence (report as "needs verification")

- Snapshots that cannot be compared safely: different variants, currencies, or
  storefronts; missing or partial data.
- Claims from unverified sources (anonymous forum posts, rumors).
- Anything about a competitor's *reasons* or *strategy* — we cannot observe motives.

## Actions the business may take (humans decide)

| Recommendation the agent may make | Who decides |
|---|---|
| Review pricing on an affected product | Head of Ecommerce |
| Investigate a new competitor feature | Product team |
| Check our product-page positioning | Marketing Lead |
| Examine a recurring complaint theme | Product + Support |
| Collect more observations to verify a change | CI analyst |
