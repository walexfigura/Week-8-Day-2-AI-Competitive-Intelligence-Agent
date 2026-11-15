"""Command-line interface: `python run.py <command>`.

Offline (no API key):  smoke · scan · briefing --offline · tool · eval --deterministic-only · build-skill
Needs OPENAI_API_KEY:  demo · briefing · eval (agent cases)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import MissingAPIKeyError, Settings

SCENARIO_FILE = Path("data/scenarios/scenarios.json")


def _p(text: str = "") -> None:
    print(text, flush=True)


def _scenarios(settings: Settings) -> dict[str, dict[str, Any]]:
    data = json.loads((settings.root / SCENARIO_FILE).read_text(encoding="utf-8"))
    return {s["id"]: s for s in data["scenarios"]}


def _print_tool_event(kind: str, data: dict[str, Any]) -> None:
    if kind == "run_started":
        _p(f"Trace {data['trace_id']} · model {data['model']}")
        _p("The model now decides which tools to call. Each line is one tool call:\n")
    elif kind == "tool_call":
        r = data["record"]
        args = r.arguments if len(r.arguments) <= 90 else r.arguments[:87] + "..."
        mark = "BLOCKED" if r.blocked else r.status
        _p(f"  {r.step:>2}. {r.tool}({args})")
        _p(f"      → {mark}: {r.summary}")


def _run_agent(settings: Settings, objective: str, scenario_id: str, *, quiet: bool, fault: dict[str, str] | None = None) -> int:
    from .agent import CompetitiveIntelligenceAgent
    from .services import Services

    settings.require_openai_key()
    agent = CompetitiveIntelligenceAgent(Services(settings), on_event=None if quiet else _print_tool_event)
    result = agent.run(objective, scenario_id=scenario_id, fault_injection=fault)
    _p()
    if result.status == "error":
        _p(f"Run failed: {result.error}")
        _p("See docs/troubleshooting.md. Logs: logs/trace-*.jsonl")
        return 1
    if result.report is None:
        _p(f"The agent stopped without saving a report (status: {result.status}). Try again or raise CI_MAX_ITERATIONS.")
        return 1
    rep = result.report
    _p("=" * 72)
    _p(rep["title"])
    _p("=" * 72)
    _p(rep["executive_summary"])
    _p()
    for s in rep["signals"]:
        _p(f"  [{s['priority'].upper():<21}] {s['title']}")
    for f in rep["sentiment_findings"]:
        _p(f"  [SENTIMENT            ] {f['statement']}")
    for n in rep["no_alert_decisions"]:
        _p(f"  [NO ALERT             ] {n['subject']}")
    for v in rep["verification_needed"]:
        _p(f"  [VERIFY               ] {v['item']}")
    if rep.get("validation_warnings"):
        _p(f"\nSaved with {len(rep['validation_warnings'])} validation warning(s) — see the report.")
    _p(f"\nReport:  {result.report_paths[0]}\nJSON:    {result.report_paths[1]}")
    _p(f"Tool calls: {len(result.tool_calls)} · model turns: {result.model_turns} · "
       f"tokens in/out: {result.input_tokens}/{result.output_tokens}")
    if result.blocked_attempts:
        _p(f"Blocked attempts: {result.blocked_attempts}")
    return 0


# --------------------------------------------------------------------------- commands
def cmd_demo(settings: Settings, args: argparse.Namespace) -> int:
    scenarios = _scenarios(settings)
    if args.list:
        for sid, sc in scenarios.items():
            _p(f"{sid:<26} {sc['title']}")
        return 0
    sc = scenarios.get(args.scenario)
    if sc is None:
        _p(f"Unknown scenario '{args.scenario}'. Run `python run.py demo --list`.")
        return 2
    _p(f"Scenario: {sc['title']}\nObjective: {sc['objective']}\n")
    return _run_agent(settings, sc["objective"], sc["id"], quiet=args.quiet, fault=sc.get("fault_injection"))


def cmd_briefing(settings: Settings, args: argparse.Namespace) -> int:
    if args.offline:
        from .briefing import run_offline_briefing
        from .services import Services

        settings.sentiment_source = "reference"
        result, ctx = run_offline_briefing(Services(settings))
        if result["status"] != "ok":
            _p(json.dumps(result, indent=2))
            return 1
        rep = ctx.report
        _p("Offline, rule-based briefing (no LLM).\n")
        _p(rep["executive_summary"] + "\n")
        _p(f"Report: {result['data']['markdown_path']}\nJSON:   {result['data']['json_path']}")
        return 0
    objective = args.objective or _scenarios(settings)["weekly_briefing"]["objective"]
    return _run_agent(settings, objective, "weekly_briefing" if not args.objective else "custom_briefing", quiet=args.quiet)


def cmd_scan(settings: Settings, args: argparse.Namespace) -> int:
    from .scan import record_findings, run_scan
    from .services import Services
    from .storage import write_report_files

    svc = Services(settings)
    scan = run_scan(svc, capture_live=args.capture_live)
    _p(f"Monitoring scan · trace {scan['trace_id']} · data mode: {scan['data_mode']} · no LLM used\n")
    for c in scan["comparisons"]:
        head = f"{c['product_id']:<11} {c['old_snapshot_id']} → {c['new_snapshot_id']}"
        if c["status"] in {"not_comparable", "incomplete_data"}:
            _p(f"{head}\n    INSUFFICIENT EVIDENCE: {' '.join(c['comparability_issues'])}")
        elif not c["events"]:
            _p(f"{head}\n    NO ALERT: " + ("formatting-only change" if c["formatting_only"] else "no meaningful change"))
        else:
            _p(head)
            for e in c["events"]:
                tier = e["baseline"]["suggested_priority"].replace("_", " ").upper()
                mag = f" {e['magnitude']['pct_display']}" if e.get("magnitude") and e["change_type"].startswith("price") else ""
                seen = " (already recorded)" if e["previously_recorded"] else ""
                value = e["new_value"] if e["change_type"] != "feature_removed" else e["old_value"]
                _p(f"    {tier:<9} {e['change_type']}{mag}: {str(value)[:70]}{seen}")
    for s in scan["single_observations"]:
        _p(f"{s['product_id']:<11} {s['snapshot_id']}\n    NOTE: {s['note']}")
    for e in scan["errors"]:
        _p(f"ERROR {e['product_id']} {e['step']}: {e['error']['message']}")
    _p(f"\nBaseline counts: {scan['event_counts_by_baseline']}")
    _p("Priorities above are the transparent rubric baseline. The agent (`python run.py briefing`) investigates further.")
    if args.save:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        lines = ["# Monitoring scan", "", f"Trace `{scan['trace_id']}` · fictional mock data · rubric baseline only", ""]
        for c in scan["comparisons"]:
            lines.append(f"- **{c['product_id']}** `{c['old_snapshot_id']}` → `{c['new_snapshot_id']}`: {c['status']}"
                         + "".join(f"\n  - {e['baseline']['suggested_priority']}: {e['change_type']}" for e in c["events"]))
        md, js = write_report_files(settings.reports_dir, f"{stamp}-scan", "\n".join(lines) + "\n", scan)
        _p(f"Saved {md.relative_to(settings.root)} and {js.relative_to(settings.root)}")
    if args.record:
        n = record_findings(svc, scan)
        _p(f"Recorded {n} new high/medium finding fingerprint(s) in state/findings.jsonl")
    return 0


def cmd_eval(settings: Settings, args: argparse.Namespace) -> int:
    from .evaluation import run_agent_cases, run_deterministic, summarize, to_json

    results = []
    if not args.agent_only:
        _p("Deterministic evaluations (no API key, repeatable)\n" + "-" * 60)
        det = run_deterministic(settings, args.case)
        for r in det:
            _p(f"{'PASS' if r.passed else 'FAIL'}  #{r.number:<2} {r.name}")
            if r.error:
                _p(f"        error: {r.error}")
            for c in r.checks:
                _p(f"        {'✓' if c.passed else '✗'} {c.name}: {c.detail}")
        results += det
    if not args.deterministic_only:
        _p("\nAgent evaluations (LLM, nondeterministic)\n" + "-" * 60)
        if not settings.has_openai_key:
            _p("SKIPPED: OPENAI_API_KEY is not set. Agent evaluations were not run.")
        else:
            agent_results = run_agent_cases(settings, args.case, repeat=args.repeat, progress=lambda m: _p(f"  {m}"))
            for r in agent_results:
                _p(f"{'PASS' if r.passed else 'FAIL'}  #{r.number:<2} {r.name}  [scenario {r.run_info.get('scenario')}, "
                   f"trace {r.run_info.get('trace_id')}]")
                if r.error:
                    _p(f"        error: {r.error}")
                for c in r.checks:
                    _p(f"        {'✓' if c.passed else '✗'} {c.name}: {c.detail}")
            results += agent_results
    summary = summarize(results)
    _p("\nSummary: " + "; ".join(f"{k}: {v['passed']} passed, {v['failed']} failed" for k, v in summary.items()))
    out_dir = settings.root / "evals" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"eval-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps({"summary": summary, "results": to_json(results)}, indent=2, ensure_ascii=False), encoding="utf-8")
    _p(f"Results saved to {out.relative_to(settings.root)}")
    return 0 if all(r.passed for r in results) else 1


def cmd_smoke(settings: Settings, args: argparse.Namespace) -> int:
    from .smoke import run_smoke

    _p("Offline smoke test (no API key needed)\n")
    results = run_smoke(settings)
    for name, ok, detail in results:
        _p(f"{'PASS' if ok else 'FAIL'}  {name}\n      {detail}")
    failed = [n for n, ok, _ in results if not ok]
    _p(f"\n{len(results) - len(failed)} of {len(results)} checks passed.")
    return 1 if failed else 0


def cmd_build_skill(settings: Settings, args: argparse.Namespace) -> int:
    from .skill_builder import build_skill_zip

    zip_path, info = build_skill_zip(settings.root, Path(args.output) if args.output else None)
    _p(f"Skill '{info['name']}' validated: {info['files']} files, {info['linked_files']} linked references, "
       f"description {info['description_chars']} chars.")
    _p(f"Created {zip_path} ({info['zip_entries']} entries)")
    _p("Next: upload the ZIP in Claude's Skills settings. Steps: claude-skill/competitive-intelligence/references/setup.md")
    return 0


def cmd_tool(settings: Settings, args: argparse.Namespace) -> int:
    from .logging_utils import new_trace_id
    from .services import Services
    from .tools import registry
    from .tools.base import ToolContext

    if args.name == "list":
        for spec in registry.TOOL_SPECS:
            params = ", ".join(spec.parameters["properties"])
            _p(f"{spec.name}({params})\n    {spec.description}")
        return 0
    settings.sentiment_source = "reference"
    ctx = ToolContext(services=Services(settings), trace_id=new_trace_id(), scenario_id="tool-cli")
    result = registry.execute(args.name, args.args, ctx)
    _p(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result.get("status") == "ok" else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python run.py", description="Northstar Supply competitive intelligence agent (fictional data).")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="Run the LLM agent on a scenario (needs OPENAI_API_KEY)")
    d.add_argument("--scenario", default="peaktrail_investigation", help="Scenario ID (see --list)")
    d.add_argument("--list", action="store_true", help="List scenarios and exit")
    d.add_argument("--quiet", action="store_true", help="Hide the step-by-step tool calls")
    d.set_defaults(func=cmd_demo)

    b = sub.add_parser("briefing", help="Weekly briefing across the watchlist (agent, or --offline rule-based)")
    b.add_argument("--offline", action="store_true", help="Rule-based briefing without an LLM")
    b.add_argument("--objective", help="Custom research objective for the agent")
    b.add_argument("--quiet", action="store_true")
    b.set_defaults(func=cmd_briefing)

    s = sub.add_parser("scan", help="Deterministic monitoring scan of stored snapshots (no LLM)")
    s.add_argument("--save", action="store_true", help="Save the scan to reports/")
    s.add_argument("--record", action="store_true", help="Record high/medium findings to avoid duplicate alerts next time")
    s.add_argument("--capture-live", action="store_true", help="In CI_DATA_MODE=live, fetch configured pages first")
    s.set_defaults(func=cmd_scan)

    e = sub.add_parser("eval", help="Run evaluations (deterministic always; agent cases need a key)")
    e.add_argument("--deterministic-only", action="store_true")
    e.add_argument("--agent-only", action="store_true")
    e.add_argument("--case", action="append", help="Case ID to run (repeatable)")
    e.add_argument("--repeat", type=int, default=1, help="Run each agent scenario N times")
    e.set_defaults(func=cmd_eval)

    sub.add_parser("smoke", help="Offline smoke test (no API key)").set_defaults(func=cmd_smoke)

    k = sub.add_parser("build-skill", help="Validate and zip the Claude Skill")
    k.add_argument("--output", help="Output folder (default: claude-skill/)")
    k.set_defaults(func=cmd_build_skill)

    t = sub.add_parser("tool", help="Call one agent tool directly, offline (or 'list')")
    t.add_argument("name", help="Tool name, or 'list'")
    t.add_argument("--args", default="{}", help="JSON arguments, e.g. '{\"product_id\": \"PT-RIDGE\"}'")
    t.set_defaults(func=cmd_tool)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = Settings.load()
        return args.func(settings, args)
    except MissingAPIKeyError as exc:
        _p(f"\n{exc}")
        return 2
    except (ValueError, RuntimeError) as exc:
        _p(f"\nError: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
