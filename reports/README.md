# Reports

Generated briefs are saved here as a Markdown file (for people) and a JSON file (for
programs) with the same base name, e.g. `20261114-090000-peaktrail_investigation.md`.
Generated files are git-ignored.

## `examples/`

- `offline-briefing-example.md` / `.json` — produced by running
  `python run.py briefing --offline` on the fictional data. This is the **rule-based
  offline mode (no LLM)**: wording comes from templates and priorities are the rubric
  baseline. It was **not** written by a language model. Run `python run.py demo` or
  `python run.py briefing` with an API key to generate an LLM agent report in the same format.

All content is fictional sample data.
