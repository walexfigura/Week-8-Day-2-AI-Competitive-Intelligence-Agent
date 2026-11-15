"""Fixture integrity: snapshots are valid, consistent, and match their HTML pages."""

from __future__ import annotations

import json

import pytest

from competitive_intelligence.integrations.page_parser import parse_product_page
from competitive_intelligence.models import ProductSnapshot
from competitive_intelligence.storage import SnapshotStore, StorageError, safe_child

from .conftest import ROOT

SNAPSHOT_FILES = sorted((ROOT / "data" / "historical-snapshots").glob("*/*.json"))


def test_every_watched_product_has_at_least_two_snapshots(services):
    for _, prod in services.watchlist.products():
        assert len(services.snapshots.list(prod["product_id"])) >= 2, prod["product_id"]


@pytest.mark.parametrize("path", SNAPSHOT_FILES, ids=lambda p: p.stem)
def test_snapshot_validates_and_is_labeled_fictional(path):
    snap = ProductSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert snap.fictional is True
    assert ".example" in snap.source_url
    assert snap.snapshot_id == path.stem
    assert path.parent.name == snap.product_id.lower()


@pytest.mark.parametrize("path", [p for p in SNAPSHOT_FILES if json.loads(p.read_text())["fixture"]], ids=lambda p: p.stem)
def test_html_fixture_parses_to_the_same_facts(path):
    snap = ProductSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))
    html = (ROOT / snap.fixture).read_text(encoding="utf-8")
    page = parse_product_page(html, snap.variant_id)
    assert page["fixture_meta"]["snapshot-id"] == snap.snapshot_id
    assert page["fixture_meta"]["observed-at"] == snap.observed_at
    for name in ("current_price", "list_price", "currency", "availability", "features", "headline", "marketing_copy", "hidden_text"):
        assert page[name] == getattr(snap, name), name
    assert page["promotion"] == (snap.promotion.model_dump() if snap.promotion else None)


def test_timestamps_are_in_order_and_before_reference_date(services, settings):
    for _, prod in services.watchlist.products():
        snaps = services.snapshots.list(prod["product_id"])
        times = [s.observed_at for s in snaps]
        assert all(t[:10] <= settings.reference_date for t in times)


def test_incomplete_snapshot_reports_missing_fields(services):
    snap = services.snapshots.get("SW-DAILY", "sw-daily-2026-11-12")
    assert not snap.is_complete
    assert {"current_price", "currency", "availability", "features"} <= set(snap.missing_fields())


def test_store_rejects_path_traversal(services):
    with pytest.raises(StorageError):
        services.snapshots.get("PT-RIDGE", "../../etc/passwd")
    with pytest.raises(StorageError):
        safe_child(ROOT, "..", "outside")


def test_store_saves_new_capture_to_state_dir(tmp_path, services):
    store = SnapshotStore(ROOT / "data" / "historical-snapshots", tmp_path / "state")
    snap = services.snapshots.get("PT-RIDGE", "pt-ridge-2026-11-01").model_copy(update={"snapshot_id": "pt-ridge-2026-11-20",
                                                                                      "observed_at": "2026-11-20T15:00:00Z"})
    path = store.save(snap)
    assert path.is_relative_to(tmp_path)
    assert [s.snapshot_id for s in store.list("PT-RIDGE")][-1] == "pt-ridge-2026-11-20"
    with pytest.raises(StorageError):
        store.save(snap)  # never overwrite


def test_invalid_currency_is_rejected():
    raw = json.loads(SNAPSHOT_FILES[0].read_text())
    raw["currency"] = "usd"
    with pytest.raises(ValueError):
        ProductSnapshot.model_validate(raw)
