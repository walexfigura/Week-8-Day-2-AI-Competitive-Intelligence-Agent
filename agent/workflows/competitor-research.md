# Workflow: Competitor Research

Use when the objective names a competitor or asks "what is X doing?".

1. `get_competitor_profile(competitor_id)` — note what we already know **and** what the
   profile says we do not know. Do not fill those gaps with assumptions.
2. `list_watchlist` — find the competitor's tracked variants and the Northstar product
   each maps to, with its comparability (`direct`, `partial`, `none`).
3. For each tracked product, follow **product-monitoring** and **change-detection**.
4. `get_competitor_news(competitor_id)` — read announcements. Weigh them by
   `reliability`: `primary_source` (the company's own statement) can confirm *what*
   the company said; `unverified` sources (forums, rumors) cannot support conclusions.
5. If reviews exist for the product, follow **sentiment-analysis**.
6. `get_our_product_info` for the mapped Northstar product before writing any
   recommendation — only verified features can be called differentiators.

**Good research question:** "Is PeakTrail's 32 oz Ridge listed lower than our Summit,
for the same size, in the same currency, and do we know whether it is a promotion?"

**Bad research question:** "Why is PeakTrail trying to undercut us?" (assumes a motive
we cannot observe).
