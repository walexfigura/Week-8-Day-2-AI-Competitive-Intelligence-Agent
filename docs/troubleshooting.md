# Troubleshooting

## Setup

| Symptom | Fix |
|---|---|
| "This project needs Python 3.10 or newer" even inside the venv | A shell alias (e.g. `alias python=/usr/bin/python3`) overrides the venv. Check `type python`; use `.venv/bin/python` or remove the alias. |
| `python: command not found` / wrong version | Use `python3` (macOS/Linux) or `py` (Windows). Check `python3 --version` is 3.10+ (tested with 3.12). |
| `ModuleNotFoundError: No module named 'pydantic'` (or `openai`, `httpx`, `dotenv`) | Activate the virtual environment, then `pip install -e ".[dev]"`. |
| `source: no such file` on Windows | Use `.venv\Scripts\activate` (PowerShell: `.venv\Scripts\Activate.ps1`). |
| PowerShell blocks the activate script | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use Command Prompt. |
| `Could not find the project root` | Run commands from the repository folder, or set `CI_PROJECT_ROOT`. |
| `pip install -e .` fails on an old pip | `python -m pip install --upgrade pip`, then retry. |

## Environment variables

| Symptom | Fix |
|---|---|
| `OPENAI_API_KEY is not set` | `cp .env.example .env` (Windows: `copy .env.example .env`) and paste your key after `OPENAI_API_KEY=`. No quotes or spaces. |
| Key set but still "not set" | The variable is empty in your shell (an exported empty value wins over `.env`). Run `unset OPENAI_API_KEY` or set it properly. |
| `CI_MAX_ITERATIONS must be an integer` | Remove quotes/units from numeric settings in `.env`. |
| `CI_DATA_MODE must be 'mock' or 'live'` | Fix the spelling, or delete the line to use mock mode. |

## OpenAI API

| Symptom | Fix |
|---|---|
| `AuthenticationError` / 401 | Key is wrong or revoked; create a new one in the OpenAI dashboard. |
| `NotFoundError` / model not found | Your account cannot use `OPENAI_MODEL`. Set a model you have access to that supports the Responses API and function calling. |
| `RateLimitError` / 429 | Wait and retry; check billing/usage limits. Evals run several scenarios — use `--case`. |
| `BadRequestError` mentioning `reasoning` | Clear `OPENAI_REASONING_EFFORT` (not all models accept it). |
| Run ends with "stopped without saving a report" | The model used its budget. Raise `CI_MAX_ITERATIONS` / `CI_MAX_TOOL_CALLS`, or try a stronger model. |
| Report saved "with validation warnings" | The model failed validation three times; the warnings are listed at the end of the report. Re-run or use a stronger model. |
| `annotation_failed` from `analyze_review_sentiment` | The annotator's JSON failed validation. Re-run, or set `CI_SENTIMENT_SOURCE=reference` to use the hand-labeled annotations. |

Every run writes a trace to `logs/trace-YYYY-MM-DD.jsonl`. Search it for the trace ID
printed at the start of the run to see each tool call, its arguments, and its result status.

## Data files

| Symptom | Fix |
|---|---|
| `failed validation: ...` for a snapshot | Check the JSON: `observed_at` needs a timezone (`...Z`), `currency` is 3 uppercase letters, prices are numbers or `null`. |
| `belongs to X, not Y` | The snapshot's `product_id` doesn't match its folder (`data/historical-snapshots/<product_id lowercased>/`). |
| A new product never appears | Add it to `competitors/watchlist.json`; tools refuse products that aren't on the watchlist. |
| Reviews `not_found` | The product needs `"review_dataset": "<file name without .json>"` in the watchlist. |
| Smoke test says HTML and JSON prices differ | You edited one but not the other; HTML fixtures and their JSON snapshots must agree. |
| Tests fail after editing fixtures | Some tests assert the teaching scenario (e.g. 8 of 20 leak reviews). Update the test if you changed the scenario on purpose. |

## Live mode

| Symptom | Fix |
|---|---|
| `No permitted live URL configured` | Add the page to `live-sources.json` with `"permission_confirmed": true`. |
| `robots.txt disallows fetching` | The site does not allow it. Do not work around it. |
| `returned 403/429` or "CAPTCHA wall" | The site is blocking automated access. Stop; use a permitted source instead. |
| Snapshot has no price | The page renders prices with JavaScript or uses different markup; adjust `page_parser.py` or use an export. |
