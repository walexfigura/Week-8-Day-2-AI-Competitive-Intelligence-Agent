"""Transparent, rule-based priority baseline for change events.

This is a *triage heuristic* built from knowledge-base/competitive-priorities.md.
It is not a measurement of business impact. The agent sees every factor and
reason, may argue for a different tier, and must explain its final choice.
The application only enforces one hard rule: events whose baseline is
`no_alert` or `insufficient_evidence` cannot be reported as `high`.
"""

from __future__ import annotations

from typing import Any

from ..models import ChangeEvent, ComparisonResult

DIFFERENTIATOR_KEYWORDS = ("leak", "insulat", "warranty", "cold for", "hot for")
LEVEL_POINTS = {"high": 3, "medium": 2, "low": 1, "none": 0, "unknown": 1}
DISCLAIMER = (
    "Heuristic triage based on documented criteria (competitive-priorities.md). "
    "It is not a measured business impact; a human should review the reasoning."
)


def _factor(level: str, reason: str) -> dict[str, str]:
    return {"level": level, "reason": reason}


def assess_event(
    event: ChangeEvent,
    *,
    comparability: str | None,
    northstar_product_id: str | None,
    related_review_count: int | None = None,
    related_sample_size: int | None = None,
) -> dict[str, Any]:
    """Score one change event. `comparability` comes from the watchlist (direct/partial/none)."""
    ct = event.change_type
    factors: dict[str, dict[str, str]] = {}

    # business relevance
    if comparability == "direct":
        factors["business_relevance"] = _factor("high", f"Directly comparable to {northstar_product_id}.")
    elif comparability == "partial":
        factors["business_relevance"] = _factor("medium", f"Partially comparable to {northstar_product_id}.")
    else:
        factors["business_relevance"] = _factor("low", "No directly comparable Northstar product.")

    # magnitude
    pct = abs((event.magnitude or {}).get("pct_change") or 0)
    if ct in {"price_decrease", "price_increase"}:
        level = "high" if pct >= 10 else "medium" if pct >= 5 else "low"
        factors["magnitude"] = _factor(level, f"Price changed by {event.magnitude['pct_display']} (computed in Python).")
    elif ct == "promotion_started":
        factors["magnitude"] = _factor("medium" if pct >= 10 else "low", "Labeled promotion; temporary by definition.")
    elif ct == "promotion_ended":
        factors["magnitude"] = _factor("none", "Price returned to its previously shown regular price.")
    elif ct in {"feature_added", "feature_removed"}:
        text = str(event.new_value or event.old_value or "").lower()
        targets = any(k in text for k in DIFFERENTIATOR_KEYWORDS)
        factors["magnitude"] = _factor(
            "high" if targets else "low",
            "Feature relates to a Northstar differentiator (leak resistance/insulation/warranty)."
            if targets
            else "Feature does not relate to a documented Northstar differentiator.",
        )
    elif ct == "availability_change":
        factors["magnitude"] = _factor("medium", f"Availability changed from {event.old_value} to {event.new_value}.")
    elif ct == "messaging_change":
        factors["magnitude"] = _factor(
            "medium",
            "Headline or marketing copy changed. The rubric cannot judge whether it targets Northstar's "
            "customer segments; the analyst must interpret the old and new text.",
        )
    else:
        factors["magnitude"] = _factor("low", f"{ct} is usually a minor change.")

    # evidence quality
    if event.caveats and any("cannot show" in c or "Two observations" in c for c in event.caveats):
        factors["evidence_quality"] = _factor("medium", "Two comparable observations, but permanence or duration is unknown.")
    else:
        factors["evidence_quality"] = _factor("high", "Two complete, comparable observations of the same variant.")

    # customer impact
    if related_review_count is not None and related_sample_size:
        level = "high" if related_review_count >= 5 else "medium" if related_review_count >= 3 else "low"
        factors["customer_impact"] = _factor(
            level, f"{related_review_count} of the {related_sample_size} reviews in our sample relate to this signal."
        )
    else:
        factors["customer_impact"] = _factor("unknown", "No related review evidence supplied.")

    # urgency
    if ct in {"price_decrease", "price_increase"} and comparability == "direct" and pct >= 10:
        factors["urgency"] = _factor("high", "A large price gap on a direct comparable can affect sales quickly.")
    elif ct in {"feature_added", "availability_change", "messaging_change", "promotion_started"}:
        factors["urgency"] = _factor("medium", "Worth investigating within weeks, not days.")
    else:
        factors["urgency"] = _factor("low", "No time pressure identified.")

    # confidence in the observation itself
    if ct == "messaging_change":
        factors["confidence"] = _factor("medium", "The text change is certain; its meaning is interpretation.")
    else:
        factors["confidence"] = _factor("high", "Direct field comparison of structured snapshots.")

    # tier
    rel = factors["business_relevance"]["level"]
    mag = factors["magnitude"]["level"]
    if ct == "promotion_ended":
        tier = "no_alert"
    elif mag == "high" and rel == "high":
        tier = "high"
    elif mag == "high" or (mag == "medium" and rel in {"high", "medium"}) or (rel == "high" and mag != "none"):
        tier = "medium"
    else:
        tier = "low"
    score = sum(LEVEL_POINTS[f["level"]] for f in factors.values())
    return {
        "event_id": event.event_id,
        "change_type": ct,
        "suggested_priority": tier,
        "factors": factors,
        "rubric_points": f"{score} of {3 * len(factors)}",
        "disclaimer": DISCLAIMER,
    }


def assess_comparison(comparison: ComparisonResult) -> dict[str, Any] | None:
    """Baseline for a comparison that produced no events."""
    if comparison.status in {"not_comparable", "incomplete_data"}:
        return {
            "suggested_priority": "insufficient_evidence",
            "reason": " ".join(comparison.comparability_issues) or "Snapshots cannot be compared safely.",
            "disclaimer": DISCLAIMER,
        }
    if not comparison.events:
        return {
            "suggested_priority": "no_alert",
            "reason": "Formatting-only change: normalized product facts are unchanged."
            if comparison.formatting_only
            else "No meaningful change detected.",
            "disclaimer": DISCLAIMER,
        }
    return None
