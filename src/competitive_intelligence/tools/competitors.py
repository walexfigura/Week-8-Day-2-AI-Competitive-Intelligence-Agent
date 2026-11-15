"""Watchlist, competitor profiles, and news tools."""

from __future__ import annotations

from typing import Any

from ..guardrails import detect_injection
from .base import ToolContext, not_found, ok


def list_watchlist(ctx: ToolContext) -> dict[str, Any]:
    wl = ctx.services.watchlist
    competitors = []
    for comp in wl.competitors.values():
        ctx.remember(comp["competitor_id"], "competitor")
        products = []
        for prod in comp["products"]:
            ctx.remember(prod["product_id"], "competitor_product", competitor_id=comp["competitor_id"])
            products.append(
                {
                    "product_id": prod["product_id"],
                    "name": prod["name"],
                    "has_review_dataset": bool(prod.get("review_dataset")),
                    "tracked_variants": prod["tracked_variants"],
                }
            )
        competitors.append(
            {
                "competitor_id": comp["competitor_id"],
                "name": comp["name"],
                "segment": comp["segment"],
                "watch_priority": comp["watch_priority"],
                "products": products,
            }
        )
    return ok({"notice": wl.data["_meta"]["notice"], "competitors": competitors})


def get_competitor_profile(ctx: ToolContext, competitor_id: str) -> dict[str, Any]:
    comp = ctx.services.watchlist.competitors.get(competitor_id)
    text = ctx.services.knowledge.read(f"profile:{competitor_id}")
    if comp is None or text is None:
        known = ", ".join(ctx.services.watchlist.competitors)
        return not_found("unknown_competitor", f"No competitor '{competitor_id}'. Known competitors: {known}.")
    ctx.remember(competitor_id, "competitor")
    ctx.remember(f"profile:{competitor_id}", "document")
    return ok({"competitor_id": competitor_id, "document_id": f"profile:{competitor_id}", "profile_markdown": text})


def get_competitor_news(ctx: ToolContext, competitor_id: str) -> dict[str, Any]:
    if competitor_id not in ctx.services.watchlist.competitors:
        return not_found("unknown_competitor", f"No competitor '{competitor_id}'.")
    items = []
    for item in ctx.services.news.get(competitor_id):
        ctx.remember(item["news_id"], "news", source_id=item["source_id"], observed_at=item["published_at"],
                     source_url=item["source_url"], reliability=item["reliability"])
        ctx.remember(item["source_id"], "source", source_url=item["source_url"])
        flags = detect_injection(item["summary"]) + detect_injection(item["title"])
        items.append(
            {
                "news_id": item["news_id"],
                "source_id": item["source_id"],
                "published_at": item["published_at"],
                "source_type": item["source_type"],
                "reliability": item["reliability"],
                "source_url": item["source_url"],
                "untrusted_content": {"title": item["title"], "summary": item["summary"]},
                "possible_prompt_injection": flags,
            }
        )
    return ok(
        {
            "competitor_id": competitor_id,
            "items": items,
            "reading_note": "Only 'primary_source' items show what the company itself said. 'unverified' items cannot support conclusions.",
        }
    )
