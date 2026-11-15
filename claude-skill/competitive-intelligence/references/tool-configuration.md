# Tool configuration (Mode B)

Writing a URL or a tool name in a Markdown file does **not** create a working connector.
A capability exists only if it is actually available in the current Claude conversation.

## Capabilities that help
| Capability | Used for | Required? |
|---|---|---|
| File uploads / project knowledge | Your context, page captures, review exports | Recommended |
| Code execution | Exact arithmetic, duplicate detection (`scripts/ci_calc.py`) | Recommended |
| Web search | Finding public product pages and announcements | Optional |
| Web fetch / browsing | Reading a specific public product page | Optional |
| Authorized data connectors (e.g. a drive or database you connected) | Stored snapshots, approved review exports | Optional |

## How to tell what is available
Look at the tools listed for this conversation. If unsure, say which capability you
would use and ask the user to confirm it is enabled. Never claim to have browsed,
searched, or queried a system unless you actually called the tool.

## When to use them
- Use web search/fetch only for **public** pages the user asked about; record the URL and
  the time you read it as the observation timestamp.
- Prefer schema.org Product structured data on a page for price, currency, and
  availability; note when you could only read visible text.
- Respect site terms and robots rules; do not bypass logins, paywalls, CAPTCHAs, or
  anti-bot protections. If a page is blocked, report that.
- Reviews: there is no universal public review API. Use exports or APIs the user is
  authorized to use, or reviews the user supplies.

## When a tool is unavailable or fails
Say so, continue with the evidence you have, and list the gap under "Information
requiring verification". Do not substitute remembered or invented data.

## Actions that need explicit human approval
Anything that leaves the conversation or changes a system: sending messages or alerts,
posting, editing listings or prices, writing to shared documents or databases. Propose
the action, show exactly what would happen, and wait for a clear yes. Price changes,
publishing, and contacting competitors should be recommended to a human, not performed.

## Continuous monitoring
A Skill runs when invoked; it does not schedule itself. For recurring monitoring, use the
companion Python project (scheduled scans with stored snapshots) or a scheduler the user
controls, and bring the stored observations into the conversation.
