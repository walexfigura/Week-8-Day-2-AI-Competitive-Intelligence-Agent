"""The rule-based priority baseline and report validation rules."""

from __future__ import annotations

from competitive_intelligence.analysis.change_detection import compare_snapshots
from competitive_intelligence.analysis.prioritization import DISCLAIMER, assess_comparison, assess_event
from competitive_intelligence.reports import validate_report
from competitive_intelligence.tools import registry


def events(services, pid, a, b):
    return compare_snapshots(services.snapshots.get(pid, a), services.snapshots.get(pid, b))


def test_direct_large_price_drop_is_high(services):
    ev = events(services, "PT-RIDGE", "pt-ridge-2026-10-01", "pt-ridge-2026-11-01").events[0]
    r = assess_event(ev, comparability="direct", northstar_product_id="NS-SUMMIT-32")
    assert r["suggested_priority"] == "high"
    assert r["disclaimer"] == DISCLAIMER
    assert set(r["factors"]) == {"business_relevance", "magnitude", "evidence_quality", "customer_impact", "urgency", "confidence"}


def test_same_drop_on_unrelated_product_is_not_high(services):
    ev = events(services, "PT-RIDGE", "pt-ridge-2026-10-01", "pt-ridge-2026-11-01").events[0]
    assert assess_event(ev, comparability="none", northstar_product_id=None)["suggested_priority"] == "medium"


def test_leak_feature_on_direct_comparable_is_high(services):
    res = events(services, "SW-METRO", "sw-metro-2026-10-01", "sw-metro-2026-11-01")
    added = next(e for e in res.events if e.change_type == "feature_added")
    assert assess_event(added, comparability="direct", northstar_product_id="NS-COMMUTE-20")["suggested_priority"] == "high"


def test_messaging_change_without_comparable_is_low_but_explained(services):
    ev = events(services, "TF-APEX", "tf-apex-2026-10-01", "tf-apex-2026-11-01").events[0]
    r = assess_event(ev, comparability="none", northstar_product_id=None)
    assert r["suggested_priority"] == "low"
    assert "interpret" in r["factors"]["magnitude"]["reason"]


def test_customer_impact_uses_sample_language(services):
    ev = events(services, "PT-RIDGE", "pt-ridge-2026-10-01", "pt-ridge-2026-11-01").events[0]
    r = assess_event(ev, comparability="direct", northstar_product_id="NS-SUMMIT-32", related_review_count=8, related_sample_size=20)
    assert r["factors"]["customer_impact"]["reason"] == "8 of the 20 reviews in our sample relate to this signal."


def test_no_alert_and_insufficient_evidence(services):
    assert assess_comparison(events(services, "TF-APEX", "tf-apex-2026-11-01", "tf-apex-2026-11-12"))["suggested_priority"] == "no_alert"
    assert assess_comparison(events(services, "PT-RIDGE", "pt-ridge-2026-11-01", "pt-ridge-2026-11-12"))["suggested_priority"] == "insufficient_evidence"


def _report(**kw):
    base = {"title": "t", "executive_summary": "Summary.", "signals": [], "sentiment_findings": [], "no_alert_decisions": [],
            "verification_needed": [], "open_questions": []}
    return {**base, **kw}


def _signal(**kw):
    base = {"title": "s", "priority": "high", "competitor_id": "peaktrail", "product_id": "PT-RIDGE", "variant_id": "PT-RIDGE-32",
            "change_type": "price_decrease", "event_ids": [], "what_changed": "x", "previous_observation": "x",
            "new_observation": "x", "why_it_matters": "x", "evidence_ids": [], "confidence": "high", "uncertainty": "x",
            "priority_rationale": "x", "recommended_next_step": "x"}
    return {**base, **kw}


def test_high_priority_rejected_for_no_alert_event(ctx):
    res = registry.execute("compare_product_snapshots", {"product_id": "SW-DAILY", "old_snapshot_id": "sw-daily-2026-10-01",
                                                         "new_snapshot_id": "sw-daily-2026-11-01"}, ctx)
    eid = res["data"]["events"][0]["event_id"]
    problems = validate_report(ctx, _report(signals=[_signal(product_id="SW-DAILY", change_type="promotion_ended", event_ids=[eid],
                                                             evidence_ids=["sw-daily-2026-11-01"])]))
    assert any("cannot be high" in p for p in problems)


def test_price_signal_needs_computed_event(ctx):
    registry.execute("list_product_snapshots", {"product_id": "PT-RIDGE"}, ctx)
    problems = validate_report(ctx, _report(signals=[_signal(evidence_ids=["pt-ridge-2026-11-01"])]))
    assert any("computed event_id" in p for p in problems)


def test_valid_signal_passes(ctx):
    res = registry.execute("compare_product_snapshots", {"product_id": "PT-RIDGE", "old_snapshot_id": "pt-ridge-2026-10-01",
                                                         "new_snapshot_id": "pt-ridge-2026-11-01"}, ctx)
    eid = res["data"]["events"][0]["event_id"]
    assert validate_report(ctx, _report(signals=[_signal(event_ids=[eid], evidence_ids=["pt-ridge-2026-10-01", "src-pt-ridge-2026-11-01"])])) == []


def test_sentiment_finding_review_ids_must_belong_to_theme(ctx):
    registry.execute("analyze_review_sentiment", {"product_id": "PT-RIDGE"}, ctx)
    finding = {"product_id": "PT-RIDGE", "aspect": "lid_leak_resistance", "sentiment": "negative", "interpretation": "x",
               "review_ids": ["PT-R01", "PT-R02"]}
    problems = validate_report(ctx, _report(sentiment_findings=[finding]))
    assert any("PT-R02" in p for p in problems)


def test_population_and_motive_language_rejected(ctx):
    problems = validate_report(ctx, _report(executive_summary="Most customers hate the lid. PeakTrail cut its price to clear inventory."))
    assert any("generalizes" in p for p in problems)
    assert any("motive" in p for p in problems)
