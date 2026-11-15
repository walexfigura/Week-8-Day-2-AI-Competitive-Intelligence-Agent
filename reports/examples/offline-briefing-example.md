# Northstar Supply Competitive Intelligence Brief (offline, rule-based)

> **Fictional data.** All companies, products, prices, and reviews in this report are FICTIONAL sample data from the Northstar Supply teaching project (10 Weeks to AI Agents). This is not real market research.

- **Generated:** 2026-11-15T18:37:58+00:00
- **How this report was produced:** Deterministic offline briefing (no LLM). Rule-based templates over the same tools; priorities are the rubric baseline without analyst judgment; review aspects use hand-labeled reference annotations.
- **Scenario:** `offline_briefing` · **Trace ID:** `ci-20261115-1c7b9b` · **Data mode:** mock (fictional fixtures)

## Executive summary

Top signal (high): PeakTrail Ridge Insulated Bottle (32 oz): price decrease — Listed price decrease of 17.9% ($39.00 USD → $32.00 USD). Signals by rubric baseline: 2 high, 1 medium, 1 low. Customer sentiment: 8 of the 20 reviews in our sample mention problems with lid leakage. 2 changes did not warrant an alert, and 3 items need verification. This is a rule-based offline briefing; run the LLM agent for interpretation of messaging and context.

## High-priority signals

### 1. PeakTrail Ridge Insulated Bottle (32 oz): price decrease

| | |
|---|---|
| **Priority** | High |
| **Competitor** | peaktrail |
| **Product** | PT-RIDGE (variant PT-RIDGE-32) |
| **What changed** | Listed price decrease of 17.9% ($39.00 USD → $32.00 USD). price decrease (current_price) |
| **Previous observation** | $39.00 USD, in_stock, headline 'Cold for 24 hours. Built for the trail.' on 2026-10-01T15:00:00Z (pt-ridge-2026-10-01). |
| **New observation** | $32.00 USD, in_stock, headline 'Cold for 24 hours. Built for the trail.' on 2026-11-01T15:00:00Z (pt-ridge-2026-11-01). |
| **Computed change (Python)** | 39.00 → 32.00: decrease of 17.9% (exact 17.95%, formula (39 - 32) / 39 * 100) |
| **Data caveat** | The new page shows no promotion label, strikethrough price, or end date. Two observations cannot show whether this price is temporary or permanent. |
| **Why it matters** | Watchlist mapping: direct comparable to Northstar Summit Insulated Bottle 32 oz ($39.00 USD). Directly comparable to NS-SUMMIT-32. Price changed by 17.9% (computed in Python). |
| **Supporting evidence** | `pt-ridge-2026-10-01`, `pt-ridge-2026-11-01`, `src-pt-ridge-2026-10-01`, `src-pt-ridge-2026-11-01`, `evt-5fc825c914` |
| **Confidence** | Medium |
| **Uncertainty** | The new page shows no promotion label, strikethrough price, or end date. Two observations cannot show whether this price is temporary or permanent. |
| **Why this priority** | Rubric baseline (no analyst judgment applied): business relevance high; magnitude high; evidence quality medium; customer impact unknown; urgency high; confidence high. |
| **Recommended next step** | Head of Ecommerce: review Northstar Summit Insulated Bottle 32 oz pricing against this listing. Before acting, capture at least two more observations of the same variant to see whether the price holds or a promotion label appears. |

### 2. SipWorks Metro Commuter Tumbler (20 oz): feature added, feature removed, messaging change

| | |
|---|---|
| **Priority** | High |
| **Competitor** | sipworks |
| **Product** | SW-METRO (variant SW-METRO-20) |
| **What changed** | feature added (features: 'LockSeal leak-proof lid'); feature removed (features: 'Splash-resistant slider lid'); messaging change (headline: Your commute, upgraded. → Now leak-proof. Toss it in your bag.); messaging change (marketing_copy: A slim tumbler that slides into any cup holder and keeps you → The Metro now ships with our new LockSeal lid, so you can th) |
| **Previous observation** | $27.00 USD, in_stock, headline 'Your commute, upgraded.' on 2026-10-01T15:10:00Z (sw-metro-2026-10-01). |
| **New observation** | $27.00 USD, in_stock, headline 'Now leak-proof. Toss it in your bag.' on 2026-11-01T15:10:00Z (sw-metro-2026-11-01). |
| **Data caveat** | Feature text comes from the competitor's page; it is a claim, not a verified test result. |
| **Data caveat** | Interpreting what a messaging change means is a judgment call, not a measured fact. |
| **Why it matters** | Watchlist mapping: direct comparable to Northstar Commute Tumbler 20 oz ($29.00 USD). Directly comparable to NS-COMMUTE-20. Feature relates to a Northstar differentiator (leak resistance/insulation/warranty). |
| **Supporting evidence** | `sw-metro-2026-10-01`, `sw-metro-2026-11-01`, `src-sw-metro-2026-10-01`, `src-sw-metro-2026-11-01`, `evt-c6a1d56218`, `evt-56e6665f2b`, `evt-4da9f5b2ca`, `evt-f3874e451a` |
| **Confidence** | High |
| **Uncertainty** | Feature text comes from the competitor's page; it is a claim, not a verified test result. Interpreting what a messaging change means is a judgment call, not a measured fact. |
| **Why this priority** | Rubric baseline (no analyst judgment applied): business relevance high; magnitude high; evidence quality high; customer impact unknown; urgency medium; confidence high. |
| **Recommended next step** | Product team: investigate the new competing feature and how it compares with Northstar Commute Tumbler 20 oz's documented limitations. |

## Medium-priority signals

### 1. TrailForge Canteen Bottle (32 oz): availability change

| | |
|---|---|
| **Priority** | Medium |
| **Competitor** | trailforge |
| **Product** | TF-CANTEEN (variant TF-CANTEEN-32) |
| **What changed** | availability change (availability) |
| **Previous observation** | $45.00 USD, in_stock, headline 'The classic, rebuilt.' on 2026-10-01T15:40:00Z (tf-canteen-2026-10-01). |
| **New observation** | $45.00 USD, out_of_stock, headline 'The classic, rebuilt.' on 2026-11-01T15:40:00Z (tf-canteen-2026-11-01). |
| **Data caveat** | A single observation cannot show how long the product will be unavailable. |
| **Why it matters** | Watchlist mapping: partial comparable to Northstar Summit Insulated Bottle 32 oz ($39.00 USD). Partially comparable to NS-SUMMIT-32. Availability changed from in_stock to out_of_stock. |
| **Supporting evidence** | `tf-canteen-2026-10-01`, `tf-canteen-2026-11-01`, `src-tf-canteen-2026-10-01`, `src-tf-canteen-2026-11-01`, `evt-3d12542594` |
| **Confidence** | Medium |
| **Uncertainty** | A single observation cannot show how long the product will be unavailable. |
| **Why this priority** | Rubric baseline (no analyst judgment applied): business relevance medium; magnitude medium; evidence quality medium; customer impact unknown; urgency medium; confidence high. |
| **Recommended next step** | Re-check availability next week; if it stays unavailable, Marketing may review whether Northstar Summit Insulated Bottle 32 oz messaging reaches customers searching for this product. |

## Customer sentiment

**PT-RIDGE** — 20 unique reviews analyzed (21 records received; duplicates excluded: `PT-R21` (exact duplicate of `PT-R04`)). Annotations: reference_annotations (hand-labeled by the course author).

_Convenience sample of visible reviews. Counts describe this sample only, not all customers._

| Theme | Count in sample | Recurring? | Supporting reviews | Interpretation |
|---|---|---|---|---|
| 8 of the 20 reviews in our sample mention problems with lid leakage. | 8 of 20 | Yes | `PT-R01`, `PT-R04`, `PT-R06`, `PT-R08`, `PT-R11`, `PT-R13`, `PT-R16`, `PT-R19` | Recurring product quality theme in this sample. Relates to a verified Northstar feature: Northstar Trailhead Insulated Bottle 24 oz (Northstar QA report QA-2025-031 (internal, fictional)); Northstar Summit Insulated Bottle 32 oz (Northstar QA report QA-2026-014 (internal, fictional), 2026-06-12). Check whether our product page communicates it; do not make comparative claims without testing the competitor product. |
| 7 of the 20 reviews in our sample mention good insulation (drinks staying cold or hot). | 7 of 20 | Yes | `PT-R01`, `PT-R02`, `PT-R06`, `PT-R08`, `PT-R12`, `PT-R13`, `PT-R17` | Recurring product quality theme in this sample. |
| 3 of the 20 reviews in our sample mention liking the design. | 3 of 20 | Yes | `PT-R05`, `PT-R06`, `PT-R20` | Recurring product quality theme in this sample. |
| 3 of the 20 reviews in our sample mention good value or price. | 3 of 20 | Yes | `PT-R03`, `PT-R13`, `PT-R17` | Recurring product quality theme in this sample. |

- Ambiguous reviews not counted toward specific themes: PT-R10, PT-R18.

**SW-METRO** — 14 unique reviews analyzed (15 records received; duplicates excluded: `SW-R08` (near duplicate of `SW-R07`)). Annotations: reference_annotations (hand-labeled by the course author).

_Convenience sample of visible reviews. Counts describe this sample only, not all customers._

| Theme | Count in sample | Recurring? | Supporting reviews | Interpretation |
|---|---|---|---|---|
| 5 of the 14 reviews in our sample mention the lid not leaking. | 5 of 14 | Yes | `SW-R06`, `SW-R07`, `SW-R09`, `SW-R13`, `SW-R15` | Recurring product quality theme in this sample. Customers praise a lid capability our comparable product does not have (see its documented limitations). |

- Ambiguous reviews not counted toward specific themes: SW-R14.
- Reviews containing instructions aimed at AI tools (ignored as instructions): SW-R12.

**TF-APEX** — 15 unique reviews analyzed (15 records received; duplicates excluded: none). Annotations: reference_annotations (hand-labeled by the course author).

_Convenience sample of visible reviews. Counts describe this sample only, not all customers._

| Theme | Count in sample | Recurring? | Supporting reviews | Interpretation |
|---|---|---|---|---|
| 3 of the 15 reviews in our sample mention good insulation (drinks staying cold or hot). | 3 of 15 | Yes | `TF-R01`, `TF-R06`, `TF-R10` | Recurring product quality theme in this sample. |

- Ambiguous reviews not counted toward specific themes: TF-R03, TF-R12.

## Lower-priority observations

- **TrailForge Apex Expedition Bottle (40 oz): messaging change** (trailforge, TF-APEX): messaging change (headline: Engineered for the backcountry. → From trailhead to train platform: one bottle for every day.); messaging change (marketing_copy: Built for multi-day expeditions, alpine starts, and river tr → Expedition-grade insulation, now for your everyday routine. ) _Why low:_ Rubric baseline (no analyst judgment applied): business relevance low; magnitude medium; evidence quality high; customer impact unknown; urgency medium; confidence medium. Evidence: `tf-apex-2026-10-01`, `tf-apex-2026-11-01`, `src-tf-apex-2026-10-01`, `src-tf-apex-2026-11-01`
- **No alert — SW-DAILY price 22.0 → 28.0:** The promotion shown on 2026-10-01 ('Fall Sale: $6 off through October 15') is gone and the price returned to the previously shown regular price of 28.00 USD. This is not a new price increase. Evidence: `sw-daily-2026-10-01`, `sw-daily-2026-11-01`
- **No alert — TF-APEX page change (tf-apex-2026-11-01 → tf-apex-2026-11-12):** Formatting-only change: the page layout and markup changed, but price, availability, features, and messaging are the same after normalization. Evidence: `tf-apex-2026-11-01`, `tf-apex-2026-11-12`

## Information requiring verification

- **PT-RIDGE: pt-ridge-2026-11-01 → pt-ridge-2026-11-12 could not be compared** — Different variants: pt-ridge-2026-11-01 captured PT-RIDGE-32 (32 oz) but pt-ridge-2026-11-12 captured PT-RIDGE-24 (24 oz). Prices of different sizes are not comparable. _Suggested check:_ Capture the tracked variant again on the same storefront and compare like with like.
- **SW-DAILY: sw-daily-2026-11-01 → sw-daily-2026-11-12 could not be compared** — Incomplete snapshot data (new snapshot missing current_price, currency, availability, features). _Suggested check:_ Capture the tracked variant again on the same storefront and compare like with like.
- **PT-RIDGE CA storefront (pt-ridge-ca-2026-11-05, CAD)** — Only one observation for the CA storefront; nothing to compare it with in the same currency. _Suggested check:_ Do not convert currencies to compare; track this storefront separately if it matters.

**Open questions (unconfirmed hypotheses — do not treat as findings):**

- Why the PeakTrail Ridge Insulated Bottle price changed is unknown; nothing on the page explains it. An unverified source (NEWS-PT-002) offers an explanation that no other source corroborates.

## Untrusted-content warnings

These sources contained text addressed to AI tools. It was treated as data and not followed.

- `tf-apex-2026-11-01` — hidden page text
- `tf-apex-2026-11-12` — hidden page text
- `SW-R12` — customer review

## Sources

| ID | Type | Observed / published | Source |
|---|---|---|---|
| `pt-ridge-2026-10-01` | snapshot | 2026-10-01T15:00:00Z | https://peaktrail.example/products/ridge-insulated-bottle |
| `pt-ridge-2026-11-01` | snapshot | 2026-11-01T15:00:00Z | https://peaktrail.example/products/ridge-insulated-bottle |
| `src-pt-ridge-2026-10-01` | source | 2026-10-01T15:00:00Z | https://peaktrail.example/products/ridge-insulated-bottle |
| `src-pt-ridge-2026-11-01` | source | 2026-11-01T15:00:00Z | https://peaktrail.example/products/ridge-insulated-bottle |
| `sw-metro-2026-10-01` | snapshot | 2026-10-01T15:10:00Z | https://sipworks.example/shop/metro-commuter-tumbler |
| `sw-metro-2026-11-01` | snapshot | 2026-11-01T15:10:00Z | https://sipworks.example/shop/metro-commuter-tumbler |
| `src-sw-metro-2026-10-01` | source | 2026-10-01T15:10:00Z | https://sipworks.example/shop/metro-commuter-tumbler |
| `src-sw-metro-2026-11-01` | source | 2026-11-01T15:10:00Z | https://sipworks.example/shop/metro-commuter-tumbler |
| `tf-canteen-2026-10-01` | snapshot | 2026-10-01T15:40:00Z | https://trailforge.example/gear/canteen-bottle |
| `tf-canteen-2026-11-01` | snapshot | 2026-11-01T15:40:00Z | https://trailforge.example/gear/canteen-bottle |
| `src-tf-canteen-2026-10-01` | source | 2026-10-01T15:40:00Z | https://trailforge.example/gear/canteen-bottle |
| `src-tf-canteen-2026-11-01` | source | 2026-11-01T15:40:00Z | https://trailforge.example/gear/canteen-bottle |
| `tf-apex-2026-10-01` | snapshot | 2026-10-01T15:30:00Z | https://trailforge.example/gear/apex-expedition-bottle |
| `tf-apex-2026-11-01` | snapshot | 2026-11-01T15:30:00Z | https://trailforge.example/gear/apex-expedition-bottle |
| `src-tf-apex-2026-10-01` | source | 2026-10-01T15:30:00Z | https://trailforge.example/gear/apex-expedition-bottle |
| `src-tf-apex-2026-11-01` | source | 2026-11-01T15:30:00Z | https://trailforge.example/gear/apex-expedition-bottle |
| `PT-R01` | review | 2026-10-03 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R04` | review | 2026-10-09 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R06` | review | 2026-10-14 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R08` | review | 2026-10-18 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R11` | review | 2026-10-24 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R13` | review | 2026-10-28 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R16` | review | 2026-11-03 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R19` | review | 2026-11-07 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R02` | review | 2026-10-04 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R12` | review | 2026-10-26 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R17` | review | 2026-11-04 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R05` | review | 2026-10-11 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R20` | review | 2026-11-08 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `PT-R03` | review | 2026-10-06 | https://peaktrail.example/products/ridge-insulated-bottle#reviews |
| `SW-R06` | review | 2026-10-23 | https://sipworks.example/shop/metro-commuter-tumbler#reviews |
| `SW-R07` | review | 2026-10-26 | https://sipworks.example/shop/metro-commuter-tumbler#reviews |
| `SW-R09` | review | 2026-10-29 | https://sipworks.example/shop/metro-commuter-tumbler#reviews |
| `SW-R13` | review | 2026-11-06 | https://sipworks.example/shop/metro-commuter-tumbler#reviews |
| `SW-R15` | review | 2026-11-09 | https://sipworks.example/shop/metro-commuter-tumbler#reviews |
| `TF-R01` | review | 2026-10-02 | https://trailforge.example/gear/apex-expedition-bottle#reviews |
| `TF-R06` | review | 2026-10-17 | https://trailforge.example/gear/apex-expedition-bottle#reviews |
| `TF-R10` | review | 2026-11-01 | https://trailforge.example/gear/apex-expedition-bottle#reviews |
| `sw-daily-2026-10-01` | snapshot | 2026-10-01T15:20:00Z | https://sipworks.example/shop/daily-bottle |
| `sw-daily-2026-11-01` | snapshot | 2026-11-01T15:20:00Z | https://sipworks.example/shop/daily-bottle |
| `tf-apex-2026-11-12` | snapshot | 2026-11-12T15:30:00Z | https://trailforge.example/gear/apex-expedition-bottle |

---

_The agent recommends; humans decide. No prices, product pages, or external messages were changed or sent by this run._
