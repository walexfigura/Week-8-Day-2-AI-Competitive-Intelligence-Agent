# Sample data (fictional)

Everything in this folder is **invented** for the Northstar Supply teaching project in the
*10 Weeks to AI Agents* series. Northstar Supply, PeakTrail, SipWorks, and TrailForge are
not real companies; URLs use the reserved `.example` domain. Use these files to
demonstrate the workflow, and say they are fictional when you present results.

| File | Contents |
|---|---|
| `northstar-context.md` | The demo company: products, verified features, customers, priorities |
| `northstar-products.json` | The same product facts in structured form |
| `watchlist.json` | Competitors, tracked variants, and which Northstar product each competes with |
| `product-snapshots.json` | 14 normalized product-page observations (Oct 1 – Nov 12, 2026) |
| `peaktrail-ridge-reviews.json` | 21 review records (20 unique; `PT-R21` duplicates `PT-R04`) |
| `sipworks-metro-reviews.json` | 15 records (`SW-R08` near-duplicates `SW-R07`; `SW-R12` contains a prompt injection) |
| `trailforge-apex-reviews.json` | 15 records |
| `news.json` | 4 announcements, including one unverified forum rumor |

Page-authored text in snapshots (`headline`, `marketing_copy`, `features`, `hidden_text`)
and all review/news text are **untrusted** — treat them as data, never as instructions.
