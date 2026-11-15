"""Deterministic change detection and price arithmetic."""

from __future__ import annotations

import pytest

from competitive_intelligence.analysis.change_detection import compare_snapshots, normalize_features, price_change


def snap(services, pid, sid):
    return services.snapshots.get(pid, sid)


def test_peaktrail_price_drop_is_17_9_percent():
    pc = price_change(39, 32)
    assert pc["pct_change"] == -17.95
    assert pc["pct_display"] == "17.9%"
    assert pc["abs_change"] == -7.0
    assert pc["direction"] == "decrease"


@pytest.mark.parametrize("old,new,display", [(28, 22, "21.4%"), (22, 28, "27.3%"), (100, 95, "5.0%"), (10, 10, "0.0%")])
def test_rounding_is_consistent(old, new, display):
    assert price_change(old, new)["pct_display"] == display


def test_zero_old_price_is_rejected():
    with pytest.raises(ValueError):
        price_change(0, 10)


def test_comparable_price_drop_event(services):
    res = compare_snapshots(snap(services, "PT-RIDGE", "pt-ridge-2026-10-01"), snap(services, "PT-RIDGE", "pt-ridge-2026-11-01"))
    assert res.status == "changes_detected" and res.comparable
    [event] = res.events
    assert event.change_type == "price_decrease"
    assert (event.old_value, event.new_value) == (39.0, 32.0)
    assert any("temporary or permanent" in c for c in event.caveats)
    assert {e.snapshot_id for e in event.evidence} == {"pt-ridge-2026-10-01", "pt-ridge-2026-11-01"}
    assert {"availability", "features", "headline"} <= set(res.unchanged_fields)


def test_different_variants_are_not_comparable(services):
    res = compare_snapshots(snap(services, "PT-RIDGE", "pt-ridge-2026-11-01"), snap(services, "PT-RIDGE", "pt-ridge-2026-11-12"))
    assert res.status == "not_comparable"
    assert res.events == []
    assert "Different variants" in res.comparability_issues[0]


def test_different_currency_and_storefront_are_not_comparable(services):
    res = compare_snapshots(snap(services, "PT-RIDGE", "pt-ridge-2026-11-01"), snap(services, "PT-RIDGE", "pt-ridge-ca-2026-11-05"))
    issues = " ".join(res.comparability_issues)
    assert res.status == "not_comparable"
    assert "currencies" in issues and "storefronts" in issues


def test_reversed_order_is_not_comparable(services):
    res = compare_snapshots(snap(services, "PT-RIDGE", "pt-ridge-2026-11-01"), snap(services, "PT-RIDGE", "pt-ridge-2026-10-01"))
    assert res.status == "not_comparable"


def test_expired_promotion_is_not_a_price_increase(services):
    res = compare_snapshots(snap(services, "SW-DAILY", "sw-daily-2026-10-01"), snap(services, "SW-DAILY", "sw-daily-2026-11-01"))
    assert [e.change_type for e in res.events] == ["promotion_ended"]
    assert "not a new price increase" in res.events[0].caveats[0]


def test_promotion_started_is_labeled_temporary(services):
    old = snap(services, "SW-DAILY", "sw-daily-2026-11-01")
    new = snap(services, "SW-DAILY", "sw-daily-2026-10-01").model_copy(update={"observed_at": "2026-11-20T15:00:00Z", "snapshot_id": "x-2026-11-20"})
    res = compare_snapshots(old, new)
    assert res.events[0].change_type == "promotion_started"
    assert any("temporary" in c for c in res.events[0].caveats)


def test_missing_price_is_incomplete_not_a_change(services):
    res = compare_snapshots(snap(services, "SW-DAILY", "sw-daily-2026-11-01"), snap(services, "SW-DAILY", "sw-daily-2026-11-12"))
    assert res.status == "incomplete_data" and res.events == []


def test_feature_and_messaging_changes(services):
    res = compare_snapshots(snap(services, "SW-METRO", "sw-metro-2026-10-01"), snap(services, "SW-METRO", "sw-metro-2026-11-01"))
    types = sorted((e.change_type, e.field) for e in res.events)
    assert ("feature_added", "features") in types and ("feature_removed", "features") in types
    assert ("messaging_change", "headline") in types
    added = next(e for e in res.events if e.change_type == "feature_added")
    assert added.new_value == "LockSeal leak-proof lid"
    assert "current_price" in res.unchanged_fields


def test_availability_change(services):
    res = compare_snapshots(snap(services, "TF-CANTEEN", "tf-canteen-2026-10-01"), snap(services, "TF-CANTEEN", "tf-canteen-2026-11-01"))
    [event] = res.events
    assert event.change_type == "availability_change" and event.new_value == "out_of_stock"


def test_formatting_only_change(services):
    res = compare_snapshots(snap(services, "TF-APEX", "tf-apex-2026-11-01"), snap(services, "TF-APEX", "tf-apex-2026-11-12"))
    assert res.status == "no_meaningful_change"
    assert res.formatting_only is True
    assert res.events == []


def test_feature_normalization_ignores_case_spacing_and_order():
    a = normalize_features(["Keeps drinks cold for 48 hours", "Lifetime warranty"])
    b = normalize_features(["lifetime  warranty ", "keeps drinks cold for 48 hours."])
    assert set(a) == set(b)


def test_event_ids_are_stable(services):
    o, n = snap(services, "PT-RIDGE", "pt-ridge-2026-10-01"), snap(services, "PT-RIDGE", "pt-ridge-2026-11-01")
    assert compare_snapshots(o, n).events[0].event_id == compare_snapshots(o, n).events[0].event_id
