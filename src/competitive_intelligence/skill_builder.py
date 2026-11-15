"""Validate and package the Claude Skill in claude-skill/competitive-intelligence/.

Checks follow the published Agent Skills format: SKILL.md at the top of the
skill folder, YAML frontmatter with `name` (≤64 chars, lowercase letters,
numbers, hyphens; must not contain "anthropic" or "claude") and `description`
(non-empty, ≤1024 chars, no XML tags). It also checks that every file SKILL.md
links to exists, so the ZIP is self-contained.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

SKILL_DIR_NAME = "competitive-intelligence"
ZIP_NAME = "competitive-intelligence-skill.zip"
MAX_UNCOMPRESSED = 30 * 1024 * 1024
FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)  # fixed so rebuilding unchanged files gives an identical ZIP


class SkillValidationError(ValueError):
    pass


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise SkillValidationError("SKILL.md must start with '---' YAML frontmatter")
    end = text.find("\n---", 4)
    if end == -1:
        raise SkillValidationError("SKILL.md frontmatter is not closed with '---'")
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise SkillValidationError(f"Unsupported frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def validate_skill(skill_dir: Path) -> dict[str, object]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise SkillValidationError(f"Missing {skill_md}")
    text = skill_md.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    name, desc = fm.get("name", ""), fm.get("description", "")
    if not re.fullmatch(r"[a-z0-9-]{1,64}", name):
        raise SkillValidationError("name must be 1-64 lowercase letters, numbers, or hyphens")
    if "anthropic" in name or "claude" in name:
        raise SkillValidationError("name must not contain 'anthropic' or 'claude'")
    if not desc or len(desc) > 1024:
        raise SkillValidationError("description must be 1-1024 characters")
    if re.search(r"<[^>]+>", name + desc):
        raise SkillValidationError("name and description must not contain XML tags")
    body_lines = text.count("\n")
    if body_lines > 500:
        raise SkillValidationError(f"SKILL.md is {body_lines} lines; keep it under 500 and move detail to references/")
    links = set(re.findall(r"\]\(((?:references|sample-data|scripts)/[^)#\s]+)\)", text))
    missing = sorted(link for link in links if not (skill_dir / link).is_file())
    if missing:
        raise SkillValidationError(f"SKILL.md links to missing files: {missing}")
    files = [p for p in skill_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"]
    size = sum(p.stat().st_size for p in files)
    if size > MAX_UNCOMPRESSED:
        raise SkillValidationError("Skill is larger than 30 MB uncompressed")
    return {"name": name, "description_chars": len(desc), "files": len(files), "linked_files": len(links), "bytes": size}


def skill_files(skill_dir: Path) -> list[Path]:
    return sorted(
        p for p in skill_dir.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"
    )


def build_skill_zip(root: Path, output_dir: Path | None = None) -> tuple[Path, dict[str, object]]:
    skill_dir = root / "claude-skill" / SKILL_DIR_NAME
    info = validate_skill(skill_dir)
    output_dir = output_dir or root / "claude-skill"
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in skill_files(skill_dir):
            arcname = (Path(SKILL_DIR_NAME) / path.relative_to(skill_dir)).as_posix()
            entry = zipfile.ZipInfo(arcname, date_time=FIXED_TIMESTAMP)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            zf.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        if f"{SKILL_DIR_NAME}/SKILL.md" not in names:
            raise SkillValidationError("ZIP does not contain SKILL.md at the top of the skill folder")
        if zf.testzip() is not None:
            raise SkillValidationError("ZIP integrity check failed")
    info["zip_entries"] = len(names)
    return zip_path, info
