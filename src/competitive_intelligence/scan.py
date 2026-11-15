"""Monitoring scan: compare stored snapshots for every watched product (no LLM).

This is the deterministic half of monitoring — the part you would schedule.
It runs the same tools the agent uses (so the evidence ledger and logs are
identical), compares consecutive snapshots per storefront, attaches the rubric
baseline, and flags findings already recorded in `state/findings.jsonl`.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .logging_utils import new_trace_id
from .services import Services
from .tools import registry
from .tools.base import ToolContext


def run_scan(services: Services, *, ctx: ToolContext | None = None, capture_live: bool = False) -> dict[str, Any]:
    ctx = ctx or ToolContext(services=services, trace_id=new_trace_id(), scenario_id="scan")
    log = services.logger.log
    log(ctx.trace_id, "scan_started", data_mode=services.settings.data_mode)
    seen = services.findings.seen()
    registry.execute("list_watchlist", {}, ctx)

    comparisons: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    single_observations: list[dict[str, Any]] = []
    captured: list[str] = []
    for comp, prod in services.watchlist.products():
        pid = prod["product_id"]
        if capture_live and services.settings.data_mode == "live":
            from .integrations.public_web import observation_to_snapshot

            for var in prod["tracked_variants"]:
                try:
                    obs = services.pages.fetch(comp["competitor_id"], pid, var["variant_id"])
                    path = services.snapshots.save(observation_to_snapshot(obs, prod["name"]))
                except Exception as exc:  # noqa: BLE001 - one failing page must not stop the scan
                    errors.append({"product_id": pid, "step": "live_capture",
                                   "error": {"code": type(exc).__name__, "message": str(exc)}})
                    continue
                captured.append(str(path))
        listing = registry.execute("list_product_snapshots", {"product_id": pid}, ctx)
        if listing["status"] != "ok":
            errors.append({"product_id": pid, "step": "list_product_snapshots", "error": listing["error"]})
            continue
        by_storefront: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in listing["data"]["snapshots"]:
            by_storefront[row["storefront"]].append(row)
        for storefront, rows in by_storefront.items():
            if len(rows) < 2:
                single_observations.append(
                    {"product_id": pid, "storefront": storefront, "snapshot_id": rows[0]["snapshot_id"],
                     "currency": rows[0]["currency"],
                     "note": f"Only one observation for the {storefront} storefront; nothing to compare it with in the same currency."}
                )
                continue
            for old, new in zip(rows, rows[1:], strict=False):
                res = registry.execute("compare_product_snapshots", {"product_id": pid, "old_snapshot_id": old["snapshot_id"],
                                                                     "new_snapshot_id": new["snapshot_id"]}, ctx)
                if res["status"] != "ok":
                    errors.append({"product_id": pid, "step": "compare", "pair": [old["snapshot_id"], new["snapshot_id"]],
                                   "error": res["error"]})
                    continue
                data = res["data"]
                events = []
                for ev in data["events"]:
                    baseline = registry.execute("assess_signal_priority", {"event_id": ev["event_id"]}, ctx)["data"]
                    fp = services.findings.fingerprint(pid, ev["change_type"], ev["field"], ev["old_value"], ev["new_value"])
                    events.append({**ev, "baseline": baseline, "fingerprint": fp, "previously_recorded": fp in seen})
                comparisons.append(
                    {
                        "competitor_id": comp["competitor_id"],
                        "product_id": pid,
                        "storefront": storefront,
                        "old_snapshot_id": old["snapshot_id"],
                        "new_snapshot_id": new["snapshot_id"],
                        "status": data["status"],
                        "formatting_only": data["formatting_only"],
                        "comparability_issues": data["comparability_issues"],
                        "notes": data["notes"],
                        "unchanged_fields": data["unchanged_fields"],
                        "events": events,
                    }
                )
    counts: dict[str, int] = defaultdict(int)
    for c in comparisons:
        if c["status"] in {"not_comparable", "incomplete_data"}:
            counts["insufficient_evidence"] += 1
        elif not c["events"]:
            counts["no_alert"] += 1
        for e in c["events"]:
            counts[e["baseline"]["suggested_priority"]] += 1
    log(ctx.trace_id, "scan_finished", comparisons=len(comparisons), errors=len(errors), counts=dict(counts))
    return {
        "trace_id": ctx.trace_id,
        "data_mode": services.settings.data_mode,
        "comparisons": comparisons,
        "single_observations": single_observations,
        "errors": errors,
        "captured_snapshots": captured,
        "event_counts_by_baseline": dict(counts),
        "note": "Baseline priorities come from a transparent rubric, not an LLM. Run `python run.py briefing` for an agent investigation.",
    }


def record_findings(services: Services, scan: dict[str, Any]) -> int:
    """Store fingerprints of high/medium events so the next scan marks them as already seen."""
    count = 0
    for c in scan["comparisons"]:
        for e in c["events"]:
            if e["baseline"]["suggested_priority"] in {"high", "medium"} and not e["previously_recorded"]:
                services.findings.record(e["fingerprint"], f"{c['product_id']} {e['change_type']} {e['field']}", scan["trace_id"])
                count += 1
    return count
