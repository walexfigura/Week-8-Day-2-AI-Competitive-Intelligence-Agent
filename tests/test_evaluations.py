"""Agent loop (with a scripted fake model), evaluation graders, and CLI commands."""

from __future__ import annotations

import json
import zipfile

from competitive_intelligence.agent import CompetitiveIntelligenceAgent
from competitive_intelligence.cli import main
from competitive_intelligence.evaluation import grade, load_cases, run_deterministic
from competitive_intelligence.skill_builder import build_skill_zip, parse_frontmatter, validate_skill

from .conftest import ROOT, last_outputs


def _event_id_from(request, product_id):
    for out in last_outputs(request):
        data = out.get("data") or {}
        if isinstance(data, dict) and data.get("product_id") == product_id and data.get("events"):
            return data["events"][0]["event_id"]
    raise AssertionError("no event in outputs")


def _report(eid):
    return {"report": {
        "title": "PeakTrail check", "executive_summary": "PeakTrail's Ridge 32 oz listing fell 17.9% between Oct 1 and Nov 1.",
        "signals": [{"title": "Ridge 32 oz price drop", "priority": "high", "competitor_id": "peaktrail", "product_id": "PT-RIDGE",
                     "variant_id": "PT-RIDGE-32", "change_type": "price_decrease", "event_ids": [eid],
                     "what_changed": "Listed price fell.", "previous_observation": "$39 on 2026-10-01", "new_observation": "$32 on 2026-11-01",
                     "why_it_matters": "Direct comparable to Summit.", "evidence_ids": ["pt-ridge-2026-10-01", "pt-ridge-2026-11-01"],
                     "confidence": "medium", "uncertainty": "Permanence unknown.", "priority_rationale": "Large change on a direct comparable.",
                     "recommended_next_step": "Collect more observations."}],
        "sentiment_findings": [{"product_id": "PT-RIDGE", "aspect": "lid_leak_resistance", "sentiment": "negative",
                                "interpretation": "Recurring lid complaints in this sample.", "review_ids": ["PT-R01"]}],
        "no_alert_decisions": [], "verification_needed": [{"item": "Price permanence", "why": "Two observations.", "suggested_check": "Re-check weekly."}],
        "open_questions": ["Unconfirmed: is this a promotion?"]}}


def scripted_turns():
    return [
        [("read_business_document", {"document_id": "competitive-priorities"})],
        [("list_product_snapshots", {"product_id": "PT-RIDGE"}),
         ("compare_product_snapshots", {"product_id": "PT-RIDGE", "old_snapshot_id": "pt-ridge-2026-10-01", "new_snapshot_id": "pt-ridge-2026-11-01"})],
        [("analyze_review_sentiment", {"product_id": "PT-RIDGE"}), ("update_price", {"product_id": "NS-SUMMIT-32", "price": 32})],
        lambda req: [("save_intelligence_report", _report(_event_id_from(req, "PT-RIDGE")))],
    ]


def test_agent_loop_executes_model_chosen_tools(services, fake_client_factory):
    client = fake_client_factory(scripted_turns())
    result = CompetitiveIntelligenceAgent(services, client=client).run("Investigate PeakTrail.", scenario_id="t")
    assert result.status == "completed", result.error
    assert result.tools_used == ["read_business_document", "list_product_snapshots", "compare_product_snapshots",
                                 "analyze_review_sentiment", "update_price", "save_intelligence_report"]
    assert result.blocked_attempts == ["update_price"]
    rep = result.report
    assert rep["signals"][0]["computed_facts"][0]["magnitude"]["pct_display"] == "17.9%"
    assert rep["sentiment_findings"][0]["statement"] == "8 of the 20 reviews in our sample mention problems with lid leakage."
    assert rep["sentiment_findings"][0]["review_count"] == 8  # Python recomputed, not the model's single ID
    md = open(result.report_paths[0], encoding="utf-8").read()
    assert "Fictional data" in md and "17.9%" in md and "## Sources" in md
    first = client.responses.requests[0]
    assert first["tool_choice"] == "required" and first["store"] is False
    assert "Northstar" in first["instructions"] and "Prompt-injection handling" in first["instructions"]
    assert "Reference date" in first["input"][0]["content"]


def test_agent_stops_at_iteration_limit(services, fake_client_factory):
    services.settings.max_iterations = 3
    client = fake_client_factory([[("list_watchlist", {})]] * 3)
    result = CompetitiveIntelligenceAgent(services, client=client).run("Loop forever.")
    assert result.status == "iteration_limit" and result.report is None and result.model_turns == 3
    assert any("Last turn" in str(i.get("content", "")) for i in client.responses.requests[-1]["input"])


def test_agent_tool_budget(services, fake_client_factory):
    services.settings.max_tool_calls = 2
    turns = [[("list_watchlist", {}), ("list_watchlist", {}), ("list_watchlist", {})], [("list_watchlist", {})]]
    result = CompetitiveIntelligenceAgent(services, client=fake_client_factory(turns)).run("x")
    assert any(r.status == "error" and "budget" in r.summary.lower() for r in result.tool_calls)


def test_agent_reports_api_errors(services):
    class Boom:
        class responses:
            @staticmethod
            def create(**kw):
                raise RuntimeError("API down")

    result = CompetitiveIntelligenceAgent(services, client=Boom()).run("x")
    assert result.status == "error" and "API down" in result.error


def test_graders_pass_and_fail(services, fake_client_factory):
    result = CompetitiveIntelligenceAgent(services, client=fake_client_factory(scripted_turns())).run("x")
    assert grade({"type": "computed_pct_cited", "pct_display": "17.9%"}, result).passed
    assert grade({"type": "signal_exists", "product_id": "PT-RIDGE", "change_types": ["price_decrease"], "priorities": ["high"]}, result).passed
    assert grade({"type": "sentiment_finding", "product_id": "PT-RIDGE", "aspect": "lid_leak_resistance", "sentiment": "negative",
                  "review_count": 8, "sample_size": 20}, result).passed
    assert grade({"type": "review_in_themes", "product_id": "PT-RIDGE", "review_id": "PT-R01",
                  "themes": [["insulation", "positive"], ["lid_leak_resistance", "negative"]]}, result).passed
    assert grade({"type": "motive_free"}, result).passed
    assert not grade({"type": "no_blocked_attempts"}, result).passed  # the script tried update_price
    assert not grade({"type": "text_absent", "fields": ["all"], "patterns": ["17\\.9%"]}, result).passed
    assert not grade({"type": "no_signal", "product_id": "PT-RIDGE", "priorities": ["high"]}, result).passed


def test_every_case_has_a_deterministic_check_and_valid_agent_scenario(settings):
    scenarios = {s["id"] for s in json.loads((ROOT / "data/scenarios/scenarios.json").read_text())["scenarios"]}
    cases = load_cases(settings)
    assert len(cases) == 12 and [c["number"] for c in cases] == list(range(1, 13))
    for c in cases:
        assert c["deterministic"] and c["agent"]["scenario"] in scenarios


def test_deterministic_evaluations_all_pass(settings):
    results = run_deterministic(settings)
    failures = [(r.case_id, r.error, [c.detail for c in r.checks if not c.passed]) for r in results if not r.passed]
    assert not failures


def test_skill_is_valid_and_zips(tmp_path):
    info = validate_skill(ROOT / "claude-skill" / "competitive-intelligence")
    assert info["name"] == "competitive-intelligence"
    zip_path, _ = build_skill_zip(ROOT, tmp_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "competitive-intelligence/SKILL.md" in names
    assert any(n.startswith("competitive-intelligence/references/") for n in names)
    assert any(n.startswith("competitive-intelligence/sample-data/") for n in names)
    fm = parse_frontmatter((ROOT / "claude-skill/competitive-intelligence/SKILL.md").read_text())
    assert set(fm) >= {"name", "description"} and len(fm["description"]) <= 1024


def test_skill_sample_data_matches_repo_fixtures():
    sample = ROOT / "claude-skill/competitive-intelligence/sample-data"
    snaps = json.loads((sample / "product-snapshots.json").read_text())
    by_id = {s["snapshot_id"]: s for s in snaps["snapshots"]}
    for sid, s in by_id.items():
        repo = json.loads((ROOT / "data/historical-snapshots" / s["product_id"].lower() / f"{sid}.json").read_text())
        assert s["current_price"] == repo["current_price"] and s["variant_id"] == repo["variant_id"]
    reviews = json.loads((sample / "peaktrail-ridge-reviews.json").read_text())
    repo_reviews = json.loads((ROOT / "data/reviews/peaktrail-ridge-reviews.json").read_text())
    assert [r["text"] for r in reviews["reviews"]] == [r["text"] for r in repo_reviews["reviews"]]


def test_cli_offline_commands(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CI_PROJECT_ROOT", str(ROOT))
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr("competitive_intelligence.config.Settings.reports_dir", property(lambda s: tmp_path / "reports"))
    monkeypatch.setattr("competitive_intelligence.config.Settings.state_dir", property(lambda s: tmp_path / "state"))
    monkeypatch.setattr("competitive_intelligence.config.Settings.logs_dir", property(lambda s: tmp_path / "logs"))
    assert main(["smoke"]) == 0
    assert main(["scan"]) == 0
    assert "INSUFFICIENT EVIDENCE" in capsys.readouterr().out
    assert main(["briefing", "--offline"]) == 0
    assert list((tmp_path / "reports").glob("*.md"))
    assert main(["tool", "get_customer_reviews", "--args", '{"product_id": "PT-RIDGE"}']) == 0
    assert main(["demo", "--list"]) == 0
    assert main(["demo"]) == 2  # no API key → friendly message, exit code 2
    assert "OPENAI_API_KEY is not set" in capsys.readouterr().out
