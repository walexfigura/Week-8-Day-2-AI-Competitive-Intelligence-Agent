"""Shared fixtures. Tests never need an API key and never write into the repo."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from competitive_intelligence.config import Settings, find_project_root
from competitive_intelligence.logging_utils import TraceLogger, new_trace_id
from competitive_intelligence.services import Services
from competitive_intelligence.tools.base import ToolContext

ROOT = find_project_root()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(root=ROOT, sentiment_source="reference", output_root=tmp_path, openai_api_key=None)


@pytest.fixture
def services(settings: Settings) -> Services:
    return Services(settings, logger=TraceLogger(None))


@pytest.fixture
def ctx(services: Services) -> ToolContext:
    return ToolContext(services=services, trace_id=new_trace_id(), scenario_id="test")


# ---------------------------------------------------------------- fake OpenAI client
@dataclass
class FakeCall:
    name: str
    arguments: str
    call_id: str
    type: str = "function_call"

    def model_dump(self, exclude_none: bool = True) -> dict[str, Any]:
        return {"type": self.type, "name": self.name, "arguments": self.arguments, "call_id": self.call_id}


@dataclass
class FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 20


@dataclass
class FakeResponse:
    output: list[Any]
    usage: FakeUsage = field(default_factory=FakeUsage)
    output_text: str = ""


class FakeResponses:
    """Plays back scripted turns. Each turn is a list of (tool_name, args) or a callable(inputs) -> list."""

    def __init__(self, turns: list[Any]):
        self.turns = list(turns)
        self.requests: list[dict[str, Any]] = []
        self._n = 0

    def create(self, **kwargs: Any) -> FakeResponse:
        self.requests.append(kwargs)
        if not self.turns:
            raise AssertionError("FakeResponses ran out of scripted turns")
        turn = self.turns.pop(0)
        if callable(turn):
            turn = turn(kwargs)
        if isinstance(turn, FakeResponse):
            return turn
        calls = []
        for name, args in turn:
            self._n += 1
            calls.append(FakeCall(name=name, arguments=json.dumps(args), call_id=f"call_{self._n}"))
        return FakeResponse(output=calls)


class FakeClient:
    def __init__(self, turns: list[Any]):
        self.responses = FakeResponses(turns)


@pytest.fixture
def fake_client_factory():
    return FakeClient


def last_outputs(request: dict[str, Any]) -> list[dict[str, Any]]:
    """Decode the function_call_output items in a request sent to the fake client."""
    return [json.loads(i["output"]) for i in request["input"] if isinstance(i, dict) and i.get("type") == "function_call_output"]
