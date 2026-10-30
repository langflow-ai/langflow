"""Deterministic text scorers: exact match, contains and fuzzy similarity."""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher
from typing import Any

from langflow.services.evaluations.scorers.types import NOT_APPLICABLE_NO_EXPECTED, ScoreResult

# SequenceMatcher is quadratic (about 40 ms for 2,000 characters of prose, 400 ms for 5,000);
# beyond this many characters the ratio is computed on a prefix.
SIMILARITY_MAX_CHARS = 2000


def normalize_text(text: str, *, case_sensitive: bool = False) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    collapsed = " ".join(normalized.split())
    return collapsed if case_sensitive else collapsed.casefold()


def _case_sensitive(config: dict[str, Any]) -> bool:
    return bool(config.get("case_sensitive", False))


def score_exact_match(actual: str, expected: str | None, config: dict[str, Any]) -> ScoreResult:
    if expected is None:
        return NOT_APPLICABLE_NO_EXPECTED
    case_sensitive = _case_sensitive(config)
    matched = normalize_text(actual, case_sensitive=case_sensitive) == normalize_text(
        expected, case_sensitive=case_sensitive
    )
    return ScoreResult(value=1.0 if matched else 0.0)


def score_contains(actual: str, expected: str | None, config: dict[str, Any]) -> ScoreResult:
    if expected is None:
        return NOT_APPLICABLE_NO_EXPECTED
    case_sensitive = _case_sensitive(config)
    needle = normalize_text(expected, case_sensitive=case_sensitive)
    if not needle:
        return ScoreResult(value=None, comment="Expected output is blank")
    haystack = normalize_text(actual, case_sensitive=case_sensitive)
    return ScoreResult(value=1.0 if needle in haystack else 0.0)


def score_similarity(actual: str, expected: str | None, config: dict[str, Any]) -> ScoreResult:
    if expected is None:
        return NOT_APPLICABLE_NO_EXPECTED
    case_sensitive = _case_sensitive(config)
    left = normalize_text(actual, case_sensitive=case_sensitive)[:SIMILARITY_MAX_CHARS]
    right = normalize_text(expected, case_sensitive=case_sensitive)[:SIMILARITY_MAX_CHARS]
    if left == right:
        return ScoreResult(value=1.0)
    ratio = SequenceMatcher(None, left, right, autojunk=False).ratio()
    return ScoreResult(value=round(ratio, 4))
