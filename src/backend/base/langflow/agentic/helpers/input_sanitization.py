"""Input sanitization: prompt injection and abusive content.

Security: Validates and sanitizes user input BEFORE it reaches the LLM. Detects prompt
injection (instruction override, system prompt leaking, role hijacking) and, via
content_safety, slurs and explicit profanity.

Injection patterns are intentionally specific, to avoid firing on legitimate Langflow
questions such as "how do I ignore errors".
"""

import re
from dataclasses import dataclass

from langflow.agentic.helpers.content_safety import REFUSAL_MESSAGE as CONTENT_REFUSAL_MESSAGE
from langflow.agentic.helpers.content_safety import check_content

MAX_INPUT_LENGTH = 2000

REFUSAL_MESSAGE = (
    "I'm sorry, but I can't process that request. "
    "I'm the Langflow Assistant and I can help you with "
    "Langflow components, flows, and technical questions. "
    "Please rephrase your question about Langflow."
)

INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Instruction override attempts
    (
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        "Prompt injection: instruction override attempt",
    ),
    (
        re.compile(r"ignore\s+(all\s+)?above\s+instructions", re.IGNORECASE),
        "Prompt injection: instruction override attempt",
    ),
    (
        re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
        "Prompt injection: instruction override attempt",
    ),
    (
        re.compile(r"forget\s+(all\s+)?(previous|prior|your)\s+instructions", re.IGNORECASE),
        "Prompt injection: instruction override attempt",
    ),
    (
        re.compile(r"IMPORTANT:\s*new\s+instructions|OVERRIDE:", re.IGNORECASE),
        "Prompt injection: instruction override attempt",
    ),
    # Role hijacking attempts
    (
        re.compile(r"you\s+are\s+now\s+(a|an|my)\s+", re.IGNORECASE),
        "Prompt injection: role hijacking attempt",
    ),
    (
        re.compile(r"act\s+as\s+(a|an|if\s+you\s+were)\s+", re.IGNORECASE),
        "Prompt injection: role hijacking attempt",
    ),
    (
        re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.IGNORECASE),
        "Prompt injection: role hijacking attempt",
    ),
    # System prompt extraction attempts
    (
        re.compile(
            r"(reveal|show|print|output|repeat|display)\s+(your\s+)?(system\s+prompt|instructions|initial\s+prompt)",
            re.IGNORECASE,
        ),
        "Prompt injection: system prompt extraction attempt",
    ),
    (
        re.compile(
            r"what\s+(are|is)\s+your\s+(system\s+prompt|instructions|initial\s+prompt)",
            re.IGNORECASE,
        ),
        "Prompt injection: system prompt extraction attempt",
    ),
    # Raw prompt delimiter injection
    (
        re.compile(r"\[SYSTEM\]|\[INST\]|<<SYS>>|<\|im_start\|>system", re.IGNORECASE),
        "Prompt injection: raw prompt delimiter injection",
    ),
]


@dataclass(frozen=True)
class SanitizationResult:
    """Result of input sanitization check."""

    is_safe: bool
    sanitized_input: str
    violation: str | None = None
    refusal: str = REFUSAL_MESSAGE
    """What to tell the user. Defaults to the injection wording; content violations override it."""


def sanitize_input(text: str) -> SanitizationResult:
    """Validate and sanitize user input before it reaches the LLM.

    Checks for prompt injection and abusive content, then normalizes the input. Returns a
    SanitizationResult with is_safe=False on either. The two are separate refusals: an
    injection attempt and a slur are different problems and read differently to the user.
    """
    if not text:
        return SanitizationResult(is_safe=True, sanitized_input="")

    violation = _check_injection_patterns(text)
    if violation:
        return SanitizationResult(is_safe=False, sanitized_input=text, violation=violation)

    content = check_content(text)
    if not content.is_safe:
        return SanitizationResult(
            is_safe=False,
            sanitized_input=text,
            violation=content.violation,
            refusal=CONTENT_REFUSAL_MESSAGE,
        )

    normalized = _normalize_input(text)
    return SanitizationResult(is_safe=True, sanitized_input=normalized)


def _check_injection_patterns(text: str) -> str | None:
    """Check text against known prompt injection patterns.

    Returns the first violation description found, or None if clean.
    """
    for pattern, violation in INJECTION_PATTERNS:
        if pattern.search(text):
            return violation
    return None


def _normalize_input(text: str) -> str:
    """Normalize input by stripping whitespace and removing null bytes."""
    cleaned = text.replace("\x00", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:MAX_INPUT_LENGTH]
