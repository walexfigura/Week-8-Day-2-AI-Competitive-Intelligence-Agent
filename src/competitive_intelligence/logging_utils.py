"""Trace IDs and structured (JSONL) logging.

Every agent run, scan, or evaluation gets a trace ID like `ci-20261114-a1b2c3`.
Each tool call is logged with that ID so you can reconstruct exactly what the
model asked for and what it received: `logs/trace-YYYY-MM-DD.jsonl`.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SECRET_KEYS = {"api_key", "authorization", "openai_api_key", "password", "token"}


def new_trace_id() -> str:
    return f"ci-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3)}"


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in _SECRET_KEYS else _scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


class TraceLogger:
    def __init__(self, logs_dir: Path | None, echo: bool = False):
        self.logs_dir = logs_dir
        self.echo = echo

    def log(self, trace_id: str, event: str, **fields: Any) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "trace_id": trace_id,
            "event": event,
            **_scrub(fields),
        }
        if self.logs_dir is not None:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            path = self.logs_dir / f"trace-{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, default=str) + "\n")
