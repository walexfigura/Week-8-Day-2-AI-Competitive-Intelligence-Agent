"""Product-page tools: snapshots, current page fetch, and deterministic comparison."""

from __future__ import annotations

from typing import Any

from ..analysis.change_detection import compare_snapshots
from ..guardrails import detect_injection
from ..integrations.mock_sources import MalformedSourceError, SourceUnavailableError
from ..models import ProductSnapshot
from ..storage import SnapshotValidationError, StorageError
from .base import ToolContext, fail, invalid, not_found, ok


def _injection_flags(*texts: Any) -> list[str]:
    hits: list[str] = []
    for t in texts:
        if isinstance(t, list):
            t = " ".join(str(x) for x in t)
        hits.extend(detect_injection(t))
    return sorted(set(hits))


def snapshot_view(snap: ProductSnapshot) -> dict[str, Any]:
    """What the model sees for one snapshot. Page-authored text is marked untrusted."""
    return {
        "snapshot_id": snap.snapshot_id,
        "source_id": snap.source_id,
        "competitor_id": snap.competitor_id,
        "product_id": snap.product_id,
        "product_name": snap.product_name,
        "variant_id": snap.variant_id,
        "variant_label": snap.variant_label,
        "size_oz": snap.size_oz,
        "storefront": snap.storefront,
        "observed_at": snap.observed_at,
        "current_price": snap.current_price,
        "list_price": snap.list_price,
        "currency": snap.currency,
        "promotion": snap.promotion.model_dump() if snap.promotion else None,
        "availability": snap.availability,
        "complete": snap.is_complete,
        "missing_fields": snap.missing_fields(),
        "source_url": snap.source_url,
        "capture_method": snap.capture_method,
        "collector_notes": snap.notes,
        "untrusted_content": {
            "headline": snap.headline,
            "marketing_copy": snap.marketing_copy,
            "features": snap.features,
            "hidden_text": snap.hidden_text,
        },
        "possible_prompt_injection": _injection_flags(snap.hidden_text, snap.marketing_copy, snap.headline, snap.features),
    }


def _remember_snapshot(ctx: ToolContext, snap: ProductSnapshot) -> None:
    meta = dict(source_id=snap.source_id, observed_at=snap.observed_at, source_url=snap.source_url,
                product_id=snap.product_id, competitor_id=snap.competitor_id)
    ctx.remember(snap.snapshot_id, "snapshot", **meta)
    ctx.remember(snap.source_id, "source", snapshot_id=snap.snapshot_id, observed_at=snap.observed_at,
                 source_url=snap.source_url)
    if snap.hidden_text and detect_injection(snap.hidden_text):
        ctx.injection_observations.append({"snapshot_id": snap.snapshot_id, "where": "hidden page text"})


def _check_product(ctx: ToolContext, product_id: str) -> dict[str, Any] | None:
    if ctx.services.watchlist.product(product_id) is None:
        known = ", ".join(p["product_id"] for _, p in ctx.services.watchlist.products())
        return not_found("unknown_product", f"'{product_id}' is not on the watchlist. Watched products: {known}.")
    return None


def list_product_snapshots(ctx: ToolContext, product_id: str) -> dict[str, Any]:
    if err := _check_product(ctx, product_id):
        return err
    try:
        snaps = ctx.services.snapshots.list(product_id)
    except (SnapshotValidationError, StorageError) as exc:
        return fail("error", "malformed_source_data", str(exc))
    rows = []
    for s in snaps:
        _remember_snapshot(ctx, s)
        rows.append(
            {
                "snapshot_id": s.snapshot_id,
                "observed_at": s.observed_at,
                "variant_id": s.variant_id,
                "storefront": s.storefront,
                "currency": s.currency,
                "current_price": s.current_price,
                "complete": s.is_complete,
                "capture_method": s.capture_method,
            }
        )
    return ok({"product_id": product_id, "snapshot_count": len(rows), "snapshots": rows,
               "tip": "Compare consecutive snapshots of the same variant and storefront."})


def get_product_snapshot(ctx: ToolContext, product_id: str, snapshot_id: str) -> dict[str, Any]:
    if err := _check_product(ctx, product_id):
        return err
    try:
        snap = ctx.services.snapshots.get(product_id, snapshot_id)
    except StorageError as exc:
        return invalid(str(exc))
    if snap is None:
        return not_found("unknown_snapshot", f"No snapshot '{snapshot_id}' for {product_id}. Use list_product_snapshots.")
    _remember_snapshot(ctx, snap)
    return ok(snapshot_view(snap))


def fetch_product_page(ctx: ToolContext, competitor_id: str, product_id: str, variant_id: str | None = None) -> dict[str, Any]:
    if err := _check_product(ctx, product_id):
        return err
    try:
        obs = ctx.services.pages.fetch(competitor_id, product_id, variant_id)
    except LookupError as exc:
        return not_found("unknown_page", str(exc))
    except SourceUnavailableError as exc:
        return fail("error", "source_unavailable", str(exc))
    except (MalformedSourceError, SnapshotValidationError) as exc:
        return fail("error", "malformed_source_data", str(exc))
    ctx.remember(obs["source_id"], "source", observed_at=obs["observed_at"], source_url=obs["source_url"],
                 snapshot_id=obs.get("page_snapshot_id"))
    if obs.get("page_snapshot_id"):
        ctx.remember(obs["page_snapshot_id"], "snapshot", source_id=obs["source_id"], observed_at=obs["observed_at"],
                     source_url=obs["source_url"], product_id=product_id, competitor_id=competitor_id)
    flags = _injection_flags(obs.get("hidden_text"), obs.get("marketing_copy"), obs.get("headline"), obs.get("features"))
    return ok(
        {
            "competitor_id": competitor_id,
            "product_id": product_id,
            "requested_variant_id": variant_id,
            "variant_id": obs.get("variant_id"),
            "selected_variant_on_page": obs.get("selected_variant_on_page"),
            "observed_at": obs["observed_at"],
            "source_id": obs["source_id"],
            "source_url": obs["source_url"],
            "capture_method": obs["capture_method"],
            "matches_stored_snapshot_id": obs.get("page_snapshot_id"),
            "current_price": obs.get("current_price"),
            "list_price": obs.get("list_price"),
            "currency": obs.get("currency"),
            "promotion": obs.get("promotion"),
            "availability": obs.get("availability"),
            "all_offers_on_page": obs.get("offers"),
            "parse_warnings": obs.get("parse_warnings"),
            "untrusted_content": {
                "headline": obs.get("headline"),
                "marketing_copy": obs.get("marketing_copy"),
                "features": obs.get("features"),
                "hidden_text": obs.get("hidden_text"),
            },
            "possible_prompt_injection": flags,
        }
    )


def compare_product_snapshots(ctx: ToolContext, product_id: str, old_snapshot_id: str, new_snapshot_id: str) -> dict[str, Any]:
    if err := _check_product(ctx, product_id):
        return err
    try:
        old = ctx.services.snapshots.get(product_id, old_snapshot_id)
        new = ctx.services.snapshots.get(product_id, new_snapshot_id)
    except SnapshotValidationError as exc:
        return fail("error", "malformed_source_data", str(exc))
    except StorageError as exc:
        return invalid(str(exc))
    missing = [sid for sid, s in ((old_snapshot_id, old), (new_snapshot_id, new)) if s is None]
    if missing:
        return not_found("unknown_snapshot", f"Snapshot(s) not found for {product_id}: {', '.join(missing)}.")
    _remember_snapshot(ctx, old)
    _remember_snapshot(ctx, new)
    result = compare_snapshots(old, new)
    ctx.comparisons[f"{old.snapshot_id}->{new.snapshot_id}"] = result
    for event in result.events:
        ctx.events[event.event_id] = (event, result)
        ctx.remember(event.event_id, "event", product_id=product_id, change_type=event.change_type,
                     snapshot_ids=[old.snapshot_id, new.snapshot_id])
    data = result.model_dump()
    for event in data["events"]:
        if event["change_type"] in {"messaging_change", "feature_added", "feature_removed"}:
            event["values_are_untrusted_page_text"] = True
    return ok(data)
