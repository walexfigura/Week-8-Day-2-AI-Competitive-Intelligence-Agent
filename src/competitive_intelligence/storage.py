"""Simple local JSON storage for snapshots, findings, and reports.

Why JSON files instead of a database? They are easy to read, diff in Git, and
edit by hand for the exercises. Two locations hold snapshots:

* `data/historical-snapshots/<product>/` — the committed fictional fixtures.
* `state/snapshots/<product>/`          — new captures (e.g. live fetches), git-ignored.

All file names are derived from validated IDs and checked to stay inside their
base directory, so a malicious or malformed ID cannot write elsewhere.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import ProductSnapshot

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


class StorageError(RuntimeError):
    pass


class SnapshotValidationError(StorageError):
    """A snapshot file exists but is malformed."""


def safe_child(base: Path, *parts: str) -> Path:
    """Join `parts` under `base`, refusing anything that escapes `base`."""
    for part in parts:
        if not part or part in {".", ".."} or "/" in part or "\\" in part:
            raise StorageError(f"Unsafe path component: {part!r}")
    base_resolved = base.resolve()
    target = base_resolved.joinpath(*parts).resolve()
    if base_resolved != target and base_resolved not in target.parents:
        raise StorageError(f"Path escapes {base}: {target}")
    return target


def validate_id(value: str, kind: str = "id") -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise StorageError(f"Invalid {kind}: {value!r}")
    return value


class SnapshotStore:
    def __init__(self, fixture_dir: Path, state_dir: Path):
        self.fixture_dir = fixture_dir
        self.state_dir = state_dir

    def _dirs(self, product_id: str) -> list[Path]:
        folder = validate_id(product_id, "product_id").lower()
        return [safe_child(self.fixture_dir, folder), safe_child(self.state_dir, folder)]

    def _load_file(self, path: Path) -> ProductSnapshot:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SnapshotValidationError(f"{path.name} is not valid JSON: {exc}") from exc
        try:
            return ProductSnapshot.model_validate(raw)
        except ValidationError as exc:
            raise SnapshotValidationError(f"{path.name} failed validation: {exc.errors()[0]['msg']}") from exc

    def list(self, product_id: str) -> list[ProductSnapshot]:
        """All valid snapshots for a product, oldest first. Malformed files raise."""
        snapshots: dict[str, ProductSnapshot] = {}
        for folder in self._dirs(product_id):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                snap = self._load_file(path)
                if snap.product_id != product_id:
                    raise SnapshotValidationError(f"{path.name} belongs to {snap.product_id}, not {product_id}")
                snapshots[snap.snapshot_id] = snap
        return sorted(snapshots.values(), key=lambda s: s.observed_datetime)

    def get(self, product_id: str, snapshot_id: str) -> ProductSnapshot | None:
        validate_id(snapshot_id, "snapshot_id")
        for folder in self._dirs(product_id):
            path = folder / f"{snapshot_id}.json"
            if path.is_file():
                return self._load_file(path)
        return None

    def save(self, snapshot: ProductSnapshot) -> Path:
        """Persist a new capture to `state/snapshots/` (never overwrites fixtures)."""
        folder = safe_child(self.state_dir, validate_id(snapshot.product_id).lower())
        folder.mkdir(parents=True, exist_ok=True)
        path = safe_child(folder, f"{validate_id(snapshot.snapshot_id)}.json")
        if path.exists():
            raise StorageError(f"Snapshot {snapshot.snapshot_id} already exists")
        path.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


class FindingsLog:
    """Append-only JSONL log of reported findings, used to avoid duplicate alerts."""

    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def fingerprint(*parts: Any) -> str:
        return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]

    def seen(self) -> set[str]:
        if not self.path.exists():
            return set()
        seen = set()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    seen.add(json.loads(line)["fingerprint"])
                except (json.JSONDecodeError, KeyError):
                    continue
        return seen

    def record(self, fingerprint: str, summary: str, run_id: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "fingerprint": fingerprint,
            "summary": summary,
            "run_id": run_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug or "report")[:max_len].strip("-")


def write_report_files(reports_dir: Path, base_name: str, markdown: str, data: dict[str, Any]) -> tuple[Path, Path]:
    """Write `<base>.md` and `<base>.json` inside the reports directory only."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    base = slugify(base_name, 80)
    md_path = safe_child(reports_dir, f"{base}.md")
    json_path = safe_child(reports_dir, f"{base}.json")
    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return md_path, json_path
