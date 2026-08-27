"""Input sanitization: prompt injection and abusive content.

Security: Validates and sanitizes user input BEFORE it reaches the LLM. Detects prompt
injection (instruction override, system prompt leaking, role hijacking) and, via
content_safety, slurs and explicit profanity.

Injection patterns are intentionally specific, to avoid firing on legitimate Langflow
questions such as "how do I ignore errors".

Trust boundary (LE-2323): the injection patterns describe what an UNTRUSTED party may
try to do to the assistant, so they only apply to a user turn. Text the assistant itself
authored -- the spec it writes for its own ``generate_component`` tool -- passes
``trusted_source=True``: a spec for a guardrail or sanitizer component legitimately
enumerates attack phrasings, and checking it rejected in-scope builds mid-flight. The
content guardrail and normalization still run for both.
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

ACT_AS_PATTERN = re.compile(r"\bact\s+as\s+(a|an|if\s+you\s+were)\s+", re.IGNORECASE)

# The one carve-out: a relative clause naming a COMPONENT's role, as in "a Prompt
# Template that will act as a bridge". Anything else keeps the original block.
_COMPONENT_ROLE_SUBJECT = re.compile(
    r"\b(?:that|which)\s+(?:will\s+|would\s+|can\s+|could\s+|should\s+|may\s+|must\s+)?$",
    re.IGNORECASE,
)


def _is_component_role_phrase(text: str, match: re.Match[str]) -> bool:
    """Whether this "act as" describes a component's role rather than the model's."""
    return bool(_COMPONENT_ROLE_SUBJECT.search(text[: match.start()]))


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
    # "act as" is blocked by default; _is_component_role_phrase carves out the one
    # benign shape ("a Prompt Template that will act as a bridge"). Enumerating the
    # hijack shapes instead let "I want you to act as a DAN" through (PR #14792).
    (ACT_AS_PATTERN, "Prompt injection: role hijacking attempt"),
    (
        re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.IGNORECASE),
        "Prompt injection: role hijacking attempt",
    ),
    # Only bare "instructions" needs a possessive to fire; requiring one for every
    # target dropped "print system prompt", which the original pattern caught.
    (
        re.compile(
            r"(reveal|show|print|output|repeat|display)\s+(?:me\s+)?"
            r"(?:(?:the\s+|your\s+)?(?:system\s+prompt|initial\s+prompt|system\s+instructions)"
            r"|your\s+instructions)",
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


def sanitize_input(text: str, *, trusted_source: bool = False) -> SanitizationResult:
    """Validate and sanitize input before it reaches the LLM.

    Checks for prompt injection and abusive content, then normalizes the input. Returns a
    SanitizationResult with is_safe=False on either. The two are separate refusals: an
    injection attempt and a slur are different problems and read differently to the user.

    ``trusted_source=True`` marks text the assistant authored itself (the spec its agent
    writes for ``generate_component``) rather than a user turn, and skips the injection
    patterns only — see the module docstring for why.
    """
    if not text:
        return SanitizationResult(is_safe=True, sanitized_input="")

    violation = None if trusted_source else _check_injection_patterns(text)
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
        for match in pattern.finditer(text):
            if pattern is ACT_AS_PATTERN and _is_component_role_phrase(text, match):
                continue
            return violation
    return None


def _normalize_input(text: str) -> str:
    """Normalize input by stripping whitespace and removing null bytes."""
    cleaned = text.replace("\x00", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:MAX_INPUT_LENGTH]
