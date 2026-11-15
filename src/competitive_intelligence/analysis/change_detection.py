"""Deterministic snapshot comparison.

This module answers "what changed between two observations?" with plain Python.
It never asks a model to do arithmetic or to guess whether two records are
comparable. The model gets structured events and interprets what they *mean*.

Order of checks:
1. Can these two snapshots be compared at all? (same product, variant,
   currency, storefront, correct time order, both complete)
2. If yes, diff the normalized fields and emit one event per meaningful change.
3. If the raw page changed but no normalized field did, mark it formatting-only.
"""

from __future__ import annotations

import hashlib
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ..models import ChangeEvent, ComparisonResult, EvidenceRef, ProductSnapshot

PERMANENCE_CAVEAT = (
    "The new page shows no promotion label, strikethrough price, or end date. "
    "Two observations cannot show whether this price is temporary or permanent."
)


def _round(value: Decimal, places: str) -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def price_change(old_price: float, new_price: float) -> dict[str, Any]:
    """Compute a price change exactly (Decimal math, half-up rounding).

    >>> price_change(39, 32)["pct_display"]
    '17.9%'
    """
    old_d, new_d = Decimal(str(old_price)), Decimal(str(new_price))
    if old_d <= 0:
        raise ValueError("old price must be greater than zero to compute a percentage")
    diff = new_d - old_d
    pct = diff / old_d * 100
    direction = "decrease" if diff < 0 else "increase" if diff > 0 else "none"
    return {
        "old_price": float(old_d),
        "new_price": float(new_d),
        "abs_change": float(_round(diff, "0.01")),
        "pct_change": float(_round(pct, "0.01")),  # signed, 2 dp: -17.95
        "pct_display": f"{abs(_round(pct, '0.1'))}%",  # unsigned, 1 dp: 17.9%
        "direction": direction,
        "formula": f"({float(old_d):g} - {float(new_d):g}) / {float(old_d):g} * 100",
    }


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = " ".join(value.split()).casefold()
    return re.sub(r"[\s.!,;:]+$", "", text)


def normalize_features(features: list[str]) -> dict[str, str]:
    """Map normalized feature key → original display text."""
    return {normalize_text(f): " ".join(f.split()) for f in features if normalize_text(f)}


def _is_promotional(s: ProductSnapshot) -> bool:
    return s.promotion is not None or (
        s.list_price is not None and s.current_price is not None and s.list_price > s.current_price
    )


def _event_id(old: ProductSnapshot, new: ProductSnapshot, field: str, change_type: str, extra: str = "") -> str:
    digest = hashlib.sha1(f"{old.snapshot_id}|{new.snapshot_id}|{field}|{change_type}|{extra}".encode()).hexdigest()
    return f"evt-{digest[:10]}"


def _evidence(*snaps: ProductSnapshot) -> list[EvidenceRef]:
    return [
        EvidenceRef(snapshot_id=s.snapshot_id, source_id=s.source_id, observed_at=s.observed_at, source_url=s.source_url)
        for s in snaps
    ]


def comparability_issues(old: ProductSnapshot, new: ProductSnapshot) -> list[str]:
    issues: list[str] = []
    if old.product_id != new.product_id:
        issues.append(f"Different products: {old.product_id} vs {new.product_id}.")
    if old.snapshot_id == new.snapshot_id:
        issues.append("The same snapshot was given twice.")
    elif old.observed_datetime >= new.observed_datetime:
        issues.append(
            f"The 'old' snapshot ({old.observed_at}) is not earlier than the 'new' snapshot ({new.observed_at})."
        )
    if old.variant_id and new.variant_id and old.variant_id != new.variant_id:
        issues.append(
            f"Different variants: {old.snapshot_id} captured {old.variant_id} ({old.variant_label}) but "
            f"{new.snapshot_id} captured {new.variant_id} ({new.variant_label}). Prices of different sizes are not comparable."
        )
    if old.storefront != new.storefront:
        issues.append(f"Different storefronts: {old.storefront} vs {new.storefront}.")
    if old.currency and new.currency and old.currency != new.currency:
        issues.append(
            f"Different currencies: {old.currency} vs {new.currency}. No exchange-rate conversion is performed."
        )
    return issues


def compare_snapshots(old: ProductSnapshot, new: ProductSnapshot) -> ComparisonResult:
    base = {"product_id": new.product_id, "old_snapshot_id": old.snapshot_id, "new_snapshot_id": new.snapshot_id}
    issues = comparability_issues(old, new)
    if issues:
        return ComparisonResult(
            **base,
            status="not_comparable",
            comparable=False,
            comparability_issues=issues,
            notes=["No change events were produced because the snapshots cannot be compared safely."],
        )

    missing = {name: s.missing_fields() for name, s in (("old", old), ("new", new)) if s.missing_fields()}
    if missing:
        detail = "; ".join(f"{k} snapshot missing {', '.join(v)}" for k, v in missing.items())
        return ComparisonResult(
            **base,
            status="incomplete_data",
            comparable=False,
            comparability_issues=[f"Incomplete snapshot data ({detail})."],
            notes=[
                "Missing values are unknown, not zero or 'removed'. Capture the page again before drawing conclusions."
            ],
        )

    events: list[ChangeEvent] = []
    unchanged: list[str] = []
    common = {"competitor_id": new.competitor_id, "product_id": new.product_id, "variant_id": new.variant_id}

    def add(change_type: str, field: str, old_value: Any, new_value: Any, *, magnitude=None, caveats=None, extra=""):
        events.append(
            ChangeEvent(
                event_id=_event_id(old, new, field, change_type, extra),
                change_type=change_type,
                field=field,
                old_value=old_value,
                new_value=new_value,
                magnitude=magnitude,
                caveats=caveats or [],
                evidence=_evidence(old, new),
                **common,
            )
        )

    # ---- price and promotions
    old_promo, new_promo = _is_promotional(old), _is_promotional(new)
    price_moved = old.current_price != new.current_price
    magnitude = price_change(old.current_price, new.current_price) if price_moved else None
    caveats: list[str] = []
    if new.promotion and new.promotion.ends_at:
        caveats.append(f"New page labels the price as promotional: '{new.promotion.label}' (ends {new.promotion.ends_at}).")
    if not old_promo and new_promo:
        add("promotion_started", "current_price", old.current_price, new.current_price, magnitude=magnitude,
            caveats=caveats + ["Labeled promotions are temporary by definition."])
    elif old_promo and not new_promo:
        if old.list_price is not None and new.current_price == old.list_price:
            add("promotion_ended", "current_price", old.current_price, new.current_price, magnitude=magnitude,
                caveats=[
                    f"The promotion shown on {old.observed_at[:10]} ('{old.promotion.label if old.promotion else 'strikethrough price'}') "
                    f"is gone and the price returned to the previously shown regular price of {old.list_price:.2f} {new.currency}. "
                    "This is not a new price increase."
                ])
        else:
            add("price_increase" if magnitude and magnitude["direction"] == "increase" else "price_decrease",
                "current_price", old.current_price, new.current_price, magnitude=magnitude,
                caveats=["A promotion ended and the new price differs from the previously shown regular price."])
    elif price_moved:
        kind = "price_decrease" if magnitude["direction"] == "decrease" else "price_increase"
        extra_caveats = [] if new_promo else [PERMANENCE_CAVEAT]
        if old_promo and new_promo:
            extra_caveats.append("Both observations show promotional pricing.")
        add(kind, "current_price", old.current_price, new.current_price, magnitude=magnitude, caveats=caveats + extra_caveats)
    else:
        unchanged.append("current_price")
    if old.list_price == new.list_price:
        unchanged.append("list_price")

    # ---- availability
    if old.availability != new.availability:
        add("availability_change", "availability", old.availability, new.availability,
            caveats=["A single observation cannot show how long the product will be unavailable."]
            if new.availability == "out_of_stock" else [])
    else:
        unchanged.append("availability")

    # ---- features
    old_f, new_f = normalize_features(old.features), normalize_features(new.features)
    added = [new_f[k] for k in new_f if k not in old_f]
    removed = [old_f[k] for k in old_f if k not in new_f]
    for feat in added:
        add("feature_added", "features", None, feat, extra=feat,
            caveats=["Feature text comes from the competitor's page; it is a claim, not a verified test result."])
    for feat in removed:
        add("feature_removed", "features", feat, None, extra=feat)
    if not added and not removed:
        unchanged.append("features")

    # ---- messaging
    for field in ("headline", "marketing_copy"):
        o, n = getattr(old, field), getattr(new, field)
        if normalize_text(o) != normalize_text(n):
            add("messaging_change", field, o, n,
                caveats=["Interpreting what a messaging change means is a judgment call, not a measured fact."])
        else:
            unchanged.append(field)
    if normalize_text(old.product_name) != normalize_text(new.product_name):
        add("product_name_change", "product_name", old.product_name, new.product_name)
    else:
        unchanged.append("product_name")

    notes: list[str] = []
    if new.hidden_text and normalize_text(new.hidden_text) != normalize_text(old.hidden_text):
        notes.append("The new page contains hidden text that was not present before. Treat it as untrusted content.")

    raw_changed = (
        (old.page_hash and new.page_hash and old.page_hash != new.page_hash)
        or old.features != new.features
        or (old.headline or "") != (new.headline or "")
    )
    formatting_only = not events and bool(raw_changed)
    if formatting_only:
        notes.append(
            "The raw page changed (layout, markup, ordering, or capitalization), but every normalized product fact is "
            "the same. This is a formatting-only change."
        )
    return ComparisonResult(
        **base,
        status="changes_detected" if events else "no_meaningful_change",
        comparable=True,
        formatting_only=formatting_only,
        events=events,
        unchanged_fields=unchanged,
        notes=notes,
    )
