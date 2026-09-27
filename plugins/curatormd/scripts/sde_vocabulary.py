"""Shared, bounded SDE trigger vocabulary and inbox-safe projection helpers."""

from __future__ import annotations

import re
from typing import Any, cast


VOCABULARY: dict[str, tuple[str, ...]] = {
    "decision": (
        "decided", "decision", "tradeoff", "chose", "selected", "rejected",
        "deferred", "accepted", "design decision", "chosen", "will use",
    ),
    "change": (
        "add", "added", "addition", "remove", "removed", "subtraction",
        "implement", "implemented", "implementation", "modernize", "modernized",
        "align", "aligned", "upgrade", "upgraded", "improve", "improved",
        "refactor", "refactored", "rewrite", "rewrote", "migrate", "migrated",
        "deprecate", "deprecated", "feature", "dependency", "dependencies",
    ),
    "repair": (
        "fix", "fixed", "repair", "repaired", "resolve", "resolved", "restore",
        "restored", "corrected", "misconfiguration", "misconfigured", "regression",
        "drift", "rollback", "rolled back", "hotfix", "workaround",
    ),
    "outcome": (
        "failure", "failed", "incident", "root cause", "lesson learned", "verified",
        "regression", "breaking change", "performance", "security", "data loss",
    ),
    "risk": (
        "destructive", "deleted", "overwritten", "data loss", "security issue",
        "credential exposure", "unsafe", "breaking change",
    ),
}

_TERMS = {term for values in VOCABULARY.values() for term in values}
_PHRASES = sorted(
    ((category, phrase) for category, phrases in VOCABULARY.items() for phrase in phrases),
    key=lambda item: len(item[1]),
    reverse=True,
)


def match_sde_cues(text: str) -> dict[str, list[str]]:
    """Find known SDE trigger phrases and return the matched terms by category."""
    found: dict[str, set[str]] = {}
    lowered = text.casefold()
    for category, phrase in _PHRASES:
        pattern = r"(?<![\w])" + re.escape(phrase).replace(r"\ ", r"\s+") + r"(?![\w])"
        if re.search(pattern, lowered):
            found.setdefault(category, set()).add(phrase)
    return {category: sorted(terms) for category, terms in sorted(found.items())}


def safe_sde_cues(value: Any) -> dict[str, list[str]]:
    """Keep only the known trigger words in a review-facing payload projection."""
    if not isinstance(value, dict):
        return {}
    raw_object = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw_object):
        return {}
    value_object = cast(dict[str, Any], value)
    result: dict[str, list[str]] = {}
    for category in VOCABULARY:
        terms = value_object.get(category)
        if not isinstance(terms, list):
            continue
        terms_list = cast(list[Any], terms)
        selected = sorted({term for term in terms_list if isinstance(term, str) and term in _TERMS})
        if selected:
            result[category] = selected[:20]
    return result
