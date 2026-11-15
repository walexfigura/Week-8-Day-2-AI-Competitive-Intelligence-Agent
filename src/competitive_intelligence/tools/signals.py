"""Signal prioritization tool: a transparent rubric baseline the model can reason about."""

from __future__ import annotations

from typing import Any

from ..analysis.prioritization import assess_event
from .base import ToolContext, invalid, not_found, ok


def assess_signal_priority(
    ctx: ToolContext,
    event_id: str,
    related_review_count: int | None = None,
    related_sample_size: int | None = None,
) -> dict[str, Any]:
    found = ctx.events.get(event_id)
    if found is None:
        return not_found("unknown_event", f"No event '{event_id}' in this run. Call compare_product_snapshots first.")
    if (related_review_count is None) != (related_sample_size is None):
        return invalid("Provide both related_review_count and related_sample_size, or neither.")
    if related_sample_size is not None and (related_sample_size <= 0 or related_review_count < 0
                                            or related_review_count > related_sample_size):
        return invalid("related_review_count must be between 0 and related_sample_size (> 0).")
    event, _ = found
    variant = ctx.services.watchlist.variant(event.variant_id) or {}
    result = assess_event(
        event,
        comparability=variant.get("comparability"),
        northstar_product_id=variant.get("northstar_product_id"),
        related_review_count=related_review_count,
        related_sample_size=related_sample_size,
    )
    ctx.priority_baselines[event_id] = result
    return ok(result)
