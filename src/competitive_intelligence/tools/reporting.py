"""The final tool: validate the model's report, enrich it with computed facts, save it."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..reports import enrich_report, render_markdown, validate_report
from ..storage import write_report_files
from .base import ToolContext, invalid, ok

MAX_REJECTIONS = 3


def save_intelligence_report(ctx: ToolContext, report: dict[str, Any], *, run_info: dict[str, Any] | None = None) -> dict[str, Any]:
    if ctx.report is not None:
        return invalid("A report was already saved in this run.")
    problems = validate_report(ctx, report)
    warnings: list[str] = []
    if problems:
        ctx.report_rejections += 1
        if ctx.report_rejections < MAX_REJECTIONS:
            return invalid(
                "The report was not saved. Fix these problems and call save_intelligence_report again.",
                problems=problems,
            )
        # Last attempt: save, but keep the problems visible to readers instead of hiding them.
        warnings = problems
    info = dict(run_info or ctx.run_info or {})
    info.setdefault("trace_id", ctx.trace_id)
    info.setdefault("scenario_id", ctx.scenario_id)
    info.setdefault("data_mode", ctx.settings.data_mode)
    enriched = enrich_report(ctx, report, info)
    enriched["validation_warnings"] = warnings
    markdown = render_markdown(enriched)
    if warnings:
        markdown += "\n## Validation warnings\n\n" + "\n".join(f"- {w}" for w in warnings) + "\n"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    md_path, json_path = write_report_files(
        ctx.settings.reports_dir, f"{stamp}-{ctx.scenario_id}", markdown, {**enriched, "submitted_report": report}
    )
    ctx.report = enriched
    ctx.report_paths = (str(md_path), str(json_path))
    rel = lambda p: str(p.relative_to(ctx.settings.root)) if p.is_relative_to(ctx.settings.root) else str(p)  # noqa: E731
    return ok({"saved": True, "markdown_path": rel(md_path), "json_path": rel(json_path), "validation_warnings": warnings})
