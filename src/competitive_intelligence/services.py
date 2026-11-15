"""Wire settings to data sources (mock by default, live adapters when configured)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Settings
from .integrations.mock_sources import (
    ExportReviewSource,
    FixtureNewsSource,
    FixturePageSource,
    FixtureReviewSource,
    Watchlist,
    read_json,
)
from .logging_utils import TraceLogger
from .storage import FindingsLog, SnapshotStore


@dataclass
class KnowledgeDoc:
    document_id: str
    path: Path
    title: str


@dataclass
class KnowledgeBase:
    """Allowlisted business documents the agent may read (no arbitrary file access)."""

    docs: dict[str, KnowledgeDoc] = field(default_factory=dict)

    @classmethod
    def build(cls, settings: Settings) -> KnowledgeBase:
        kb = cls()
        for path in sorted(settings.kb_dir.glob("*.md")):
            kb.add(path.stem, path)
        for path in sorted((settings.agent_dir / "workflows").glob("*.md")):
            kb.add(f"workflow:{path.stem}", path)
        for path in sorted((settings.competitors_dir / "profiles").glob("*.md")):
            kb.add(f"profile:{path.stem}", path)
        kb.add("scope", settings.agent_dir / "scope.md")
        return kb

    def add(self, doc_id: str, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        first = next((ln for ln in text.splitlines() if ln.startswith("#")), doc_id)
        self.docs[doc_id] = KnowledgeDoc(doc_id, path, first.lstrip("# ").strip())

    def read(self, doc_id: str) -> str | None:
        doc = self.docs.get(doc_id)
        return doc.path.read_text(encoding="utf-8") if doc else None

    def sections(self) -> list[tuple[str, str, str]]:
        """(doc_id, heading, body) for every Markdown section."""
        out = []
        for doc_id, doc in self.docs.items():
            heading, body = doc.title, []
            for line in doc.path.read_text(encoding="utf-8").splitlines():
                if line.startswith("#"):
                    if body:
                        out.append((doc_id, heading, "\n".join(body).strip()))
                    heading, body = line.lstrip("# ").strip(), []
                else:
                    body.append(line)
            if body:
                out.append((doc_id, heading, "\n".join(body).strip()))
        return out

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        terms = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
        if not terms:
            return []
        scored = []
        for doc_id, heading, body in self.sections():
            hay = f"{heading} {heading} {body}".lower()
            score = sum(hay.count(t) for t in terms)
            if score:
                snippet = " ".join(body.split())[:400]
                scored.append((score, {"document_id": doc_id, "section": heading, "snippet": snippet}))
        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored[:limit]]


class Services:
    """Everything the tools need, created once per run."""

    def __init__(self, settings: Settings, *, logger: TraceLogger | None = None, page_source: Any = None):
        self.settings = settings
        self.logger = logger or TraceLogger(settings.logs_dir)
        self.watchlist = Watchlist(settings.competitors_dir / "watchlist.json")
        self.snapshots = SnapshotStore(settings.data_dir / "historical-snapshots", settings.state_dir / "snapshots")
        self.findings = FindingsLog(settings.state_dir / "findings.jsonl")
        self.knowledge = KnowledgeBase.build(settings)
        self.news = FixtureNewsSource(settings.data_dir / "news" / "announcements.json")
        self.fixture_reviews = FixtureReviewSource(settings.data_dir / "reviews", self.watchlist)
        self.reviews: Any = self.fixture_reviews
        if settings.review_export_dir:
            self.reviews = ExportReviewSource(Path(settings.review_export_dir).expanduser(), self.watchlist)
        self.pages: Any = page_source or FixturePageSource(settings.root, self.snapshots, self.watchlist)
        if page_source is None and settings.data_mode == "live":
            from .integrations.public_web import LiveSourceConfig, PublicPageSource

            self.pages = PublicPageSource(
                LiveSourceConfig(settings.root / settings.live_sources_file),
                user_agent=settings.live_user_agent,
                timeout=settings.live_timeout_seconds,
                min_interval=settings.live_min_interval_seconds,
            )
        self._our_products: dict[str, Any] | None = None

    @property
    def our_products(self) -> dict[str, dict[str, Any]]:
        if self._our_products is None:
            data = read_json(self.settings.data_dir / "northstar" / "our-products.json")
            self._our_products = {p["product_id"]: p for p in data["products"]}
        return self._our_products
