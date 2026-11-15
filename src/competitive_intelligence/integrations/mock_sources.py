"""Mock data sources: read the fictional fixtures that ship with the repository.

Each source has a small interface (methods below). A live or user-supplied
source can replace any of them without changing the tools or the agent:

* `PageSource.fetch(competitor_id, product_id, variant_id)` → parsed page dict
* `ReviewSource.get(product_id)` → (meta, list[Review])
* `NewsSource.get(competitor_id)` → list of announcement dicts
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Protocol

from ..models import Review
from ..storage import SnapshotStore, safe_child, validate_id
from .page_parser import parse_product_page


class SourceUnavailableError(RuntimeError):
    """The source could not be reached (network down, file missing, etc.)."""


class MalformedSourceError(RuntimeError):
    """The source responded, but the data could not be parsed or validated."""


class PageSource(Protocol):
    name: str

    def fetch(self, competitor_id: str, product_id: str, variant_id: str | None) -> dict[str, Any]: ...


class ReviewSource(Protocol):
    name: str

    def get(self, product_id: str) -> tuple[dict[str, Any], list[Review]]: ...


def read_json(path: Path) -> Any:
    if not path.is_file():
        raise SourceUnavailableError(f"File not found: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MalformedSourceError(f"{path.name} is not valid JSON: {exc}") from exc


class Watchlist:
    def __init__(self, path: Path):
        self.path = path
        self.data = read_json(path)
        self.competitors: dict[str, dict[str, Any]] = {c["competitor_id"]: c for c in self.data["competitors"]}

    def product(self, product_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for comp in self.competitors.values():
            for prod in comp["products"]:
                if prod["product_id"] == product_id:
                    return comp, prod
        return None

    def variant(self, variant_id: str | None) -> dict[str, Any] | None:
        if not variant_id:
            return None
        for comp in self.competitors.values():
            for prod in comp["products"]:
                for var in prod["tracked_variants"]:
                    if var["variant_id"] == variant_id:
                        return var
        return None

    def products(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        return [(c, p) for c in self.competitors.values() for p in c["products"]]


class FixturePageSource:
    """Serves the most recent local HTML fixture for a product, parsed like a live page."""

    name = "mock_fixture"

    def __init__(self, root: Path, snapshots: SnapshotStore, watchlist: Watchlist):
        self.root = root
        self.snapshots = snapshots
        self.watchlist = watchlist

    def fetch(self, competitor_id: str, product_id: str, variant_id: str | None) -> dict[str, Any]:
        found = self.watchlist.product(product_id)
        if not found or found[0]["competitor_id"] != competitor_id:
            raise LookupError(f"{product_id} is not a watched product of {competitor_id}")
        with_fixture = [s for s in self.snapshots.list(product_id) if s.fixture]
        if not with_fixture:
            raise SourceUnavailableError(f"No page fixture available for {product_id}")
        latest = with_fixture[-1]
        path = safe_child(self.root, *latest.fixture.split("/"))
        if not path.is_file():
            raise SourceUnavailableError(f"Fixture file missing: {latest.fixture}")
        parsed = parse_product_page(path.read_text(encoding="utf-8"), variant_id)
        parsed.update(
            {
                "competitor_id": competitor_id,
                "product_id": product_id,
                "observed_at": latest.observed_at,
                "source_id": latest.source_id,
                "source_url": latest.source_url,
                "fixture": latest.fixture,
                "page_snapshot_id": latest.snapshot_id,
                "capture_method": self.name,
            }
        )
        return parsed


class FixtureReviewSource:
    """Reads `data/reviews/<dataset>.json` (fictional review samples)."""

    name = "mock_fixture"

    def __init__(self, reviews_dir: Path, watchlist: Watchlist):
        self.reviews_dir = reviews_dir
        self.watchlist = watchlist

    def dataset_id(self, product_id: str) -> str | None:
        found = self.watchlist.product(product_id)
        return found[1].get("review_dataset") if found else None

    def get(self, product_id: str) -> tuple[dict[str, Any], list[Review]]:
        dataset = self.dataset_id(product_id)
        if not dataset:
            raise LookupError(f"No review dataset is configured for {product_id}")
        raw = read_json(safe_child(self.reviews_dir, f"{validate_id(dataset)}.json"))
        try:
            reviews = [Review.model_validate(r) for r in raw["reviews"]]
            meta = raw["_meta"]
        except Exception as exc:  # noqa: BLE001 - surface as malformed data
            raise MalformedSourceError(f"Review dataset {dataset} failed validation: {exc}") from exc
        return meta, [r for r in reviews if r.product_id == product_id]

    def reference_annotations(self, product_id: str) -> list[dict[str, Any]]:
        dataset = self.dataset_id(product_id)
        if not dataset:
            raise LookupError(f"No review dataset is configured for {product_id}")
        raw = read_json(safe_child(self.reviews_dir, "reference-annotations", f"{validate_id(dataset)}.json"))
        return raw["annotations"]


class ExportReviewSource:
    """Reads reviews you are permitted to use from an export folder (JSON or CSV).

    Expected file: `<CI_REVIEW_EXPORT_DIR>/<product_id>.json` with the same shape
    as the fixtures, or `<product_id>.csv` with columns
    review_id,review_date,rating,title,text,source_ref (others optional).
    """

    name = "user_export"

    def __init__(self, export_dir: Path, watchlist: Watchlist):
        self.export_dir = export_dir
        self.watchlist = watchlist

    def get(self, product_id: str) -> tuple[dict[str, Any], list[Review]]:
        validate_id(product_id)
        found = self.watchlist.product(product_id)
        competitor_id = found[0]["competitor_id"] if found else "unknown"
        json_path = safe_child(self.export_dir, f"{product_id}.json")
        csv_path = safe_child(self.export_dir, f"{product_id}.csv")
        if json_path.is_file():
            raw = read_json(json_path)
            try:
                reviews = [Review.model_validate(r) for r in raw["reviews"]]
            except Exception as exc:  # noqa: BLE001
                raise MalformedSourceError(f"{json_path.name} failed validation: {exc}") from exc
            return raw.get("_meta", {"collection_method": self.name}), reviews
        if csv_path.is_file():
            reviews = []
            with csv_path.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    try:
                        reviews.append(
                            Review(
                                review_id=row["review_id"],
                                competitor_id=row.get("competitor_id") or competitor_id,
                                product_id=product_id,
                                variant_id=row.get("variant_id") or None,
                                review_date=row["review_date"],
                                rating=int(row["rating"]) if row.get("rating") else None,
                                title=row.get("title") or None,
                                text=row["text"],
                                reviewer=row.get("reviewer") or None,
                                source_id=row.get("source_id") or f"src-export-{product_id.lower()}",
                                source_ref=row.get("source_ref") or csv_path.name,
                            )
                        )
                    except Exception as exc:  # noqa: BLE001
                        raise MalformedSourceError(f"{csv_path.name} row {row.get('review_id')} invalid: {exc}") from exc
            meta = {"collection_method": self.name, "sample_description": f"User-supplied export {csv_path.name}"}
            return meta, reviews
        raise SourceUnavailableError(f"No export file for {product_id} in {self.export_dir}")


class FixtureNewsSource:
    name = "mock_fixture"

    def __init__(self, path: Path):
        self.path = path

    def get(self, competitor_id: str) -> list[dict[str, Any]]:
        data = read_json(self.path)
        return [item for item in data["items"] if item["competitor_id"] == competitor_id]
