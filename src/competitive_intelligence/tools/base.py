"""Shared tool plumbing: the run context, result envelopes, and the evidence ledger.

Every tool returns the same envelope so the model always knows what happened:

    {"status": "ok",            "data": {...}}
    {"status": "not_found",     "error": {"code": ..., "message": ...}}
    {"status": "invalid_input", "error": {...}}
    {"status": "error",         "error": {...}}      # source unavailable / malformed

The **evidence ledger** records every ID a tool has returned during this run
(snapshot IDs, source IDs, review IDs, news IDs, event IDs). The final report
may only cite IDs in the ledger, which stops the model from inventing sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import ChangeEvent, ComparisonResult
from ..services import Services


@dataclass
class ToolContext:
    services: Services
    trace_id: str
    scenario_id: str = "adhoc"
    client: Any = None  # OpenAI client, used by analyze_review_sentiment in "llm" mode
    fault_injection: dict[str, str] = field(default_factory=dict)
    evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: dict[str, tuple[ChangeEvent, ComparisonResult]] = field(default_factory=dict)
    comparisons: dict[str, ComparisonResult] = field(default_factory=dict)
    priority_baselines: dict[str, dict[str, Any]] = field(default_factory=dict)
    sentiment: dict[str, dict[str, Any]] = field(default_factory=dict)
    injection_observations: list[dict[str, Any]] = field(default_factory=list)
    report: dict[str, Any] | None = None
    report_paths: tuple[str, str] | None = None
    report_rejections: int = 0
    run_info: dict[str, Any] = field(default_factory=dict)

    @property
    def settings(self):
        return self.services.settings

    def remember(self, evidence_id: str | None, kind: str, **meta: Any) -> None:
        if evidence_id:
            entry = self.evidence.setdefault(evidence_id, {"kind": kind})
            entry.update({k: v for k, v in meta.items() if v is not None})


def ok(data: Any, **extra: Any) -> dict[str, Any]:
    return {"status": "ok", "data": data, **extra}


def fail(status: str, code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, "error": {"code": code, "message": message}, **extra}


def not_found(code: str, message: str) -> dict[str, Any]:
    return fail("not_found", code, message)


def invalid(message: str, **extra: Any) -> dict[str, Any]:
    return fail("invalid_input", "invalid_input", message, **extra)
