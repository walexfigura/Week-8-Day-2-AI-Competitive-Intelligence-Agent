# Production considerations

This repository is an educational project. A commercial competitive-monitoring service
would need the following — none of which is implemented here beyond the noted basics.

| Area | What a real deployment needs | In this repo |
|---|---|---|
| **Scheduled execution** | A scheduler (cron, cloud scheduler, workflow engine) with retries and alerting on failure | Manual commands; cron example in `live-integrations.md` |
| **Persistent storage** | A database for snapshots, findings, and reports with history and indexes | JSON files in `state/` and `reports/` |
| **Data-source permissions** | Legal review of each source's terms; contracts or APIs for reviews | `permission_confirmed` flag; documentation |
| **Rate limits** | Per-domain budgets, backoff, global concurrency limits | Per-host interval and timeout |
| **Source quality** | JS rendering where permitted, selector maintenance, parse-failure monitoring, multiple observations before alerting | JSON-LD-first parser; incomplete snapshots flagged |
| **Monitoring and tracing** | Central logs, dashboards, per-run cost and latency, alert on error rates | JSONL logs with trace IDs in `logs/` |
| **Human review** | An approval queue before any brief is distributed or any action taken | Agent only recommends; nothing is sent |
| **Cost management** | Token budgets per run, cheaper models for annotation, caching unchanged pages, skipping LLM when the scan finds nothing | Iteration/tool budgets; token counts printed; `CI_SENTIMENT_MODEL` |
| **Duplicate alert prevention** | Fingerprinting, suppression windows, "still true" follow-ups | `scan --record` fingerprints |
| **Authentication and secrets** | Secret manager, key rotation, least-privilege API keys | `.env` (git-ignored) |
| **Data retention** | Retention periods for snapshots, reviews, and logs; deletion process; privacy review of reviewer data | Not implemented; reviewer handles are fictional |
| **Prompt-injection protection** | Defense in depth: no write tools, content isolation, injection detection, output validation, red-team evals | All of these, in basic form; see `guardrails.py` and eval #9 |
| **Evaluation in CI** | Run deterministic tests on every change; run agent evals on a schedule and track pass rates over time | Tests and evals runnable locally |

## Accuracy claims

This project makes no claims about model accuracy. The evaluations show whether the
agent behaved correctly on specific fictional scenarios in a specific run. Measure on
your own data, repeat runs, and track results over time before relying on the agent.
