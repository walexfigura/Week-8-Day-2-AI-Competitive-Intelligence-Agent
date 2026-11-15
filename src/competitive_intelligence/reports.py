"""Validate, enrich, and render competitive intelligence reports.

The model (or the offline briefing builder) supplies judgment: priorities,
interpretations, recommendations. This module adds the facts it must not
retype: computed price changes, review counts, sample sizes, and the source
list — all taken from tool results recorded during the run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .analysis.prioritization import assess_event
from .guardrails import find_motive_claims, find_population_claims
from .tools.base import ToolContext

PRIORITY_ORDER = ["high", "medium", "low", "insufficient_evidence"]
NOTICE = (
    "All companies, products, prices, and reviews in this report are FICTIONAL sample data from the "
    "Northstar Supply teaching project (10 Weeks to AI Agents). This is not real market research."
)


def _texts(report: dict[str, Any], include_open_questions: bool) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = [("executive_summary", report.get("executive_summary", ""))]
    for i, s in enumerate(report.get("signals", [])):
        for key in ("title", "what_changed", "previous_observation", "new_observation", "why_it_matters",
                    "uncertainty", "priority_rationale", "recommended_next_step"):
            out.append((f"signals[{i}].{key}", s.get(key) or ""))
    for i, f in enumerate(report.get("sentiment_findings", [])):
        out.append((f"sentiment_findings[{i}].interpretation", f.get("interpretation") or ""))
    for i, n in enumerate(report.get("no_alert_decisions", [])):
        out.append((f"no_alert_decisions[{i}].reason", n.get("reason") or ""))
    for i, v in enumerate(report.get("verification_needed", [])):
        out.append((f"verification_needed[{i}]", f"{v.get('item', '')} {v.get('why', '')} {v.get('suggested_check', '')}"))
    if include_open_questions:
        for i, q in enumerate(report.get("open_questions", [])):
            out.append((f"open_questions[{i}]", q))
    return out


def _baseline(ctx: ToolContext, event_id: str) -> dict[str, Any]:
    if event_id in ctx.priority_baselines:
        return ctx.priority_baselines[event_id]
    event, _ = ctx.events[event_id]
    variant = ctx.services.watchlist.variant(event.variant_id) or {}
    result = assess_event(event, comparability=variant.get("comparability"),
                          northstar_product_id=variant.get("northstar_product_id"))
    ctx.priority_baselines[event_id] = result
    return result


def validate_report(ctx: ToolContext, report: dict[str, Any]) -> list[str]:
    """Return a list of problems. An empty list means the report can be saved."""
    problems: list[str] = []
    ledger = ctx.evidence

    def check_ids(where: str, ids: list[str]) -> None:
        unknown = [i for i in ids or [] if i not in ledger]
        if unknown:
            problems.append(f"{where}: cites IDs that no tool returned in this run: {', '.join(unknown)}.")

    if not (report.get("executive_summary") or "").strip():
        problems.append("executive_summary is empty.")

    for i, s in enumerate(report.get("signals", [])):
        where = f"signals[{i}] ({s.get('title', '')[:40]})"
        if s.get("priority") not in PRIORITY_ORDER:
            problems.append(f"{where}: priority must be one of {PRIORITY_ORDER}.")
        check_ids(where, s.get("evidence_ids", []))
        if not s.get("evidence_ids") and not s.get("event_ids"):
            problems.append(f"{where}: every signal needs evidence_ids or event_ids.")
        unknown_events = [e for e in s.get("event_ids", []) if e not in ctx.events]
        if unknown_events:
            problems.append(f"{where}: unknown event_ids {unknown_events}; use IDs from compare_product_snapshots.")
        if "price" in (s.get("change_type") or "") and s.get("priority") in {"high", "medium"} and not s.get("event_ids"):
            problems.append(f"{where}: price signals rated {s.get('priority')} must reference a computed event_id.")
        if s.get("priority") == "high":
            for e in s.get("event_ids", []):
                if e in ctx.events and _baseline(ctx, e)["suggested_priority"] in {"no_alert", "insufficient_evidence"}:
                    problems.append(f"{where}: event {e} is '{_baseline(ctx, e)['suggested_priority']}' and cannot be high.")
        if s.get("priority") in {"high", "medium"}:
            related = [ctx.events[e][1] for e in s.get("event_ids", []) if e in ctx.events]
            if any(not c.comparable for c in related):
                problems.append(f"{where}: references a non-comparable comparison.")

    for i, f in enumerate(report.get("sentiment_findings", [])):
        where = f"sentiment_findings[{i}]"
        analysis = ctx.sentiment.get(f.get("product_id"))
        if analysis is None:
            problems.append(f"{where}: no analyze_review_sentiment result for {f.get('product_id')} in this run.")
            continue
        theme = next((t for t in analysis["themes"] if t["aspect"] == f.get("aspect") and t["sentiment"] == f.get("sentiment")), None)
        if theme is None:
            problems.append(f"{where}: theme {f.get('aspect')}/{f.get('sentiment')} was not found by analyze_review_sentiment.")
            continue
        extra = [r for r in f.get("review_ids", []) if r not in theme["review_ids"]]
        if extra:
            problems.append(f"{where}: review_ids {extra} are not part of the {f.get('aspect')}/{f.get('sentiment')} theme.")

    for i, n in enumerate(report.get("no_alert_decisions", [])):
        check_ids(f"no_alert_decisions[{i}]", n.get("evidence_ids", []))

    for where, text in _texts(report, include_open_questions=True):
        for claim in find_population_claims(text):
            problems.append(
                f"{where}: '{claim}' generalizes a review sample to all customers. Use 'N of the M reviews in our sample'."
            )
    for where, text in _texts(report, include_open_questions=False):
        for claim in find_motive_claims(text):
            problems.append(
                f"{where}: '{claim}' asserts a competitor motive. Move hypotheses to open_questions and label them unconfirmed."
            )
    return problems


def enrich_report(ctx: ToolContext, report: dict[str, Any], run_info: dict[str, Any]) -> dict[str, Any]:
    cited: list[str] = []

    def cite(ids: list[str]) -> None:
        for i in ids:
            if i not in cited:
                cited.append(i)

    signals = []
    for s in report.get("signals", []):
        computed = []
        for e in s.get("event_ids", []):
            if e not in ctx.events:
                continue
            event, comparison = ctx.events[e]
            computed.append(
                {
                    "event_id": e,
                    "change_type": event.change_type,
                    "field": event.field,
                    "old_value": event.old_value,
                    "new_value": event.new_value,
                    "magnitude": event.magnitude,
                    "caveats": event.caveats,
                    "snapshots": [comparison.old_snapshot_id, comparison.new_snapshot_id],
                    "rubric_baseline": _baseline(ctx, e)["suggested_priority"],
                }
            )
            cite([comparison.old_snapshot_id, comparison.new_snapshot_id])
        cite(s.get("evidence_ids", []))
        signals.append({**s, "computed_facts": computed})
    signals.sort(key=lambda s: PRIORITY_ORDER.index(s["priority"]) if s.get("priority") in PRIORITY_ORDER else 9)

    sentiment = []
    for f in report.get("sentiment_findings", []):
        analysis = ctx.sentiment.get(f.get("product_id"))
        theme = next((t for t in (analysis or {}).get("themes", [])
                      if t["aspect"] == f.get("aspect") and t["sentiment"] == f.get("sentiment")), None)
        if not theme:
            continue
        cite(theme["review_ids"])
        sentiment.append(
            {
                **f,
                "review_ids": theme["review_ids"],
                "review_count": theme["review_count"],
                "sample_size": theme["sample_size"],
                "statement": theme["statement"],
                "recurring": theme["recurring"],
                "category": theme["category"],
            }
        )
    samples = {
        pid: {
            **a["sample"],
            "annotation_source": a["annotation_source"],
            "ambiguous_review_ids": a["ambiguous_review_ids"],
            "possible_prompt_injection_review_ids": a["possible_prompt_injection_review_ids"],
        }
        for pid, a in ctx.sentiment.items()
        if any(f["product_id"] == pid for f in sentiment)
    }
    for n in report.get("no_alert_decisions", []):
        cite(n.get("evidence_ids", []))

    sources = []
    for i in cited:
        meta = ctx.evidence.get(i)
        if meta is None:
            continue
        sources.append({"id": i, **{k: v for k, v in meta.items() if k in {"kind", "observed_at", "source_id", "source_url", "reliability"}}})

    return {
        "title": report.get("title") or "Competitive Intelligence Brief",
        "notice": NOTICE,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run": run_info,
        "executive_summary": report.get("executive_summary", ""),
        "signals": signals,
        "sentiment_findings": sentiment,
        "review_samples": samples,
        "no_alert_decisions": report.get("no_alert_decisions", []),
        "verification_needed": report.get("verification_needed", []),
        "open_questions": report.get("open_questions", []),
        "prompt_injection_observations": _dedupe(
            ctx.injection_observations
            + [{"review_id": r, "where": "customer review"} for a in ctx.sentiment.values()
               for r in a["possible_prompt_injection_review_ids"]]
        ),
        "sources": sources,
    }


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out, seen = [], set()
    for item in items:
        key = tuple(sorted(item.items()))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


# --------------------------------------------------------------------------- markdown
def _md(text: Any) -> str:
    return str(text if text is not None else "—").replace("|", "\\|").replace("\n", " ")


def _signal_block(n: int, s: dict[str, Any]) -> list[str]:
    lines = [f"### {n}. {s.get('title', 'Signal')}", ""]
    rows = [
        ("Priority", s.get("priority", "").replace("_", " ").title()),
        ("Competitor", s.get("competitor_id")),
        ("Product", f"{s.get('product_id')}" + (f" (variant {s['variant_id']})" if s.get("variant_id") else "")),
        ("What changed", s.get("what_changed")),
        ("Previous observation", s.get("previous_observation")),
        ("New observation", s.get("new_observation")),
    ]
    seen_caveats: set[str] = set()
    for fact in s.get("computed_facts", []):
        if fact.get("magnitude"):
            m = fact["magnitude"]
            rows.append(("Computed change (Python)",
                         f"{m['old_price']:.2f} → {m['new_price']:.2f}: {m['direction']} of {m['pct_display']} "
                         f"(exact {abs(m['pct_change'])}%, formula {m['formula']})"))
        for c in fact.get("caveats", []):
            if c not in seen_caveats:
                seen_caveats.add(c)
                rows.append(("Data caveat", c))
    rows += [
        ("Why it matters", s.get("why_it_matters")),
        ("Supporting evidence", ", ".join(f"`{i}`" for i in s.get("evidence_ids", []) + s.get("event_ids", []))),
        ("Confidence", (s.get("confidence") or "").title()),
        ("Uncertainty", s.get("uncertainty")),
        ("Why this priority", s.get("priority_rationale")),
        ("Recommended next step", s.get("recommended_next_step")),
    ]
    lines += ["| | |", "|---|---|"] + [f"| **{k}** | {_md(v)} |" for k, v in rows] + [""]
    return lines


def render_markdown(r: dict[str, Any]) -> str:
    run = r["run"]
    out = [
        f"# {r['title']}",
        "",
        f"> **Fictional data.** {r['notice']}",
        "",
        f"- **Generated:** {r['generated_at']}",
        f"- **How this report was produced:** {run.get('producer')}",
        f"- **Scenario:** `{run.get('scenario_id')}` · **Trace ID:** `{run.get('trace_id')}` · **Data mode:** {run.get('data_mode')}",
    ]
    if run.get("tool_calls") is not None:
        out.append(f"- **Tool calls:** {run.get('tool_calls')} · **Model turns:** {run.get('model_turns', 0)}")
    out += ["", "## Executive summary", "", r["executive_summary"], ""]

    groups = {p: [s for s in r["signals"] if s.get("priority") == p] for p in PRIORITY_ORDER}
    out += ["## High-priority signals", ""]
    if groups["high"]:
        for i, s in enumerate(groups["high"], 1):
            out += _signal_block(i, s)
    else:
        out += ["No high-priority signals in this run.", ""]
    if groups["medium"]:
        out += ["## Medium-priority signals", ""]
        for i, s in enumerate(groups["medium"], 1):
            out += _signal_block(i, s)

    out += ["## Customer sentiment", ""]
    if r["sentiment_findings"]:
        for pid, sample in r["review_samples"].items():
            dupes = ", ".join(f"`{d['review_id']}` ({d['kind'].replace('_', ' ')} of `{d['duplicate_of']}`)"
                              for d in sample["duplicates_excluded"]) or "none"
            out += [
                f"**{pid}** — {sample['unique_reviews']} unique reviews analyzed "
                f"({sample['records_received']} records received; duplicates excluded: {dupes}). "
                f"Annotations: {sample['annotation_source']}.",
                "",
                f"_{sample['caveat']}_",
                "",
                "| Theme | Count in sample | Recurring? | Supporting reviews | Interpretation |",
                "|---|---|---|---|---|",
            ]
            for f in [f for f in r["sentiment_findings"] if f["product_id"] == pid]:
                out.append(
                    f"| {_md(f['statement'])} | {f['review_count']} of {f['sample_size']} | "
                    f"{'Yes' if f['recurring'] else 'No (isolated)'} | {', '.join(f'`{x}`' for x in f['review_ids'])} | "
                    f"{_md(f.get('interpretation'))} |"
                )
            extra = []
            if sample["ambiguous_review_ids"]:
                extra.append(f"Ambiguous reviews not counted toward specific themes: {', '.join(sample['ambiguous_review_ids'])}.")
            if sample["possible_prompt_injection_review_ids"]:
                extra.append("Reviews containing instructions aimed at AI tools (ignored as instructions): "
                             f"{', '.join(sample['possible_prompt_injection_review_ids'])}.")
            out += [""] + [f"- {e}" for e in extra] + ([""] if extra else [])
    else:
        out += ["No customer sentiment findings in this run.", ""]

    out += ["## Lower-priority observations", ""]
    lows = groups["low"]
    if not lows and not r["no_alert_decisions"]:
        out += ["None recorded.", ""]
    for s in lows:
        out.append(f"- **{_md(s.get('title'))}** ({s.get('competitor_id')}, {s.get('product_id')}): "
                   f"{_md(s.get('what_changed'))} _Why low:_ {_md(s.get('priority_rationale'))} "
                   f"Evidence: {', '.join(f'`{i}`' for i in s.get('evidence_ids', []))}")
    for n in r["no_alert_decisions"]:
        out.append(f"- **No alert — {_md(n.get('subject'))}:** {_md(n.get('reason'))} "
                   f"Evidence: {', '.join(f'`{i}`' for i in n.get('evidence_ids', []))}")
    out.append("")

    out += ["## Information requiring verification", ""]
    for s in groups["insufficient_evidence"]:
        out.append(f"- **{_md(s.get('title'))}:** {_md(s.get('what_changed'))} {_md(s.get('uncertainty'))} "
                   f"Next step: {_md(s.get('recommended_next_step'))}")
    for v in r["verification_needed"]:
        out.append(f"- **{_md(v.get('item'))}** — {_md(v.get('why'))} _Suggested check:_ {_md(v.get('suggested_check'))}")
    if not groups["insufficient_evidence"] and not r["verification_needed"]:
        out.append("- Nothing flagged.")
    if r["open_questions"]:
        out += ["", "**Open questions (unconfirmed hypotheses — do not treat as findings):**", ""]
        out += [f"- {_md(q)}" for q in r["open_questions"]]
    out.append("")

    if r["prompt_injection_observations"]:
        out += ["## Untrusted-content warnings", "",
                "These sources contained text addressed to AI tools. It was treated as data and not followed.", ""]
        out += [f"- `{o.get('snapshot_id') or o.get('review_id')}` — {o['where']}" for o in r["prompt_injection_observations"]]
        out.append("")

    out += ["## Sources", "", "| ID | Type | Observed / published | Source |", "|---|---|---|---|"]
    for s in r["sources"]:
        out.append(f"| `{s['id']}` | {s.get('kind', '')} | {s.get('observed_at', '—')} | "
                   f"{_md(s.get('source_url') or s.get('source_id') or '—')} |")
    out += ["", "---", "", "_The agent recommends; humans decide. No prices, product pages, or external messages were "
            "changed or sent by this run._", ""]
    return "\n".join(out)
