#!/usr/bin/env python3
"""Deterministic helpers for the competitive-intelligence Skill (standard library only).

    python scripts/ci_calc.py price-change 39 32
    python scripts/ci_calc.py compare sample-data/product-snapshots.json OLD_ID NEW_ID
    python scripts/ci_calc.py duplicates sample-data/peaktrail-ridge-reviews.json

Outputs JSON so the numbers can be quoted exactly.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal


def price_change(old: float, new: float) -> dict:
    o, n = Decimal(str(old)), Decimal(str(new))
    if o <= 0:
        raise SystemExit("old price must be > 0")
    pct = (n - o) / o * 100
    return {
        "old_price": float(o),
        "new_price": float(n),
        "abs_change": float((n - o).quantize(Decimal("0.01"), ROUND_HALF_UP)),
        "pct_change": float(pct.quantize(Decimal("0.01"), ROUND_HALF_UP)),
        "pct_display": f"{abs(pct.quantize(Decimal('0.1'), ROUND_HALF_UP))}%",
        "direction": "decrease" if n < o else "increase" if n > o else "none",
    }


def _norm(text: str | None) -> str:
    return re.sub(r"[\s.!,;:]+$", "", " ".join((text or "").split()).casefold())


def compare(path: str, old_id: str, new_id: str) -> dict:
    snaps = {s["snapshot_id"]: s for s in json.load(open(path, encoding="utf-8"))["snapshots"]}
    missing = [i for i in (old_id, new_id) if i not in snaps]
    if missing:
        return {"status": "not_found", "missing": missing}
    old, new = snaps[old_id], snaps[new_id]
    issues = []
    for field in ("product_id", "variant_id", "storefront", "currency"):
        if old.get(field) and new.get(field) and old[field] != new[field]:
            issues.append(f"different {field}: {old[field]} vs {new[field]}")
    if old["observed_at"] >= new["observed_at"]:
        issues.append("old observation is not earlier than new observation")
    if issues:
        return {"status": "not_comparable", "issues": issues}
    gaps = [f for f in ("current_price", "currency", "availability") if old.get(f) is None or new.get(f) is None]
    if gaps:
        return {"status": "incomplete_data", "missing_fields": gaps}
    changes = []
    old_promo = bool(old.get("promotion")) or (old.get("list_price") or 0) > old["current_price"]
    new_promo = bool(new.get("promotion")) or (new.get("list_price") or 0) > new["current_price"]
    if old["current_price"] != new["current_price"]:
        pc = price_change(old["current_price"], new["current_price"])
        if old_promo and not new_promo and new["current_price"] == old.get("list_price"):
            changes.append({"type": "promotion_ended", **pc, "note": "returned to the previously shown regular price"})
        elif new_promo and not old_promo:
            changes.append({"type": "promotion_started", **pc, "note": "labeled promotion: temporary"})
        else:
            note = "" if new_promo else "no promotion shown; permanence unknown from two observations"
            changes.append({"type": f"price_{pc['direction']}", **pc, "note": note})
    if old.get("availability") != new.get("availability"):
        changes.append({"type": "availability_change", "old": old.get("availability"), "new": new.get("availability")})
    of, nf = {_norm(f): f for f in old.get("features", [])}, {_norm(f): f for f in new.get("features", [])}
    changes += [{"type": "feature_added", "feature": nf[k]} for k in nf if k not in of]
    changes += [{"type": "feature_removed", "feature": of[k]} for k in of if k not in nf]
    for field in ("headline", "marketing_copy"):
        if _norm(old.get(field)) != _norm(new.get(field)):
            changes.append({"type": "messaging_change", "field": field, "old": old.get(field), "new": new.get(field)})
    return {"status": "changes_detected" if changes else "no_meaningful_change", "changes": changes,
            "evidence": [old_id, new_id], "observed": [old["observed_at"], new["observed_at"]]}


def duplicates(path: str) -> dict:
    reviews = json.load(open(path, encoding="utf-8"))["reviews"]
    kept, dupes = [], []
    for r in reviews:
        text = re.sub(r"[^a-z0-9 ]+", "", " ".join(r["text"].lower().split()))
        for k in kept:
            ktext = re.sub(r"[^a-z0-9 ]+", "", " ".join(k["text"].lower().split()))
            same_author = r.get("reviewer") and r.get("reviewer") == k.get("reviewer")
            if text == ktext or (same_author and difflib.SequenceMatcher(None, text, ktext).ratio() >= 0.85):
                dupes.append({"review_id": r["review_id"], "duplicate_of": k["review_id"],
                              "kind": "exact" if text == ktext else "near"})
                break
        else:
            kept.append(r)
    return {"records": len(reviews), "unique": len(kept), "duplicates": dupes}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("price-change")
    a.add_argument("old", type=float)
    a.add_argument("new", type=float)
    b = sub.add_parser("compare")
    b.add_argument("file")
    b.add_argument("old_id")
    b.add_argument("new_id")
    c = sub.add_parser("duplicates")
    c.add_argument("file")
    args = p.parse_args(argv)
    if args.cmd == "price-change":
        out = price_change(args.old, args.new)
    elif args.cmd == "compare":
        out = compare(args.file, args.old_id, args.new_id)
    else:
        out = duplicates(args.file)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
