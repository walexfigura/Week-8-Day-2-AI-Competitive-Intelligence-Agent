#!/usr/bin/env python3
"""Entry point: `python run.py <command>`. Run `python run.py --help` for commands.

Works from a fresh clone without `pip install -e .` as long as the
dependencies in pyproject.toml are installed.
"""

import sys
from pathlib import Path

if sys.version_info < (3, 10):  # noqa: UP036 - friendly message for the wrong interpreter
    sys.exit(
        f"This project needs Python 3.10 or newer, but this is Python {sys.version.split()[0]} ({sys.executable}).\n"
        "Activate the virtual environment (see README Quick start) or run it directly, e.g. .venv/bin/python run.py smoke"
    )

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from competitive_intelligence.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
