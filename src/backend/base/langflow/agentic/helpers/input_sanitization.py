"""Input sanitization and prompt injection detection.

Security: Validates and sanitizes user input BEFORE it reaches the LLM.
Detects prompt injection attempts, system prompt leaking, and role hijacking.
"""

import re
from dataclasses import dataclass

MAX_INPUT_LENGTH = 2000

REFUSAL_MESSAGE = (
    "I'm sorry, but I can't process that request. "
    "I'm the Langflow Assistant and I can help you with "
    "Langflow components, flows, and technical questions. "
    "Please rephrase your question about Langflow."
)

# Prompt injection patterns: (compiled_regex, violation_description)
# Each pattern targets a specific injection technique.
# Patterns are intentionally specific to avoid false positives on
# legitimate Langflow questions (e.g., "how do I ignore errors").
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


def sanitize_input(text: str) -> SanitizationResult:
    """Validate and sanitize user input before it reaches the LLM.

    Checks for prompt injection patterns and normalizes the input.
    Returns a SanitizationResult with is_safe=False if injection is detected.
    """
    if not text:
        return SanitizationResult(is_safe=True, sanitized_input="")

    violation = _check_injection_patterns(text)
    if violation:
        return SanitizationResult(is_safe=False, sanitized_input=text, violation=violation)

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
