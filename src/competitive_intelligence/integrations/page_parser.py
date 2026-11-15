"""Parse a product page (HTML) into a normalized observation.

The same parser is used for the local mock fixtures and for the optional live
fetcher, so the mock path exercises real parsing code.

Strategy:
1. Prefer schema.org `Product` JSON-LD (https://schema.org/Product): name,
   offers (sku, price, priceCurrency, availability, priceValidUntil) and
   strikethrough prices in `priceSpecification`.
2. Fall back to visible HTML hooks for anything JSON-LD lacks:
   `.product-headline`, `.feature-list li`, `.product-description`,
   `.price-current`, `.price-compare-at`, `.promo-banner`, `.availability`.
3. Text inside elements hidden with `style="display:none"` or `hidden` is kept
   separately as `hidden_text` — a common place for prompt-injection payloads.

This is deliberately small and standard-library only. Real sites vary a lot;
see docs/live-integrations.md for what this does and does not handle.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

_AVAILABILITY = {
    "instock": "in_stock",
    "outofstock": "out_of_stock",
    "soldout": "out_of_stock",
    "preorder": "preorder",
    "discontinued": "discontinued",
}
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
_PRICE_RE = re.compile(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)")


def _clean(text: str) -> str:
    return " ".join(text.split())


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    match = _PRICE_RE.search(str(text))
    return float(match.group(1).replace(",", "")) if match else None


def _availability(value: str | None) -> str | None:
    if not value:
        return None
    key = re.sub(r"[^a-z]", "", value.rsplit("/", 1)[-1].lower())
    if key in _AVAILABILITY:
        return _AVAILABILITY[key]
    lowered = value.lower()
    if "sold out" in lowered or "out of stock" in lowered:
        return "out_of_stock"
    if "in stock" in lowered:
        return "in_stock"
    return None


@dataclass
class _Capture:
    key: str
    depth: int
    hidden_depth: int | None = None
    buf: list[str] = field(default_factory=list)


class _PageHTMLParser(HTMLParser):
    """Collects JSON-LD blocks, meta tags, and text of elements with known classes."""

    CLASS_KEYS = {
        "product-title": "title",
        "product-headline": "headline",
        "price-current": "price_current",
        "price-compare-at": "price_compare_at",
        "promo-banner": "promo",
        "availability": "availability",
        "product-description": "description",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.jsonld: list[str] = []
        self._in_jsonld = False
        self._jsonld_buf: list[str] = []
        self.meta: dict[str, str] = {}
        self.texts: dict[str, list[str]] = {}
        self.features: list[str] = []
        self.hidden: list[str] = []
        self.variants: list[dict[str, str]] = []
        self.selected_variant: str | None = None
        self.product_id: str | None = None
        self.canonical: str | None = None
        self.promo_ends: str | None = None
        self._captures: list[_Capture] = []
        self._hidden_stack: list[int] = []
        self._feature_list_depth: int | None = None
        self._feature_item: list[str] | None = None
        self._variant_item: dict[str, str] | None = None

    # -- helpers
    def _is_hidden(self) -> bool:
        return bool(self._hidden_stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag in _VOID:
            if tag == "meta" and a.get("name"):
                self.meta[a["name"]] = a.get("content", "")
            if tag == "link" and a.get("rel") == "canonical":
                self.canonical = a.get("href")
            return
        self.depth += 1
        style = a.get("style", "").replace(" ", "").lower()
        if "display:none" in style or "hidden" in a or a.get("aria-hidden") == "true":
            self._hidden_stack.append(self.depth)
        if tag == "script" and a.get("type") == "application/ld+json":
            self._in_jsonld = True
            self._jsonld_buf = []
        if tag == "main" and "data-product-id" in a:
            self.product_id = a["data-product-id"]
            self.selected_variant = a.get("data-selected-variant") or None
        classes = set(a.get("class", "").split())
        for cls, key in self.CLASS_KEYS.items():
            if cls in classes:
                self._captures.append(_Capture(key=key, depth=self.depth))
                if key == "promo":
                    self.promo_ends = a.get("data-ends") or None
        if tag == "ul" and "feature-list" in classes:
            self._feature_list_depth = self.depth
        if tag == "li" and self._feature_list_depth is not None:
            self._feature_item = []
        if tag == "li" and "data-variant-id" in a:
            self._variant_item = {"variant_id": a["data-variant-id"], "size_oz": a.get("data-size-oz", ""), "label": ""}

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID:
            return
        if tag == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._jsonld_buf))
            self._in_jsonld = False
        if tag == "li" and self._feature_item is not None:
            text = _clean("".join(self._feature_item))
            if text:
                self.features.append(text)
            self._feature_item = None
        if tag == "li" and self._variant_item is not None:
            self._variant_item["label"] = _clean(self._variant_item["label"])
            self.variants.append(self._variant_item)
            self._variant_item = None
        if tag == "ul" and self._feature_list_depth == self.depth:
            self._feature_list_depth = None
        while self._captures and self._captures[-1].depth == self.depth:
            cap = self._captures.pop()
            self.texts.setdefault(cap.key, []).append(_clean("".join(cap.buf)))
        if self._hidden_stack and self._hidden_stack[-1] == self.depth:
            self._hidden_stack.pop()
        self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._jsonld_buf.append(data)
            return
        if self._is_hidden():
            if data.strip():
                self.hidden.append(_clean(data))
            return
        for cap in self._captures:
            cap.buf.append(data)
        if self._feature_item is not None:
            self._feature_item.append(data)
        if self._variant_item is not None:
            self._variant_item["label"] += data


def _find_product(obj: Any) -> dict[str, Any] | None:
    if isinstance(obj, list):
        for item in obj:
            found = _find_product(item)
            if found:
                return found
    elif isinstance(obj, dict):
        types = obj.get("@type")
        types = types if isinstance(types, list) else [types]
        if "Product" in types:
            return obj
        if "@graph" in obj:
            return _find_product(obj["@graph"])
    return None


def parse_product_page(html: str, variant_id: str | None = None) -> dict[str, Any]:
    """Return a dict of normalized fields plus `parse_warnings` and `offers`.

    `variant_id` selects which offer to report; by default the page's selected
    variant (or the only offer) is used.
    """
    parser = _PageHTMLParser()
    parser.feed(html)
    parser.close()
    warnings: list[str] = []

    product: dict[str, Any] | None = None
    for block in parser.jsonld:
        try:
            product = _find_product(json.loads(block))
        except json.JSONDecodeError:
            warnings.append("A JSON-LD block could not be parsed")
            continue
        if product:
            break
    if product is None:
        warnings.append("No schema.org Product structured data found; using visible page text only")

    offers: list[dict[str, Any]] = []
    if product:
        raw_offers = product.get("offers") or []
        raw_offers = raw_offers if isinstance(raw_offers, list) else [raw_offers]
        for off in raw_offers:
            if not isinstance(off, dict):
                continue
            strike = None
            specs = off.get("priceSpecification") or []
            for spec in specs if isinstance(specs, list) else [specs]:
                if isinstance(spec, dict) and "StrikethroughPrice" in str(spec.get("priceType", "")):
                    strike = _parse_price(spec.get("price"))
            offers.append(
                {
                    "variant_id": off.get("sku"),
                    "label": off.get("name"),
                    "price": _parse_price(off.get("price")),
                    "currency": off.get("priceCurrency"),
                    "availability": _availability(off.get("availability")),
                    "list_price": strike,
                    "price_valid_until": off.get("priceValidUntil"),
                }
            )

    def text(key: str) -> str | None:
        values = [v for v in parser.texts.get(key, []) if v]
        return values[0] if values else None

    wanted = variant_id or parser.selected_variant
    offer = None
    if offers:
        offer = next((o for o in offers if o["variant_id"] == wanted), None)
        if offer is None and wanted is None and len(offers) == 1:
            offer = offers[0]
        if offer is None and wanted is not None:
            warnings.append(f"Variant {wanted} not found in structured offers")

    visible_selected = wanted is None or wanted == parser.selected_variant
    current_price = offer["price"] if offer else (_parse_price(text("price_current")) if visible_selected else None)
    currency = offer["currency"] if offer else None
    if currency is None and current_price is not None and (text("price_current") or "").strip().startswith("$"):
        warnings.append("Currency inferred only from a '$' symbol; treat as unverified")
    list_price = None
    if offer and offer.get("list_price") is not None:
        list_price = offer["list_price"]
    elif visible_selected:
        list_price = _parse_price(text("price_compare_at"))
    availability = offer["availability"] if offer else (_availability(text("availability")) if visible_selected else None)
    promo_label = text("promo") if visible_selected else None
    promotion = None
    if promo_label:
        promotion = {"label": promo_label, "ends_at": parser.promo_ends}

    variant_meta = next((v for v in parser.variants if v["variant_id"] == (offer or {}).get("variant_id", wanted)), None)
    size_oz = None
    if variant_meta and variant_meta.get("size_oz"):
        try:
            size_oz = float(variant_meta["size_oz"])
        except ValueError:
            size_oz = None

    description = text("description")
    hidden_text = " ".join(parser.hidden) or None
    if description and hidden_text:
        description = _clean(description.replace(hidden_text, ""))

    for name, value in (("price", current_price), ("availability", availability)):
        if value is None:
            warnings.append(f"Could not extract {name}")
    if not parser.features:
        warnings.append("Could not extract a feature list")

    return {
        "product_name": (product or {}).get("name") or text("title"),
        "page_product_id": parser.product_id,
        "variant_id": (offer or {}).get("variant_id") or wanted,
        "variant_label": (offer or {}).get("label") or (variant_meta or {}).get("label"),
        "size_oz": size_oz,
        "selected_variant_on_page": parser.selected_variant,
        "current_price": current_price,
        "list_price": list_price,
        "currency": currency,
        "promotion": promotion,
        "availability": availability,
        "features": parser.features,
        "headline": text("headline"),
        "marketing_copy": description or None,
        "hidden_text": hidden_text,
        "offers": offers,
        "canonical_url": parser.canonical,
        "fixture_meta": {k[3:]: v for k, v in parser.meta.items() if k.startswith("ci:")},
        "parse_warnings": warnings,
    }
