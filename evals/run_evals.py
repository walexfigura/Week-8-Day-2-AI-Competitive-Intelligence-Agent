#!/usr/bin/env python3
"""Run the evaluations (same as `python run.py eval`).

    python evals/run_evals.py                         # deterministic + agent (agent needs OPENAI_API_KEY)
    python evals/run_evals.py --deterministic-only    # no API key needed
    python evals/run_evals.py --case small_sample --repeat 3

Cases: evals/test-cases.json · Logic: src/competitive_intelligence/evaluation.py
Results are saved to evals/results/ (git-ignored).
"""

import sys
from pathlib import Path

if sys.version_info < (3, 10):  # noqa: UP036 - friendly message for the wrong interpreter
    sys.exit(
        f"This project needs Python 3.10 or newer, but this is Python {sys.version.split()[0]} ({sys.executable}).\n"
        "Activate the virtual environment (see README Quick start) or run it directly, e.g. .venv/bin/python run.py smoke"
    )

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from competitive_intelligence.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["eval", *sys.argv[1:]]))
