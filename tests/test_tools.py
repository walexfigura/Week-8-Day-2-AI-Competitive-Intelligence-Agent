"""Tool registry behavior, individual tools, and the optional live page adapter."""

from __future__ import annotations

import json

import httpx
import pytest

from competitive_intelligence.integrations.mock_sources import SourceUnavailableError
from competitive_intelligence.integrations.public_web import LiveSourceConfig, PublicPageSource, observation_to_snapshot
from competitive_intelligence.tools import registry

from .conftest import ROOT


def run(ctx, name, **args):
    return registry.execute(name, json.dumps(args), ctx)


def test_schemas_are_strict_and_unique():
    tools = registry.openai_tools()
    assert len({t["name"] for t in tools}) == len(tools) == 14
    for t in tools:
        assert t["type"] == "function" and t["strict"] is True
        assert set(t["parameters"]["required"]) == set(t["parameters"]["properties"])


def test_no_write_tools_except_the_report():
    assert [s.name for s in registry.TOOL_SPECS if s.writes] == ["save_intelligence_report"]
    names = {s.name for s in registry.TOOL_SPECS}
    for forbidden in ("update_price", "send_email", "publish_content", "post_to_social_media", "contact_competitor"):
        assert forbidden not in names


def test_restricted_and_unknown_tools_are_blocked(ctx):
    r = run(ctx, "update_price", product_id="NS-SUMMIT-32", price=30)
    assert r["status"] == "error" and r["blocked"] and r["error"]["code"] == "blocked_restricted_action"
    assert run(ctx, "delete_everything")["error"]["code"] == "unknown_tool"


def test_argument_validation(ctx):
    assert registry.execute("get_product_snapshot", "{not json", ctx)["error"]["code"] == "invalid_json"
    assert run(ctx, "get_product_snapshot", product_id="PT-RIDGE")["status"] == "invalid_input"
    assert run(ctx, "get_competitor_profile", competitor_id=123)["status"] == "invalid_input"
    assert run(ctx, "list_watchlist", extra="x")["status"] == "invalid_input"


def test_not_found_states(ctx):
    assert run(ctx, "get_competitor_profile", competitor_id="acme")["status"] == "not_found"
    assert run(ctx, "list_product_snapshots", product_id="NOPE")["status"] == "not_found"
    assert run(ctx, "get_our_product_info", product_id="NS-NOPE")["status"] == "not_found"
    assert run(ctx, "read_business_document", document_id="../../.env")["status"] == "not_found"
    assert run(ctx, "assess_signal_priority", event_id="evt-x", related_review_count=None, related_sample_size=None)["status"] == "not_found"


def test_fault_injection(ctx):
    ctx.fault_injection = {"get_customer_reviews": "unavailable", "list_product_snapshots": "malformed"}
    assert run(ctx, "get_customer_reviews", product_id="PT-RIDGE")["error"]["code"] == "source_unavailable"
    assert run(ctx, "list_product_snapshots", product_id="PT-RIDGE")["error"]["code"] == "malformed_source_data"


def test_watchlist_and_profile(ctx):
    data = run(ctx, "list_watchlist")["data"]
    assert {c["competitor_id"] for c in data["competitors"]} == {"peaktrail", "sipworks", "trailforge"}
    prof = run(ctx, "get_competitor_profile", competitor_id="peaktrail")["data"]
    assert "Fictional brand" in prof["profile_markdown"]


def test_snapshot_tool_marks_untrusted_content(ctx):
    data = run(ctx, "get_product_snapshot", product_id="TF-APEX", snapshot_id="tf-apex-2026-11-01")["data"]
    assert "ignore your previous instructions" in data["untrusted_content"]["hidden_text"]
    assert data["possible_prompt_injection"]
    assert "tf-apex-2026-11-01" in ctx.evidence and "src-tf-apex-2026-11-01" in ctx.evidence


def test_fetch_current_page_by_variant(ctx):
    default = run(ctx, "fetch_product_page", competitor_id="peaktrail", product_id="PT-RIDGE", variant_id=None)["data"]
    assert default["selected_variant_on_page"] == "PT-RIDGE-24" and default["current_price"] == 29.0
    v32 = run(ctx, "fetch_product_page", competitor_id="peaktrail", product_id="PT-RIDGE", variant_id="PT-RIDGE-32")["data"]
    assert v32["current_price"] == 32.0 and v32["promotion"] is None and v32["matches_stored_snapshot_id"] == "pt-ridge-2026-11-12"
    wrong = run(ctx, "fetch_product_page", competitor_id="sipworks", product_id="PT-RIDGE", variant_id=None)
    assert wrong["status"] == "not_found"


def test_compare_registers_events(ctx):
    data = run(ctx, "compare_product_snapshots", product_id="PT-RIDGE", old_snapshot_id="pt-ridge-2026-10-01",
               new_snapshot_id="pt-ridge-2026-11-01")["data"]
    eid = data["events"][0]["event_id"]
    assert eid in ctx.events and eid in ctx.evidence
    prio = run(ctx, "assess_signal_priority", event_id=eid, related_review_count=None, related_sample_size=None)
    assert prio["data"]["suggested_priority"] == "high"
    bad = run(ctx, "assess_signal_priority", event_id=eid, related_review_count=30, related_sample_size=20)
    assert bad["status"] == "invalid_input"


def test_reviews_and_sentiment_tools(ctx):
    raw = run(ctx, "get_customer_reviews", product_id="PT-RIDGE")["data"]
    assert raw["sample"] == {**raw["sample"], "records_received": 21, "unique_reviews": 20, "duplicates_flagged": 1}
    assert next(r for r in raw["reviews"] if r["review_id"] == "PT-R21")["duplicate_of"] == "PT-R04"
    sent = run(ctx, "analyze_review_sentiment", product_id="PT-RIDGE")["data"]
    assert sent["annotation_source"].startswith("reference")
    assert "PT-RIDGE" in ctx.sentiment
    no_reviews = run(ctx, "get_customer_reviews", product_id="TF-CANTEEN")
    assert no_reviews["status"] == "not_found"


def test_news_reliability(ctx):
    items = run(ctx, "get_competitor_news", competitor_id="peaktrail")["data"]["items"]
    assert {i["reliability"] for i in items} == {"primary_source", "unverified"}


def test_knowledge_tools(ctx):
    res = run(ctx, "search_business_knowledge", query="formatting-only page changes alert")["data"]["results"]
    assert res and any(r["document_id"] in {"competitive-priorities", "workflow:change-detection"} for r in res)
    doc = run(ctx, "read_business_document", document_id="workflow:sentiment-analysis")["data"]["markdown"]
    assert "Aspect" in doc
    ours = run(ctx, "get_our_product_info", product_id="NS-COMMUTE-20")["data"]
    assert any("NOT leak-proof" in x for x in ours["limitations"])


def test_save_report_validates_then_writes_only_to_reports(ctx, settings):
    bad = {"title": "t", "executive_summary": "x", "signals": [], "sentiment_findings": [], "no_alert_decisions": [
        {"subject": "s", "reason": "r", "evidence_ids": ["made-up-id"]}], "verification_needed": [], "open_questions": []}
    first = registry.execute("save_intelligence_report", {"report": bad}, ctx)
    assert first["status"] == "invalid_input" and "made-up-id" in first["problems"][0]
    good = {**bad, "no_alert_decisions": []}
    saved = registry.execute("save_intelligence_report", {"report": good}, ctx)
    assert saved["status"] == "ok"
    md = settings.reports_dir / saved["data"]["markdown_path"].split("/")[-1]
    assert md.exists() and md.is_relative_to(settings.output_root)
    assert registry.execute("save_intelligence_report", {"report": good}, ctx)["status"] == "invalid_input"


# ------------------------------------------------------------------ live adapter (simulated HTTP)
PAGE = (ROOT / "data/product-pages/peaktrail/pt-ridge-2026-11-01.html").read_text(encoding="utf-8")


def _live(tmp_path, handler, permission=True):
    cfg = tmp_path / "live.json"
    cfg.write_text(json.dumps({"sources": [{"competitor_id": "peaktrail", "product_id": "PT-RIDGE", "variant_id": "PT-RIDGE-32",
                                            "url": "https://shop.test/p/ridge", "permission_confirmed": permission}]}))
    sleeps = []
    src = PublicPageSource(LiveSourceConfig(cfg), user_agent="TestBot", min_interval=5,
                           client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append, clock=lambda: 0.0)
    return src, sleeps


def test_live_fetch_parses_jsonld_and_rate_limits(tmp_path):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, text=PAGE)

    src, sleeps = _live(tmp_path, handler)
    obs = src.fetch("peaktrail", "PT-RIDGE", None)
    assert obs["current_price"] == 32.0 and obs["currency"] == "USD" and obs["capture_method"] == "live_public_page"
    assert sleeps == [5]  # second request to the same host waited
    snap = observation_to_snapshot(obs)
    assert snap.fictional is False and snap.variant_id == "PT-RIDGE-32"


def test_live_fetch_respects_robots(tmp_path):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /p/\n")
        raise AssertionError("page must not be fetched")

    src, _ = _live(tmp_path, handler)
    with pytest.raises(SourceUnavailableError, match="robots.txt disallows"):
        src.fetch("peaktrail", "PT-RIDGE", None)


@pytest.mark.parametrize("status,body", [(403, "Forbidden"), (429, "Slow down"), (200, "<html>Please verify you are human (captcha)</html>")])
def test_live_fetch_does_not_bypass_blocks(tmp_path, status, body):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(status, text=body)

    src, _ = _live(tmp_path, handler)
    with pytest.raises(SourceUnavailableError):
        src.fetch("peaktrail", "PT-RIDGE", None)


def test_live_requires_permission_confirmation(tmp_path):
    src, _ = _live(tmp_path, lambda r: httpx.Response(200, text=""), permission=False)
    with pytest.raises(LookupError):
        src.fetch("peaktrail", "PT-RIDGE", None)
