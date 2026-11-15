"""Northstar business-context tools (our products, knowledge search, document reading)."""

from __future__ import annotations

from typing import Any

from .base import ToolContext, invalid, not_found, ok


def get_our_product_info(ctx: ToolContext, product_id: str | None = None) -> dict[str, Any]:
    products = ctx.services.our_products
    if not product_id:
        for pid in products:
            ctx.remember(pid, "northstar_product")
        summary = [
            {"product_id": p["product_id"], "name": p["name"], "price": p["price"], "currency": p["currency"],
             "size_oz": p["size_oz"]}
            for p in products.values()
        ]
        return ok({"products": summary, "tip": "Call again with a product_id for verified features and limitations."})
    product = products.get(product_id)
    if product is None:
        return not_found("unknown_product", f"No Northstar product '{product_id}'. Known: {', '.join(products)}.")
    ctx.remember(product_id, "northstar_product")
    return ok({**product, "rule": "Only 'verified_features' may be used as differentiators."})


def search_business_knowledge(ctx: ToolContext, query: str) -> dict[str, Any]:
    if not query or not query.strip():
        return invalid("query must not be empty")
    results = ctx.services.knowledge.search(query)
    for r in results:
        ctx.remember(r["document_id"], "document")
    return ok({"query": query, "results": results, "available_documents": sorted(ctx.services.knowledge.docs)})


def read_business_document(ctx: ToolContext, document_id: str) -> dict[str, Any]:
    text = ctx.services.knowledge.read(document_id)
    if text is None:
        return not_found(
            "unknown_document",
            f"No document '{document_id}'. Available: {', '.join(sorted(ctx.services.knowledge.docs))}.",
        )
    ctx.remember(document_id, "document")
    return ok({"document_id": document_id, "markdown": text})
