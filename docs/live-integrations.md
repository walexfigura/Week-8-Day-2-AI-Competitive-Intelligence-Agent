# Live integrations

Mock mode (the default) reads fictional local files. This page explains how each mock
source maps to real-world data collection, what is implemented, and what is not.

| Mock source | Real-world equivalent | Status in this repo |
|---|---|---|
| `FixturePageSource` (HTML fixtures) | Fetching a public product page | `PublicPageSource` implemented; tested with simulated HTTP only |
| `data/historical-snapshots/` | A snapshot history you collect over time | `SnapshotStore` saves new captures to `state/snapshots/` |
| `FixtureReviewSource` | Review data you are permitted to use | `ExportReviewSource` reads your JSON/CSV exports |
| `data/news/announcements.json` | Press releases, blogs, news | Mock only; supply your own file or use connected tools |
| Manual `python run.py scan` | Scheduled monitoring | Not included; see "Scheduling" |

## Public product-page fetching

`src/competitive_intelligence/integrations/public_web.py`

1. Copy `live-sources.example.json` to `live-sources.json` (git-ignored).
2. List only **public** pages you are allowed to monitor. Set `permission_confirmed: true`
   only after checking the site's terms of service. Entries without it are ignored.
3. Run with `CI_DATA_MODE=live`:
   ```bash
   CI_DATA_MODE=live python run.py scan --capture-live --save
   ```
   Each configured page is fetched once, parsed, and saved as a new snapshot in
   `state/snapshots/<product>/`, then compared with earlier snapshots. In live mode the
   agent's `fetch_product_page` tool also uses this adapter.

What the fetcher does:
- Checks `robots.txt` for every URL (disallowed → no fetch; robots error → no fetch).
- One request per host every `CI_LIVE_MIN_INTERVAL_SECONDS` (default 10 s), with a
  timeout (`CI_LIVE_TIMEOUT_SECONDS`).
- Sends a plain, honest User-Agent; no cookies, logins, or session reuse.
- Stops on 401/403/429 and on pages that look like login or CAPTCHA walls. It never
  tries to bypass them.

What it does **not** do:
- Execute JavaScript. Many stores render prices client-side; those pages will parse
  without a price and the snapshot will be marked incomplete.
- Guarantee compatibility with any particular ecommerce platform.
- Crawl, discover URLs, or follow links.

## Product structured data

The parser prefers schema.org [Product](https://schema.org/Product) JSON-LD:
`offers[].price`, `priceCurrency`, `availability`, `sku`, `priceValidUntil`, and
`priceSpecification` with `priceType: StrikethroughPrice` for list prices. If there is
no JSON-LD, it falls back to visible HTML hooks used by the fixtures
(`.price-current`, `.feature-list`, ...). For a real site you will usually need to adjust
those selectors in `page_parser.py`. Text hidden with `display:none` is kept separately
as `hidden_text` and scanned for prompt injection.

## Review-source limitations

There is no universal public review API, and scraping reviews often violates site terms.
Permitted options:
- **Exports you own** (e.g. reviews of your own products from your platform).
- **Approved APIs** from a review platform or marketplace, under their terms.
- **User-supplied data** (a CSV a team member compiled manually).

Set `CI_REVIEW_EXPORT_DIR=/path/to/exports` and add `<PRODUCT_ID>.json` (same shape as
`data/reviews/*.json`) or `<PRODUCT_ID>.csv` with columns
`review_id,review_date,rating,title,text,source_ref`. Record how the sample was collected —
sample descriptions matter for honest reporting.

To use another source, implement a class with `get(product_id) -> (meta, list[Review])`
and assign it to `Services.reviews`.

## Historical storage and timestamps

- Fixture snapshots are read-only. New captures go to `state/snapshots/` and are never
  overwritten (`SnapshotStore.save` refuses duplicates).
- `observed_at` is the time the page was fetched (UTC) — not the time you analyzed it.
- For reviews, keep `review_date` and the collection timestamp (`collected_at`).

## Rate limiting and terms of service

Monitoring a handful of pages once a day is very different from crawling. Keep the
list small, keep intervals long, and stop if a site objects or blocks you. You are
responsible for complying with each site's terms and applicable law.

## Scheduling

The educational version runs manually. To run the same workflow on a schedule:
- **cron (macOS/Linux):** `0 9 * * * cd /path/to/repo && .venv/bin/python run.py scan --capture-live --save --record`
- **Windows Task Scheduler:** run `.venv\Scripts\python.exe run.py scan ...` daily.
- Then run `python run.py briefing` (agent) when the scan finds something new.

`--record` stores fingerprints of high/medium findings in `state/findings.jsonl`, so the
next scan marks repeats as "already recorded" instead of alerting twice.

## Failure handling

Every source failure becomes a structured tool result (`source_unavailable`,
`malformed_source_data`, `not_found`), never an exception that crashes the run. The agent
is instructed to list gaps under "Information requiring verification" instead of
filling them in, and evaluation case #12 tests this.
