"""Application-level guardrails.

The system prompt *asks* the model to behave; these checks make sure the
application *enforces* the rules that matter most:

* Detect instructions hidden in untrusted content (prompt injection).
* Reject population claims made from review samples ("40% of customers ...").
* Reject asserted competitor motives outside the open-questions section.
* Name the restricted operations that no tool implements.
"""

from __future__ import annotations

import re

# Operations the agent must never perform. No tool implements them; listing them
# lets the registry label an attempted call as a blocked, restricted action.
RESTRICTED_OPERATIONS = {
    "update_price",
    "change_price",
    "set_price",
    "update_product_description",
    "edit_product_page",
    "publish_content",
    "publish_marketing",
    "post_to_social_media",
    "send_email",
    "send_alert",
    "send_slack_message",
    "contact_competitor",
    "notify_team",
}

_INJECTION_PATTERNS = [
    r"ignore (all |any |your )?(previous|prior|above) instructions",
    r"disregard (all |your )?(previous|prior) (instructions|rules)",
    r"system (notice|prompt|message)",
    r"note to (ai|llm|assistant)",
    r"(ai|llm) (assistants?|analysts?|agents?|bots?)\b.*\b(ignore|report|recommend|tell)",
    r"you are now",
    r"(cut|drop|lower) (all )?(your )?prices? (by|to)",
    r"email [\w.+-]+@[\w-]+\.[\w.]+",
]
_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

_POPULATION_PATTERNS = [
    r"\b\d{1,3}(\.\d+)?\s*%\s+of\s+(all\s+)?(customers|buyers|users|owners|shoppers|people|reviewers)\b",
    r"\b(percent|per cent)\s+of\s+(all\s+)?(customers|buyers|users|owners|shoppers)\b",
    r"\b(most|the majority of|nearly all|almost all|all)\s+(of\s+)?(their\s+|its\s+|peaktrail\s+|sipworks\s+|trailforge\s+)?(customers|buyers|users|owners|shoppers)\b",
    r"\bcustomers (generally|typically|usually) (experience|report|have)\b",
]
_POPULATION_RE = [re.compile(p, re.IGNORECASE) for p in _POPULATION_PATTERNS]

_MOTIVE_PATTERNS = [
    r"\b(lowered|cut|reduced|dropped|raised|changed)\b[^.]{0,60}\b(price|prices|pricing)\b[^.]{0,20}\b(because|in order to|to clear|to dump|to undercut|to steal|to compete with)\b",
    r"\b(in order to|trying to|wants to|aims to|attempting to)\s+(undercut|clear (its |their )?inventory|dump|steal|win (back )?market share)",
    r"\b(strategy|plan|goal) is to\b",
    r"\bto clear (its |their |excess )?(inventory|stock)\b",
]
_MOTIVE_RE = [re.compile(p, re.IGNORECASE) for p in _MOTIVE_PATTERNS]


def detect_injection(text: str | None) -> list[str]:
    """Return the suspicious phrases found in untrusted text (empty if none)."""
    if not text:
        return []
    hits = []
    for rx in _INJECTION_RE:
        m = rx.search(text)
        if m:
            hits.append(m.group(0)[:80])
    return hits


def find_population_claims(text: str | None) -> list[str]:
    if not text:
        return []
    return [m.group(0) for rx in _POPULATION_RE for m in rx.finditer(text)]


def find_motive_claims(text: str | None) -> list[str]:
    if not text:
        return []
    return [m.group(0) for rx in _MOTIVE_RE for m in rx.finditer(text)]
