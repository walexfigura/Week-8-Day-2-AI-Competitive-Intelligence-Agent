"""Offline briefing: a rule-based report built without any LLM.

Why have this? It lets you see the complete report format, the evidence
handling, and the validation rules without an API key — and it is a useful
baseline to compare against the agent. It is clearly labeled as rule-based:
priorities are the rubric's suggestions, and all wording comes from templates.
It does *not* interpret meaning the way the LLM agent does (for example, it
cannot tell that TrailForge's new headline targets commuters).
"""

from __future__ import annotations

from typing import Any

from .logging_utils import new_trace_id
from .scan import run_scan
from .services import Services
from .tools import registry
from .tools.base import ToolContext

RANK = {"high": 0, "medium": 1, "low": 2, "insufficient_evidence": 3, "no_alert": 4}
NEXT_STEP = {
    "price_decrease": "Head of Ecommerce: review {ns} pricing against this listing. Before acting, capture at least two more "
    "observations of the same variant to see whether the price holds or a promotion label appears.",
    "price_increase": "Record the new price and re-check next week before drawing conclusions.",
    "feature_added": "Product team: investigate the new competing feature and how it compares with {ns}'s documented limitations.",
    "availability_change": "Re-check availability next week; if it stays unavailable, Marketing may review whether {ns} "
    "messaging reaches customers searching for this product.",
    "messaging_change": "Marketing Lead: read the old and new copy and decide whether it targets Northstar's customer segments.",
}


def _money(value: Any, currency: str | None) -> str:
    return f"${value:.2f} {currency}" if isinstance(value, (int, float)) else "unknown"


def build_offline_report(services: Services, *, scenario_id: str = "offline_briefing") -> tuple[dict[str, Any], ToolContext]:
    ctx = ToolContext(services=services, trace_id=new_trace_id(), scenario_id=scenario_id)
    ctx.run_info = {
        "producer": "Deterministic offline briefing (no LLM). Rule-based templates over the same tools; priorities are "
        "the rubric baseline without analyst judgment; review aspects use hand-labeled reference annotations.",
        "model": None,
        "trace_id": ctx.trace_id,
        "scenario_id": scenario_id,
        "data_mode": "mock (fictional fixtures)" if services.settings.data_mode == "mock" else services.settings.data_mode,
    }
    for doc in ("competitive-priorities", "evidence-standards"):
        registry.execute("read_business_document", {"document_id": doc}, ctx)
    scan = run_scan(services, ctx=ctx)
    news: dict[str, list[dict[str, Any]]] = {}
    for cid in services.watchlist.competitors:
        res = registry.execute("get_competitor_news", {"competitor_id": cid}, ctx)
        news[cid] = res["data"]["items"] if res["status"] == "ok" else []

    signals, no_alert, verify, questions = [], [], [], []
    for c in scan["comparisons"]:
        pid, cid = c["product_id"], c["competitor_id"]
        pair = [c["old_snapshot_id"], c["new_snapshot_id"]]
        if c["status"] in {"not_comparable", "incomplete_data"}:
            verify.append(
                {
                    "item": f"{pid}: {pair[0]} → {pair[1]} could not be compared",
                    "why": " ".join(c["comparability_issues"]),
                    "suggested_check": "Capture the tracked variant again on the same storefront and compare like with like.",
                }
            )
            continue
        if not c["events"]:
            reason = (
                "Formatting-only change: the page layout and markup changed, but price, availability, features, and messaging are the same after normalization."
                if c["formatting_only"]
                else "No meaningful change detected."
            )
            no_alert.append({"subject": f"{pid} page change ({pair[0]} → {pair[1]})", "reason": reason, "evidence_ids": pair})
            continue
        ended = [e for e in c["events"] if e["baseline"]["suggested_priority"] == "no_alert"]
        for e in ended:
            no_alert.append({"subject": f"{pid} price {e['old_value']} → {e['new_value']}", "reason": " ".join(e["caveats"]),
                             "evidence_ids": pair})
        events = [e for e in c["events"] if e["baseline"]["suggested_priority"] != "no_alert"]
        if not events:
            continue
        events.sort(key=lambda e: RANK[e["baseline"]["suggested_priority"]])
        top = events[0]
        variant = services.watchlist.variant(top["variant_id"]) or {}
        ns_id = variant.get("northstar_product_id")
        ns = services.our_products.get(ns_id) if ns_id else None
        ns_label = f"{ns['name']} ({_money(ns['price'], ns['currency'])})" if ns else "no directly comparable Northstar product"
        old_snap = services.snapshots.get(pid, pair[0])
        new_snap = services.snapshots.get(pid, pair[1])
        change_list = "; ".join(
            f"{e['change_type'].replace('_', ' ')} ({e['field']}"
            + (f": {e['old_value']!s:.60} → {e['new_value']!s:.60}" if e["change_type"] in {"messaging_change"} else "")
            + (f": '{e['new_value'] or e['old_value']}'" if e["change_type"].startswith("feature") else "")
            + ")"
            for e in events
        )
        mag = top.get("magnitude") or {}
        what = change_list
        if mag:
            what = f"Listed price {mag['direction']} of {mag['pct_display']} ({_money(mag['old_price'], new_snap.currency)} → {_money(mag['new_price'], new_snap.currency)}). " + change_list
        factors = top["baseline"]["factors"]
        signals.append(
            {
                "title": f"{old_snap.product_name} ({old_snap.variant_label}): "
                + ", ".join(sorted({e['change_type'].replace('_', ' ') for e in events})),
                "priority": top["baseline"]["suggested_priority"],
                "competitor_id": cid,
                "product_id": pid,
                "variant_id": top["variant_id"],
                "change_type": top["change_type"],
                "event_ids": [e["event_id"] for e in events],
                "what_changed": what,
                "previous_observation": f"{_money(old_snap.current_price, old_snap.currency)}, {old_snap.availability}, "
                f"headline '{old_snap.headline}' on {old_snap.observed_at} ({old_snap.snapshot_id}).",
                "new_observation": f"{_money(new_snap.current_price, new_snap.currency)}, {new_snap.availability}, "
                f"headline '{new_snap.headline}' on {new_snap.observed_at} ({new_snap.snapshot_id}).",
                "why_it_matters": f"Watchlist mapping: {variant.get('comparability', 'unknown')} comparable to {ns_label}. "
                + factors["business_relevance"]["reason"] + " " + factors["magnitude"]["reason"],
                "evidence_ids": pair + [old_snap.source_id, new_snap.source_id],
                "confidence": "high" if factors["evidence_quality"]["level"] == "high" and factors["confidence"]["level"] == "high" else "medium",
                "uncertainty": " ".join(dict.fromkeys(c for e in events for c in e["caveats"])) or "None noted beyond the two observations.",
                "priority_rationale": "Rubric baseline (no analyst judgment applied): "
                + "; ".join(f"{k.replace('_', ' ')} {v['level']}" for k, v in factors.items()) + ".",
                "recommended_next_step": NEXT_STEP.get(top["change_type"], "Record and re-check on the next scan.").format(
                    ns=ns["name"] if ns else "our closest product"),
            }
        )
        if top["change_type"] == "price_decrease":
            rumors = [n for n in news.get(cid, []) if n["reliability"] == "unverified"]
            questions.append(
                f"Why the {old_snap.product_name} price changed is unknown; nothing on the page explains it."
                + (f" An unverified source ({', '.join(n['news_id'] for n in rumors)}) offers an explanation that no other source corroborates."
                   if rumors else "")
            )
    for single in scan["single_observations"]:
        verify.append({"item": f"{single['product_id']} {single['storefront']} storefront ({single['snapshot_id']}, {single['currency']})",
                       "why": single["note"], "suggested_check": "Do not convert currencies to compare; track this storefront separately if it matters."})
    for err in scan["errors"]:
        verify.append({"item": f"{err['product_id']}: {err['step']} failed", "why": err["error"]["message"],
                       "suggested_check": "Fix or re-collect the source data, then re-run the scan."})

    findings = []
    for comp in services.watchlist.competitors.values():
        for prod in comp["products"]:
            if not prod.get("review_dataset"):
                continue
            pid = prod["product_id"]
            res = registry.execute("analyze_review_sentiment", {"product_id": pid}, ctx)
            if res["status"] != "ok":
                verify.append({"item": f"{pid} reviews", "why": res["error"]["message"], "suggested_check": "Re-collect the review sample."})
                continue
            ns_ids = {v["northstar_product_id"] for v in prod["tracked_variants"] if v.get("northstar_product_id")}
            leak_verified = [
                f"{services.our_products[n]['name']} ({vf['evidence']})"
                for n in ns_ids for vf in services.our_products[n]["verified_features"] if "leak" in vf["feature"].lower()
            ]
            for theme in res["data"]["themes"]:
                if not theme["recurring"]:
                    continue
                interp = f"Recurring {theme['category'].replace('_', ' ')} theme in this sample."
                if theme["aspect"] == "lid_leak_resistance" and theme["sentiment"] == "negative" and leak_verified:
                    interp += (" Relates to a verified Northstar feature: " + "; ".join(leak_verified)
                               + ". Check whether our product page communicates it; do not make comparative claims without testing the competitor product.")
                if theme["aspect"] == "lid_leak_resistance" and theme["sentiment"] == "positive" and not leak_verified:
                    interp += " Customers praise a lid capability our comparable product does not have (see its documented limitations)."
                findings.append({"product_id": pid, "aspect": theme["aspect"], "sentiment": theme["sentiment"],
                                 "interpretation": interp, "review_ids": theme["review_ids"]})

    signals.sort(key=lambda s: RANK[s["priority"]])
    top_signal = signals[0] if signals else None
    leak = next((f for f in findings if f["aspect"] == "lid_leak_resistance" and f["sentiment"] == "negative"), None)
    leak_stmt = next((t["statement"] for t in ctx.sentiment.get(leak["product_id"], {}).get("themes", [])
                      if leak and t["aspect"] == "lid_leak_resistance" and t["sentiment"] == "negative"), None) if leak else None
    summary = []
    if top_signal:
        summary.append(f"Top signal ({top_signal['priority']}): {top_signal['title']} — {top_signal['what_changed'].split('. ')[0]}.")
    counts = {p: sum(1 for s in signals if s["priority"] == p) for p in ("high", "medium", "low")}
    summary.append(f"Signals by rubric baseline: {counts['high']} high, {counts['medium']} medium, {counts['low']} low.")
    if leak_stmt:
        summary.append(f"Customer sentiment: {leak_stmt}")
    summary.append(f"{len(no_alert)} changes did not warrant an alert, and {len(verify)} items need verification.")
    summary.append("This is a rule-based offline briefing; run the LLM agent for interpretation of messaging and context.")
    report = {
        "title": "Northstar Supply Competitive Intelligence Brief (offline, rule-based)",
        "executive_summary": " ".join(summary),
        "signals": signals,
        "sentiment_findings": findings,
        "no_alert_decisions": no_alert,
        "verification_needed": verify,
        "open_questions": questions,
    }
    return report, ctx


def run_offline_briefing(services: Services, *, scenario_id: str = "offline_briefing") -> tuple[dict[str, Any], ToolContext]:
    report, ctx = build_offline_report(services, scenario_id=scenario_id)
    result = registry.execute("save_intelligence_report", {"report": report}, ctx)
    return result, ctx
