"""The agent loop: OpenAI Responses API + function calling.

One run looks like this:

    objective ──► model decides which tool(s) to call            ◄──┐
              ──► Python validates and executes them (logged)       │ repeat
              ──► structured results go back to the model ──────────┘
              ──► model calls save_intelligence_report
              ──► Python validates citations/claims, adds computed facts, saves

Nothing here hard-codes "call X, then Y". The model reads the objective, the
business documents, and each tool result, and chooses the next step. The loop
is bounded by `max_iterations` model turns and `max_tool_calls` executions so
a confused model cannot loop forever.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .logging_utils import new_trace_id
from .services import Services
from .tools import registry
from .tools.base import ToolContext


@dataclass
class ToolCallRecord:
    step: int
    tool: str
    arguments: str
    status: str
    summary: str
    duration_ms: int
    blocked: bool = False


@dataclass
class AgentResult:
    trace_id: str
    scenario_id: str
    status: str  # completed | iteration_limit | error
    report: dict[str, Any] | None
    report_paths: tuple[str, str] | None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    blocked_attempts: list[str] = field(default_factory=list)
    model_turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    context: ToolContext | None = None

    @property
    def tools_used(self) -> list[str]:
        return [c.tool for c in self.tool_calls]


def _to_input_item(item: Any) -> dict[str, Any]:
    """Convert a response output item back into an input item for the next turn."""
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_none=True)
    if isinstance(item, dict):
        return dict(item)
    return dict(vars(item))


def build_objective_message(objective: str, settings: Any, extra_context: str | None = None) -> str:
    parts = [
        "Research objective:",
        objective.strip(),
        "",
        f"Reference date (today): {settings.reference_date}",
        f"Data mode: {settings.data_mode}"
        + (" (fictional local fixtures — never present findings as real market research)" if settings.data_mode == "mock" else ""),
    ]
    if extra_context:
        parts += ["", extra_context]
    parts += ["", "Investigate with your tools, then call save_intelligence_report exactly once."]
    return "\n".join(parts)


class CompetitiveIntelligenceAgent:
    def __init__(self, services: Services, client: Any | None = None,
                 on_event: Callable[[str, dict[str, Any]], None] | None = None):
        self.services = services
        self.settings = services.settings
        self._client = client
        self.on_event = on_event or (lambda kind, data: None)
        agent_dir = self.settings.agent_dir
        self.instructions = (
            (agent_dir / "system-prompt.md").read_text(encoding="utf-8")
            + "\n\n"
            + (agent_dir / "scope.md").read_text(encoding="utf-8")
        )

    @property
    def client(self) -> Any:
        if self._client is None:
            from openai import OpenAI  # imported lazily so offline commands don't need it

            self._client = OpenAI(api_key=self.settings.require_openai_key(), max_retries=2, timeout=120)
        return self._client

    def _create_response(self, input_items: list[dict[str, Any]]) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.settings.openai_model,
            "instructions": self.instructions,
            "input": input_items,
            "tools": registry.openai_tools(),
            "tool_choice": "required",  # every turn is a tool call; the last one saves the report
            "parallel_tool_calls": True,
            "store": False,  # don't keep conversation state on OpenAI's servers
        }
        if self.settings.openai_reasoning_effort:
            kwargs["reasoning"] = {"effort": self.settings.openai_reasoning_effort}
            # With store=False, reasoning items must be passed back in encrypted form.
            kwargs["include"] = ["reasoning.encrypted_content"]
        return self.client.responses.create(**kwargs)

    def run(
        self,
        objective: str,
        *,
        scenario_id: str = "adhoc",
        extra_context: str | None = None,
        fault_injection: dict[str, str] | None = None,
        trace_id: str | None = None,
    ) -> AgentResult:
        settings = self.settings
        trace_id = trace_id or new_trace_id()
        log = self.services.logger.log
        ctx = ToolContext(
            services=self.services,
            trace_id=trace_id,
            scenario_id=scenario_id,
            client=self.client if settings.sentiment_source == "llm" else None,
            fault_injection=dict(fault_injection or {}),
        )
        ctx.run_info = {
            "producer": f"LLM agent run (model `{settings.openai_model}`, OpenAI Responses API with tool calling)",
            "model": settings.openai_model,
            "trace_id": trace_id,
            "scenario_id": scenario_id,
            "data_mode": f"{settings.data_mode} (fictional fixtures)" if settings.data_mode == "mock" else settings.data_mode,
        }
        result = AgentResult(trace_id=trace_id, scenario_id=scenario_id, status="iteration_limit",
                             report=None, report_paths=None, context=ctx)
        log(trace_id, "run_started", scenario_id=scenario_id, model=settings.openai_model,
            data_mode=settings.data_mode, fault_injection=ctx.fault_injection)
        self.on_event("run_started", {"trace_id": trace_id, "model": settings.openai_model})

        input_items: list[dict[str, Any]] = [
            {"role": "user", "content": build_objective_message(objective, settings, extra_context)}
        ]
        executed = 0
        try:
            for turn in range(1, settings.max_iterations + 1):
                response = self._create_response(input_items)
                result.model_turns += 1
                usage = getattr(response, "usage", None)
                if usage is not None:
                    result.input_tokens += getattr(usage, "input_tokens", 0) or 0
                    result.output_tokens += getattr(usage, "output_tokens", 0) or 0
                calls = [o for o in response.output if getattr(o, "type", None) == "function_call"]
                input_items.extend(_to_input_item(o) for o in response.output)
                log(trace_id, "model_turn", turn=turn, function_calls=[c.name for c in calls])
                if not calls:
                    input_items.append({"role": "user", "content": f"Call {registry.FINAL_TOOL} to finish."})
                    continue

                remaining_turns = settings.max_iterations - turn
                for call in calls:
                    if call.name != registry.FINAL_TOOL and executed >= settings.max_tool_calls:
                        output = {"status": "error", "error": {"code": "tool_budget_exhausted",
                                  "message": f"Tool budget reached. Call {registry.FINAL_TOOL} now."}}
                        duration = 0
                    else:
                        executed += 1
                        ctx.run_info.update({"tool_calls": executed, "model_turns": result.model_turns})
                        output, duration = registry.timed_execute(call.name, call.arguments, ctx)
                    record = ToolCallRecord(
                        step=len(result.tool_calls) + 1,
                        tool=call.name,
                        arguments=call.arguments if isinstance(call.arguments, str) else str(call.arguments),
                        status=output.get("status", "?"),
                        summary=registry.summarize(output),
                        duration_ms=duration,
                        blocked=bool(output.get("blocked")),
                    )
                    result.tool_calls.append(record)
                    if record.blocked:
                        result.blocked_attempts.append(call.name)
                    log(trace_id, "tool_call", step=record.step, tool=call.name, arguments=record.arguments[:2000],
                        status=record.status, summary=record.summary, duration_ms=duration, blocked=record.blocked)
                    self.on_event("tool_call", {"record": record})
                    input_items.append(
                        {"type": "function_call_output", "call_id": call.call_id, "output": registry.serialize(output)}
                    )
                if ctx.report is not None:
                    result.status = "completed"
                    break
                if remaining_turns == 1:
                    input_items.append({"role": "user", "content": f"Last turn: call {registry.FINAL_TOOL} now with what you have."})
        except Exception as exc:  # noqa: BLE001 - report API/runtime errors cleanly
            result.status = "error"
            result.error = f"{type(exc).__name__}: {exc}"
            log(trace_id, "run_error", error=result.error)

        result.report = ctx.report
        result.report_paths = ctx.report_paths
        log(trace_id, "run_finished", status=result.status, tool_calls=executed, model_turns=result.model_turns,
            report=ctx.report_paths[0] if ctx.report_paths else None,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens)
        self.on_event("run_finished", {"result": result})
        return result
