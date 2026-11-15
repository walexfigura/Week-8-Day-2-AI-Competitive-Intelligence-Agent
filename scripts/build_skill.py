#!/usr/bin/env python3
"""Validate the Claude Skill and build dist/competitive-intelligence-skill.zip.

Same as `python run.py build-skill`. Logic: src/competitive_intelligence/skill_builder.py
"""

import sys
from pathlib import Path

if sys.version_info < (3, 10):  # noqa: UP036 - friendly message for the wrong interpreter
    sys.exit(
        f"This project needs Python 3.10 or newer, but this is Python {sys.version.split()[0]} ({sys.executable}).\n"
        "Activate the virtual environment (see README Quick start) or run it directly, e.g. .venv/bin/python run.py smoke"
    )

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from competitive_intelligence.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["build-skill", *sys.argv[1:]]))
