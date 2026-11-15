"""Settings loaded from environment variables (and an optional `.env` file).

Every setting has a safe default so offline commands (`smoke`, `scan`,
`briefing --offline`, `tool`, `build-skill`, unit tests) work without credentials.
Only model-backed commands need OPENAI_API_KEY.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_REFERENCE_DATE = "2026-11-14"  # the "today" of the fictional datasets


def find_project_root() -> Path:
    """Locate the repository root (the folder containing `data/` and `agent/`)."""
    override = os.environ.get("CI_PROJECT_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    here = Path(__file__).resolve()
    for candidate in [*here.parents, Path.cwd()]:
        if (candidate / "data").is_dir() and (candidate / "agent").is_dir():
            return candidate
    raise RuntimeError(
        "Could not find the project root (a folder containing 'data/' and 'agent/'). "
        "Run commands from the repository folder or set CI_PROJECT_ROOT."
    )


def _load_dotenv(root: Path) -> None:
    env_file = root / ".env"
    if not env_file.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - declared dependency
        return
    load_dotenv(env_file, override=False)


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got {raw!r}") from exc


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a number, got {raw!r}") from exc


class MissingAPIKeyError(RuntimeError):
    pass


@dataclass
class Settings:
    root: Path
    openai_api_key: str | None = None
    openai_model: str = DEFAULT_MODEL
    openai_reasoning_effort: str | None = None
    sentiment_model: str | None = None
    sentiment_source: str = "llm"  # "llm" or "reference"
    data_mode: str = "mock"  # "mock" or "live"
    max_iterations: int = 16
    max_tool_calls: int = 40
    reference_date: str = DEFAULT_REFERENCE_DATE
    live_sources_file: str = "live-sources.json"
    live_min_interval_seconds: float = 10.0
    live_timeout_seconds: float = 15.0
    live_user_agent: str = "NorthstarCI-Educational/1.0 (+manual research run)"
    review_export_dir: str | None = None
    output_root: Path | None = None  # where reports/, state/, logs/ go (tests point this at a temp dir)

    # ------------------------------------------------------------- paths
    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def agent_dir(self) -> Path:
        return self.root / "agent"

    @property
    def kb_dir(self) -> Path:
        return self.root / "knowledge-base"

    @property
    def competitors_dir(self) -> Path:
        return self.root / "competitors"

    @property
    def reports_dir(self) -> Path:
        return (self.output_root or self.root) / "reports"

    @property
    def state_dir(self) -> Path:
        return (self.output_root or self.root) / "state"

    @property
    def logs_dir(self) -> Path:
        return (self.output_root or self.root) / "logs"

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key)

    def require_openai_key(self) -> str:
        if not self.openai_api_key:
            raise MissingAPIKeyError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
                "or run an offline command instead: `python run.py smoke`, `python run.py scan`, "
                "or `python run.py briefing --offline`."
            )
        return self.openai_api_key

    @classmethod
    def load(cls, root: Path | None = None) -> Settings:
        root = root or find_project_root()
        _load_dotenv(root)
        mode = os.environ.get("CI_DATA_MODE", "mock").strip().lower() or "mock"
        if mode not in {"mock", "live"}:
            raise ValueError("CI_DATA_MODE must be 'mock' or 'live'")
        sentiment_source = os.environ.get("CI_SENTIMENT_SOURCE", "llm").strip().lower() or "llm"
        if sentiment_source not in {"llm", "reference"}:
            raise ValueError("CI_SENTIMENT_SOURCE must be 'llm' or 'reference'")
        return cls(
            root=root,
            openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip() or None,
            openai_model=os.environ.get("OPENAI_MODEL", "").strip() or DEFAULT_MODEL,
            openai_reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "").strip() or None,
            sentiment_model=os.environ.get("CI_SENTIMENT_MODEL", "").strip() or None,
            sentiment_source=sentiment_source,
            data_mode=mode,
            max_iterations=_int_env("CI_MAX_ITERATIONS", 16),
            max_tool_calls=_int_env("CI_MAX_TOOL_CALLS", 40),
            reference_date=os.environ.get("CI_REFERENCE_DATE", "").strip() or DEFAULT_REFERENCE_DATE,
            live_sources_file=os.environ.get("CI_LIVE_SOURCES_FILE", "").strip() or "live-sources.json",
            live_min_interval_seconds=_float_env("CI_LIVE_MIN_INTERVAL_SECONDS", 10.0),
            live_timeout_seconds=_float_env("CI_LIVE_TIMEOUT_SECONDS", 15.0),
            review_export_dir=os.environ.get("CI_REVIEW_EXPORT_DIR", "").strip() or None,
        )
