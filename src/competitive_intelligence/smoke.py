"""Offline smoke test: verifies the project is wired correctly. No API key needed."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .analysis.change_detection import compare_snapshots
from .config import Settings
from .integrations.page_parser import parse_product_page
from .logging_utils import TraceLogger, new_trace_id
from .services import Services
from .storage import safe_child
from .tools import registry
from .tools.base import ToolContext


def run_smoke(settings: Settings) -> list[tuple[str, bool, str]]:
    settings = Settings(**{**settings.__dict__, "sentiment_source": "reference"})
    results: list[tuple[str, bool, str]] = []

    def step(name: str, fn: Callable[[], str]) -> None:
        try:
            results.append((name, True, fn()))
        except Exception as exc:  # noqa: BLE001
            results.append((name, False, f"{type(exc).__name__}: {exc}"))

    svc = Services(settings, logger=TraceLogger(None))
    ctx = ToolContext(services=svc, trace_id=new_trace_id(), scenario_id="smoke")

    def datasets() -> str:
        counts: dict[str, Any] = {"competitors": len(svc.watchlist.competitors), "northstar_products": len(svc.our_products)}
        for pid in ("PT-RIDGE", "SW-METRO", "TF-APEX"):
            meta, reviews = svc.fixture_reviews.get(pid)
            assert reviews, f"no reviews for {pid}"
            counts[f"reviews:{pid}"] = len(reviews)
        news = json.loads((settings.data_dir / "news" / "announcements.json").read_text(encoding="utf-8"))
        counts["news_items"] = len(news["items"])
        scen = json.loads((settings.data_dir / "scenarios" / "scenarios.json").read_text(encoding="utf-8"))
        counts["scenarios"] = len(scen["scenarios"])
        return ", ".join(f"{k}={v}" for k, v in counts.items())

    def snapshots() -> str:
        total, parsed = 0, 0
        for _, prod in svc.watchlist.products():
            snaps = svc.snapshots.list(prod["product_id"])
            assert len(snaps) >= 2, f"{prod['product_id']} needs at least two snapshots"
            total += len(snaps)
            for s in snaps:
                if s.fixture:
                    html = safe_child(settings.root, *s.fixture.split("/")).read_text(encoding="utf-8")
                    page = parse_product_page(html, s.variant_id)
                    if s.is_complete:
                        assert page["current_price"] == s.current_price, f"{s.snapshot_id}: HTML and JSON prices differ"
                    parsed += 1
        return f"{total} snapshots valid; {parsed} HTML fixtures parsed and match their JSON records"

    def prices() -> str:
        old = svc.snapshots.get("PT-RIDGE", "pt-ridge-2026-10-01")
        new = svc.snapshots.get("PT-RIDGE", "pt-ridge-2026-11-01")
        ev = compare_snapshots(old, new).events[0]
        assert ev.magnitude["pct_display"] == "17.9%", ev.magnitude
        return f"PT-RIDGE-32 {ev.old_value} → {ev.new_value} USD = {ev.change_type} of {ev.magnitude['pct_display']}"

    def reviews() -> str:
        res = registry.execute("get_customer_reviews", {"product_id": "PT-RIDGE"}, ctx)
        assert res["status"] == "ok", res
        sent = registry.execute("analyze_review_sentiment", {"product_id": "PT-RIDGE"}, ctx)
        assert sent["status"] == "ok", sent
        lid = next(t for t in sent["data"]["themes"] if t["aspect"] == "lid_leak_resistance" and t["sentiment"] == "negative")
        return f"{res['data']['sample']['records_received']} records retrieved; reference annotations: {lid['statement']}"

    def tools() -> str:
        schemas = registry.openai_tools()
        names = [s["name"] for s in schemas]
        assert len(names) == len(set(names))
        for s in schemas:
            assert s["parameters"]["additionalProperties"] is False
        probe = registry.execute("list_watchlist", {}, ctx)
        bad = registry.execute("no_such_tool", {}, ctx)
        blocked = registry.execute("send_email", {}, ctx)
        assert probe["status"] == "ok" and bad["status"] == "error" and blocked.get("blocked")
        return f"{len(names)} tools registered; unknown and restricted tools are refused"

    def knowledge() -> str:
        docs = sorted(svc.knowledge.docs)
        assert {"competitive-priorities", "evidence-standards", "workflow:change-detection"} <= set(docs)
        return f"{len(docs)} business documents available to the agent"

    step("Mock datasets load", datasets)
    step("Historical snapshots are valid", snapshots)
    step("Prices can be compared", prices)
    step("Review data can be retrieved", reviews)
    step("Tool registry works", tools)
    step("Knowledge base is readable", knowledge)
    step("OpenAI key configured (optional)", lambda: "yes" if settings.has_openai_key else
         "not set — offline commands work; `demo`, `briefing`, and agent evals need it")
    return results
