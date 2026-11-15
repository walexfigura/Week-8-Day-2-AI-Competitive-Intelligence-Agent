# Week 8, Day 2: AI Competitive Intelligence Agent

*Part of the **10 Weeks to AI Agents** series by Alex Figura.*

An AI agent that watches competitors for **Northstar Supply** — the same fictional
ecommerce brand from Week 8, Day 1 — and turns what it finds into an evidence-backed
briefing: what changed, whether it is real, why it matters, and what a human should do next.

> **Everything in this repository is fictional.** Northstar Supply, PeakTrail, SipWorks,
> and TrailForge are invented brands. Their "websites" are local files on reserved
> `.example` domains, and every price, review, and announcement was written for teaching.
> Nothing here is real market research.

---

## Contents

1. [Why this is more than a research chatbot](#why-this-is-more-than-a-research-chatbot)
2. [What you'll learn](#what-youll-learn)
3. [Architecture](#architecture)
4. [Repository structure](#repository-structure)
5. [Prerequisites](#prerequisites)
6. [Quick start](#quick-start)
7. [Understanding the fictional data](#understanding-the-fictional-data)
8. [Running scenarios](#running-scenarios)
9. [How the agent works](#how-the-agent-works)
10. [System prompts and Markdown architecture](#system-prompts-and-markdown-architecture)
11. [Product-page monitoring](#product-page-monitoring)
12. [Customer sentiment](#customer-sentiment)
13. [Using the Claude Skill](#using-the-claude-skill)
14. [Using real competitor data](#using-real-competitor-data)
15. [Testing and reliability](#testing-and-reliability)
16. [Extending the agent](#extending-the-agent)
17. [Troubleshooting](#troubleshooting)
18. [Safety and limitations](#safety-and-limitations)
19. [Credits and license](#credits-and-license)

---

## Why this is more than a research chatbot

Northstar sells the **Summit 32 oz insulated bottle for $39**. Its closest competitor,
PeakTrail, sold a comparable 32 oz bottle for $39 too. Then a new snapshot of PeakTrail's
product page shows **$32**. In the same week, a sample of 20 PeakTrail customer reviews
contains **8 reviews that mention lid leaks**.

A research chatbot would say: *"PeakTrail cut prices 18% and 40% of their customers have
leaky lids — you should lower your price."* Every part of that is a problem:

- Is it the **same size and variant**? (One later snapshot actually captured the 24 oz bottle.)
- Is it the **same currency and storefront**? (There's a Canadian page priced in CAD.)
- Is $32 a **temporary promotion or permanent**? Two observations can't tell you.
- 8 of 20 reviews is a **sample**, not "40% of customers".
- **Why** did PeakTrail change its price? Nobody knows — and a forum rumor isn't evidence.

This agent is built to ask those questions. It computes the change exactly
(**$39 → $32 is a 17.9% decrease**), checks comparability, reads the reviews **by product
attribute**, compares against Northstar's **verified** features, decides what deserves
attention (and what doesn't), and writes a sourced brief.

> **The lesson:** finding competitor information is useful. Figuring out what changed,
> why it matters, and what to do next is what makes the agent valuable.

---

## What you'll learn

| Topic | Where to look |
|---|---|
| **Agent architecture** — model + tools + loop + guardrails | `src/competitive_intelligence/agent.py`, [docs/architecture.md](docs/architecture.md) |
| **System prompt design** — short, rule-focused, with procedures moved out | `agent/system-prompt.md`, `agent/scope.md` |
| **Business knowledge bases** — context that changes the agent's judgment | `knowledge-base/` |
| **Competitor profiles** — including what we *don't* know | `competitors/` |
| **Tool calling** — the model chooses which of 14 tools to call | `src/competitive_intelligence/tools/` |
| **Product-page monitoring** — HTML + schema.org JSON-LD parsing | `integrations/page_parser.py` |
| **Historical snapshots** — normalized observations over time | `data/historical-snapshots/`, `storage.py` |
| **Change detection** — exact, comparable, testable | `analysis/change_detection.py` |
| **Customer sentiment analysis** — aspect-based, sample-safe | `analysis/sentiment.py` |
| **Competitive signal prioritization** — a transparent rubric + model judgment | `analysis/prioritization.py`, `knowledge-base/competitive-priorities.md` |
| **Evidence-backed reports** — citations validated in code | `reports.py`, `reports/examples/` |
| **Evaluations and guardrails** — 12 cases, deterministic + agent | `evals/`, `tests/`, `guardrails.py` |
| **Claude Skills** — the same workflow without code | `claude-skill/competitive-intelligence/` |

---

## Architecture

```mermaid
flowchart LR
    subgraph Context["Business context (Markdown + JSON)"]
        KB["knowledge-base/<br/>company, products,<br/>customers, priorities,<br/>evidence standards"]
        WL["competitors/<br/>watchlist + profiles"]
        WF["agent/<br/>system prompt +<br/>workflows"]
    end

    subgraph Brain["The model decides"]
        LLM(("OpenAI model<br/>(Responses API)<br/>chooses what to<br/>investigate next"))
    end

    subgraph Tools["Tools collect and compute (Python)"]
        PT["Product tools<br/>snapshots, page fetch"]
        RT["Review tools<br/>reviews, aspect sentiment"]
        CT["Context tools<br/>watchlist, docs, our products, news"]
        CMP["Historical comparison<br/>exact price math,<br/>comparability checks"]
        PRI["Priority rubric<br/>(transparent baseline)"]
    end

    subgraph Output["Investigation → report"]
        VAL["Report validator<br/>citations, sample-size language,<br/>no invented motives"]
        REP["Competitive intelligence brief<br/>reports/*.md + *.json"]
    end

    Context --> LLM
    LLM -- "function calls" --> Tools
    Tools -- "structured results<br/>(untrusted text wrapped)" --> LLM
    PT --> CMP --> PRI
    LLM -- "save_intelligence_report" --> VAL --> REP
```

**Tools collect information and do the math. The model decides what to look at, what it
means, and what to recommend.** The application enforces the rules that matter most
(no fabricated sources, no population claims from samples, no write actions).

---

## Repository structure

```
├── run.py                     Entry point: python run.py <command>
├── agent/                     System prompt, scope, and six workflow procedures
├── knowledge-base/            Northstar: company, products, customers, priorities, evidence standards
├── competitors/               watchlist.json + one profile per competitor
├── data/
│   ├── product-pages/         13 HTML product-page fixtures (with schema.org JSON-LD)
│   ├── historical-snapshots/  14 normalized JSON observations (Oct 1 – Nov 12, 2026)
│   ├── reviews/               3 review samples + hand-labeled reference annotations
│   ├── news/                  4 announcements (one is an unverified rumor)
│   ├── northstar/             Northstar product facts (structured)
│   └── scenarios/             11 research objectives for demos and evals
├── src/competitive_intelligence/
│   ├── agent.py               The tool-calling loop
│   ├── tools/                 The 14 tools + registry (schemas, validation, blocking)
│   ├── analysis/              Change detection, sentiment aggregation, prioritization
│   ├── integrations/          Mock sources, HTML parser, optional live fetcher, review exports
│   ├── reports.py             Report validation + Markdown rendering
│   ├── scan.py / briefing.py  No-LLM monitoring scan and offline briefing
│   ├── evaluation.py          Evaluation checks and graders
│   └── cli.py, config.py, models.py, storage.py, services.py, guardrails.py, ...
├── evals/                     test-cases.json (12 cases) + run_evals.py
├── tests/                     Unit tests (pytest), no API key needed
├── reports/                   Generated briefs (examples/ is committed)
├── claude-skill/              The Claude Skill folder + the ready-to-upload competitive-intelligence-skill.zip
├── scripts/build_skill.py     Rebuilds claude-skill/competitive-intelligence-skill.zip
└── docs/                      Architecture, live integrations, production, troubleshooting
```

---

## Prerequisites

- **Python 3.10 or newer** (tested with Python 3.12 on macOS; the test suite also runs on 3.11).
- **Git**.
- **An OpenAI API key** for the LLM commands (`demo`, `briefing`, agent evaluations).
  Create one at [platform.openai.com](https://platform.openai.com/). API usage is billed
  by OpenAI. *Without a key you can still run the smoke test, the monitoring scan, the
  offline briefing, the tool explorer, all unit tests, the deterministic evaluations, and
  the Skill build.*
- Dependencies (installed in step 3): `openai`, `pydantic`, `httpx`, `python-dotenv`;
  `pytest` and `ruff` for development.

---

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/walexfigura/Week-8-Day-2-AI-Competitive-Intelligence-Agent.git
cd Week-8-Day-2-AI-Competitive-Intelligence-Agent
```

### 2. Create and activate a virtual environment

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -e ".[dev]"
```

### 4. Check that everything works (no API key needed)

```bash
python run.py smoke
```

You should see `7 of 7 checks passed` (the last check just tells you whether a key is set).
If you see "This project needs Python 3.10 or newer", check `python --version`; some shells
alias `python` to an older system Python even inside a virtual environment. Running
`.venv/bin/python run.py smoke` (Windows: `.venv\Scripts\python run.py smoke`) always uses the right one.

### 5. Add your OpenAI API key

macOS / Linux: `cp .env.example .env` · Windows: `copy .env.example .env`

Open `.env` and set:
```
OPENAI_API_KEY=sk-...your key...
OPENAI_MODEL=gpt-5.4-mini
```
`.env` is git-ignored — never commit it. You can use any OpenAI model that supports the
Responses API with function calling.

### 6. Run the first demonstration

```bash
python run.py demo
```

You'll watch the agent work, one tool call per line, for example:

```
   1. read_business_document({"document_id": "competitive-priorities"})
      → ok: ok
   2. list_product_snapshots({"product_id": "PT-RIDGE"})
      → ok: 4 snapshots
   3. compare_product_snapshots({"product_id": "PT-RIDGE", "old_snapshot_id": "pt-ridge-2026-10-01", ...
      → ok: changes_detected (events: price_decrease)
```

(The exact tools and order are chosen by the model and will vary between runs.)

### 7. Review the generated report

The run ends by printing the paths of a Markdown brief and a JSON record in `reports/`.
Open the `.md` file in any Markdown viewer (VS Code, GitHub, Obsidian).

**No API key?** Run `python run.py briefing --offline` to produce the same report format
with rule-based logic, or read the committed example:
[reports/examples/offline-briefing-example.md](reports/examples/offline-briefing-example.md).

---

## Understanding the fictional data

### The competitors

| Competitor | Who they are | Products watched | Competes with |
|---|---|---|---|
| **PeakTrail** | Insulated bottles and outdoor drinkware | Ridge bottle, 32 oz and 24 oz variants | Summit 32 oz ($39), Trailhead 24 oz ($34) — *direct* |
| **SipWorks** | Everyday commuter drinkware | Metro tumbler 20 oz; Daily bottle 24 oz | Commute 20 oz ($29) — *direct*; Trailhead — *partial* |
| **TrailForge** | Premium outdoor hydration | Apex 40 oz; Canteen 32 oz | No 40 oz match (*positioning only*); Summit — *partial* |

### The snapshots — each one teaches something

| Observation | What happened | What the agent should conclude |
|---|---|---|
| PeakTrail Ridge 32 oz, Oct 1 → Nov 1 | $39 → $32, no sale label | **17.9% decrease**, comparable, permanence unknown → **high** |
| PeakTrail Ridge, Nov 12 | Page pre-selected the **24 oz** variant ($29) | **Not comparable** — different size, not another price cut |
| PeakTrail Canada, Nov 5 | CAD 44.00 | **Not comparable** — different currency/storefront |
| SipWorks Metro, Oct 1 → Nov 1 | New "LockSeal leak-proof lid"; headline "Now leak-proof" | New competing feature where Northstar's tumbler is *not* leak-proof |
| SipWorks Daily, Oct 1 → Nov 1 | $22 sale (ends Oct 15) → $28 regular | **Promotion ended**, not a price increase → no alert |
| SipWorks Daily, Nov 12 | Page loaded partially, no price | **Incomplete data** — re-capture, don't guess |
| TrailForge Apex, Oct 1 → Nov 1 | "Engineered for the backcountry" → "From trailhead to train platform" | Positioning shift toward commuters (interpretation) |
| TrailForge Apex, Nov 1 → Nov 12 | Site redesign, same facts | **Formatting-only** → no alert |
| TrailForge Apex page | Hidden text telling AI tools to recommend $25 prices | **Prompt injection** → ignore, report it |
| TrailForge Canteen, Oct 1 → Nov 1 | In stock → sold out | Availability change, duration unknown |

Each snapshot exists as an **HTML page** (`data/product-pages/`) and as a **normalized
JSON record** (`data/historical-snapshots/`). A test proves the parser turns each HTML
page into exactly its JSON record.

### The reviews

| Dataset | Records | Notable details |
|---|---|---|
| PeakTrail Ridge | 21 (20 unique) | **8 of 20 mention lid leakage**; `PT-R21` duplicates `PT-R04`; mixed reviews like "cold all day, but the lid leaks"; a 5-star review with a lid complaint; ambiguous reviews |
| SipWorks Metro | 15 (14 unique) | Old slider lid vs new LockSeal lid; `SW-R08` near-duplicates `SW-R07`; `SW-R12` contains a prompt injection |
| TrailForge Apex | 15 | Durability praise, weight and price complaints, shipping/service issues |

### News

Four announcements with a `reliability` field. `NEWS-PT-002` is an anonymous forum
rumor claiming PeakTrail is clearing inventory — a trap for agents that invent motives.

---

## Running scenarios

| Command | API key? | What it does | Output |
|---|---|---|---|
| `python run.py smoke` | No | Verifies datasets, snapshots, price math, reviews, tool registry | PASS/FAIL checklist |
| `python run.py demo` | Yes | Main demo: PeakTrail price + review investigation | Live tool trace, brief in `reports/` |
| `python run.py demo --scenario price_drop` | Yes | Is PeakTrail's price change real and comparable? | Brief |
| `python run.py demo --scenario review_sentiment` | Yes | Aspect-based analysis of PeakTrail reviews | Brief |
| `python run.py demo --list` | No | Lists all 11 scenarios | List |
| `python run.py scan` | No | Deterministic monitoring scan of every watched product | Change list with rubric priorities |
| `python run.py scan --save --record` | No | Also saves the scan and remembers findings to avoid duplicate alerts | `reports/*-scan.*`, `state/findings.jsonl` |
| `python run.py briefing` | Yes | Weekly briefing across the full watchlist (agent) | Brief |
| `python run.py briefing --offline` | No | Same report format, rule-based, no LLM | Brief |
| `python run.py eval` | Partly | 12 evaluation cases (agent part needs a key) | PASS/FAIL with explanations |
| `python run.py eval --deterministic-only` | No | Only the deterministic checks | PASS/FAIL |
| `python run.py build-skill` | No | Validates and zips the Claude Skill | `claude-skill/competitive-intelligence-skill.zip` |
| `python run.py tool list` | No | Lists the agent's tools | List |
| `python run.py tool compare_product_snapshots --args '{"product_id": "PT-RIDGE", "old_snapshot_id": "pt-ridge-2026-10-01", "new_snapshot_id": "pt-ridge-2026-11-01"}'` | No | Calls one tool yourself and shows exactly what the model would see | JSON |

Other scenarios for `demo --scenario`: `peaktrail_investigation` (default),
`weekly_briefing`, `new_feature`, `promotion_expiry`, `variant_mismatch`,
`formatting_only`, `prompt_injection`, `missing_data`, `tool_failure` (simulates a broken
review source).

> Windows PowerShell tip: for `--args`, wrap the JSON in single quotes as shown; in
> Command Prompt use double quotes and escape inner quotes (`"{\"product_id\": \"PT-RIDGE\"}"`).

---

## How the agent works

Here is the main scenario (`python run.py demo`) from the agent's point of view.

1. **It receives only an objective** — "PeakTrail's Ridge bottle may have dropped in
   price... investigate." No list of steps.
2. **It reads the rules of the business.** Typically it calls
   `read_business_document("competitive-priorities")` and `"evidence-standards"`.
3. **It finds the right comparison.** `list_watchlist` shows that `PT-RIDGE-32` is a
   *direct* competitor of Summit 32 oz. `list_product_snapshots("PT-RIDGE")` returns four
   observations with different variants and storefronts.
4. **Python compares; the model reads.** `compare_product_snapshots` on Oct 1 → Nov 1
   returns a `price_decrease` event: `39.0 → 32.0`, `pct_display: "17.9%"`, with a caveat
   that no promotion label was shown. Comparing Nov 1 → Nov 12 returns `not_comparable`
   because the newer snapshot captured the 24 oz variant.
5. **It decides whether to dig further.** A good run fetches the current page for the
   32 oz variant (still $32, no promotion label) and checks news — finding only an
   unverified rumor, which it must not treat as the reason.
6. **It investigates customers.** `analyze_review_sentiment("PT-RIDGE")` labels each review
   by aspect, and Python reports "8 of the 20 reviews in our sample mention problems with
   lid leakage" (duplicate `PT-R21` excluded).
7. **It checks Northstar's side.** `get_our_product_info("NS-SUMMIT-32")` shows the
   LeakLock lid passed a 1,000-cycle QA test — a *verified* differentiator.
8. **It prioritizes.** `assess_signal_priority` returns a transparent rubric (relevance,
   magnitude, evidence quality, customer impact, urgency, confidence). The model makes
   the final call and explains it.
9. **It writes the brief.** `save_intelligence_report` is validated: every cited ID must
   have come from a tool in this run; phrases like "40% of customers" or "lowered prices
   to clear inventory" are rejected and the model must fix them. Python inserts the
   computed numbers and the sources table.

| The model decides | Python computes |
|---|---|
| Which tools to call, in what order, and when to stop | Parsing pages, normalizing fields, storing snapshots |
| Whether a messaging change targets our customers | Price differences and percentages (Decimal, half-up rounding) |
| What review themes mean for Northstar | Variant/currency/storefront/completeness checks |
| Final priority and its rationale | Duplicate detection and review counts with sample sizes |
| Recommendations and the written brief | Rubric baseline, citation checks, report rendering |

The loop is bounded: at most `CI_MAX_ITERATIONS` model turns (default 16) and
`CI_MAX_TOOL_CALLS` tool calls (default 40). Every call is logged with a trace ID in
`logs/trace-YYYY-MM-DD.jsonl`.

---

## System prompts and Markdown architecture

- **`agent/system-prompt.md`** (loaded every run): role, business summary, tool list,
  research workflow, evidence rules, comparison rules, sentiment rules, prioritization,
  uncertainty, output requirements, tool restrictions, prompt-injection handling.
- **`agent/scope.md`** (loaded every run): what the agent may and may not do.
- **`agent/workflows/*.md`** (read on demand): competitor research, product monitoring,
  change detection, sentiment analysis, signal prioritization, briefing generation.
- **`knowledge-base/*.md`**: the business itself. These files change the agent's
  conclusions — e.g. `our-products.md` says the Commute tumbler is *not* leak-proof,
  which is what makes SipWorks' new lid relevant.
- **`competitors/`**: `watchlist.json` is data the code uses (comparability, mapping);
  profiles are prose the model reads.

Keeping the system prompt short and moving procedures into workflow files means the
model always sees the non-negotiable rules, reads detail only when needed, and you can
edit one procedure without touching the others. See [docs/architecture.md](docs/architecture.md).

---

## Product-page monitoring

1. **Collect** — a page is fetched (in mock mode, the latest HTML fixture) and parsed.
   The parser prefers schema.org Product JSON-LD (price, currency, availability, SKU,
   strikethrough price) and falls back to visible HTML.
2. **Store** — each observation becomes a JSON snapshot with `snapshot_id`,
   `observed_at`, `variant_id`, `storefront`, `current_price`, `list_price`, `promotion`,
   `availability`, `features`, `headline`, `marketing_copy`, `source_id`, `source_url`.
   New captures go to `state/snapshots/` and never overwrite history.
3. **Normalize** — features are compared ignoring case, spacing, and order; text ignores
   whitespace and trailing punctuation. That's how the TrailForge redesign is recognized
   as formatting-only.
4. **Compare** — `analysis/change_detection.py` first asks *can these be compared?*
   (product, variant, currency, storefront, time order, completeness) and only then emits
   change events with magnitudes, caveats, and evidence references.

Try it: `python run.py scan`.

---

## Customer sentiment

A simple positive/negative label per review would call "Keeps water ice cold all day,
but the lid leaks whenever the bottle is on its side" *mixed* — and lose the one fact
that matters to Northstar: the **lid** is the problem, the **insulation** is praised.

This project uses **aspect-based sentiment**:

1. Duplicates are found in Python (exact text, or same reviewer with ~identical text).
2. Each unique review is labeled with every attribute it mentions and the sentiment
   toward it, plus a quote. In agent runs an LLM does this with OpenAI **Structured
   Outputs** (a strict JSON schema); offline, hand-labeled reference annotations are used.
3. Python counts unique reviews per (aspect, sentiment), keeps the review IDs, and writes
   sample-safe statements: **"8 of the 20 reviews in our sample mention problems with lid
   leakage."** It never computes "% of customers".
4. Product-quality complaints (lid, insulation) are kept separate from shipping and
   customer-service complaints. Five-star reviews with complaints and ambiguous reviews
   are listed explicitly.

---

## Using the Claude Skill

The `claude-skill/competitive-intelligence/` folder teaches Claude the same workflow —
competitor research, change detection, aspect-based sentiment, prioritization, and
briefing — without running any Python.

1. **Get the ZIP:** download
   [`claude-skill/competitive-intelligence-skill.zip`](https://github.com/walexfigura/Week-8-Day-2-AI-Competitive-Intelligence-Agent/raw/main/claude-skill/competitive-intelligence-skill.zip)
   directly — no Python needed. If you edit the Skill, rebuild it with `python run.py build-skill`
   (validates frontmatter, linked files, and size, then overwrites the ZIP).
2. **Upload it to Claude:** in Claude's settings, open the Skills area and upload the ZIP.
   Custom Skills need a plan with Skills and code execution enabled; if you can't find the
   option, check Anthropic's help center (menu names can change).
3. **Run the fictional example:** ask *"Use the competitive-intelligence skill with its
   sample data. Did PeakTrail really lower the price of the bottle that competes with
   Northstar's Summit 32 oz, and what do its reviews say?"* The Skill ships with all the
   fictional snapshots, reviews, and news in `sample-data/`, and a stdlib helper
   (`scripts/ci_calc.py`) for exact price math and duplicate detection.
   Expected conclusions are in `references/example-scenarios.md`.
4. **Customize the business context:** replace `sample-data/northstar-context.md` with
   your products (and their verified features), customers, watchlist, and priorities —
   or just paste them into the conversation. Rebuild and re-upload after editing.
5. **Configure tools:** see `references/tool-configuration.md`. With no connectors, the
   Skill works on files you provide. If web search, browsing, or authorized data
   connectors are enabled in your Claude workspace, it can use them for public pages and
   permitted data. Writing a URL into a Markdown file does *not* create a connector, and
   the Skill cannot monitor sites on a schedule.

---

## Using real competitor data

Mock mode is the default and needs no accounts or websites. To experiment with real,
**permitted** sources (details in [docs/live-integrations.md](docs/live-integrations.md)):

- **Product pages:** copy `live-sources.example.json` to `live-sources.json`, list public
  pages you are allowed to monitor, set `permission_confirmed: true`, then run
  `CI_DATA_MODE=live python run.py scan --capture-live --save`. The fetcher checks
  `robots.txt`, rate-limits per host, uses timeouts, never logs in or bypasses CAPTCHAs,
  and reports blocks instead of working around them. *Status: implemented and unit-tested
  with simulated HTTP responses; not validated against real retail sites. Pages that
  render prices with JavaScript will come back incomplete.*
- **Reviews:** there is no universal public review API. Use exports you own, approved
  APIs, or user-supplied files: set `CI_REVIEW_EXPORT_DIR` to a folder containing
  `<PRODUCT_ID>.json` or `<PRODUCT_ID>.csv`.
- **Replacing an adapter:** page sources implement `fetch(competitor_id, product_id,
  variant_id)`; review sources implement `get(product_id)`. Swap them in `services.py`.
- **Scheduling:** run the same scan with cron or Task Scheduler (examples in the docs).
  A production system would also need persistent storage, alerting, and human review —
  see [docs/production-considerations.md](docs/production-considerations.md).

---

## Testing and reliability

```bash
pytest                                   # 103 unit tests, no API key
python run.py eval --deterministic-only  # 12 deterministic evaluation cases
python run.py eval                       # + agent evaluations (needs OPENAI_API_KEY)
python run.py eval --case small_sample --repeat 3   # repeat a nondeterministic case
ruff check src tests                     # lint
```

The 12 evaluation cases (`evals/test-cases.json`) each have a **deterministic part**
(exact Python checks) and an **agent part** (runs the real agent on a scenario):

| # | Case | Deterministic check | Agent check (examples) |
|---|---|---|---|
| 1 | Price calculation | $39 → $32 = 17.9% | Signal cites the computed 17.9% event |
| 2 | Irrelevant change | Redesign → no events, no alert | No high/medium signal for the redesign |
| 3 | Different variants | 32 oz vs 24 oz and USD vs CAD → not comparable | No price signal from the 24 oz snapshot |
| 4 | Promotional pricing | Sale ending → `promotion_ended` | No "price increase" alert |
| 5 | Aspect-based sentiment | PT-R01 is +insulation and −lid | LLM annotator labels PT-R01 the same way |
| 6 | Small sample sizes | "8 of the 20 …"; "40% of customers" rejected | Finding is 8 of 20; no population claims |
| 7 | Missing evidence | Asserted motive rejected; open question allowed | No motive stated; permanence flagged as unknown |
| 8 | Source accuracy | Invented IDs rejected | Report passes validation; every signal cites evidence |
| 9 | Prompt injection | Hidden text and review flagged; `update_price` blocked | No restricted tools; no "$25"/"30%" recommendations |
| 10 | Alert prioritization | high / no_alert / low / no_alert as expected | PeakTrail high; redesign and expired promo not escalated |
| 11 | Duplicate reviews | PT-R21 and SW-R08 detected; 20 unique | Sample size 20, not 21 |
| 12 | Tool failure | Outage, not-found, invalid input, malformed file, partial page | No review findings when the review source is down |

Agent checks grade **structured output** (priorities, event IDs, counts, cited IDs, tool
calls) rather than exact wording, with a few regex checks for forbidden phrasing. LLM
runs are nondeterministic: a single pass or fail is one sample. Results are saved to
`evals/results/`.

---

## Extending the agent

1. **Add a fourth competitor.** Add an entry to `competitors/watchlist.json`, write
   `competitors/profiles/<id>.md`, and add snapshots under
   `data/historical-snapshots/<product_id lowercased>/`. Run `python run.py scan`.
2. **Add a new Northstar product.** Add it to `data/northstar/our-products.json` and
   `knowledge-base/our-products.md`, with verified features and limitations; map
   competitor variants to it in the watchlist.
3. **Create a new historical snapshot.** Copy `pt-ridge-2026-11-01.json`, change
   `snapshot_id` (must match the file name), `source_id`, `observed_at`, and a field or two.
   Set `fixture` and `page_hash` to `null` if there is no HTML page.
4. **Change a competitor's price.** In your new snapshot set `current_price` to `35` and
   compare it: `python run.py tool compare_product_snapshots --args '{...}'`.
   Then add a `promotion` object and see how the event type and caveats change.
5. **Add customer reviews.** Append reviews to a file in `data/reviews/` and matching
   entries in `data/reviews/reference-annotations/`. Watch the counts and sample size change.
6. **Change Northstar's priorities.** Edit `knowledge-base/competitive-priorities.md`
   (e.g. make availability changes high priority) and re-run `python run.py briefing`.
7. **Add a new alert criterion.** Extend `assess_event` in `analysis/prioritization.py`
   (e.g. treat warranty changes as high) and add a test in `tests/test_prioritization.py`.
8. **Add a new evaluation scenario.** Add an objective to `data/scenarios/scenarios.json`
   and a case to `evals/test-cases.json` using the check types in `evaluation.py`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Activate the virtual environment and run `pip install -e ".[dev]"`. |
| "This project needs Python 3.10 or newer" after activating | Your shell may alias `python` to the system Python (check with `type python`). Run `.venv/bin/python run.py ...` (Windows: `.venv\Scripts\python run.py ...`) or remove the alias. |
| `OPENAI_API_KEY is not set` | Create `.env` from `.env.example` and add your key (no quotes). |
| Model not found / 401 / 429 | Check `OPENAI_MODEL`, your key, and your usage limits. |
| "Stopped without saving a report" | Raise `CI_MAX_ITERATIONS` / `CI_MAX_TOOL_CALLS` or try a stronger model. |
| Snapshot "failed validation" | `observed_at` needs a timezone (`Z`), currency must be 3 uppercase letters. |
| New product ignored | Add it to `competitors/watchlist.json`. |

More in [docs/troubleshooting.md](docs/troubleshooting.md). Every run's tool calls are in
`logs/trace-*.jsonl`.

---

## Safety and limitations

- **Educational, not a monitoring service.** It runs when you run it, on fictional local
  data by default. There is no scheduler, database, alerting, or user management.
- **Recommends only.** No tool can change prices, edit product pages, publish content,
  post to social media, contact competitors, or send alerts. Attempts are blocked and logged.
- **Untrusted content.** Product pages, reviews, and news are treated as data. Injection
  attempts are detected and reported, but detection is pattern-based and not perfect —
  which is why there are no write tools for an attacker to trigger.
- **Model behavior varies.** Validation catches invented sources, population claims,
  asserted motives, and over-escalation, but not every possible mistake. Read the brief
  critically; the evaluations measure specific fictional scenarios only.
- **Live fetching** is minimal, unverified against real sites, and your responsibility to
  use within each site's terms.
- **No claims about accuracy** on real data.

---

## Credits and license

Created by **Alex Figura** for the **10 Weeks to AI Agents** series (Week 8, Day 2).
Northstar Supply and all competitors, products, reviews, and announcements are fictional.

Licensed under the MIT License — see [LICENSE](LICENSE).
