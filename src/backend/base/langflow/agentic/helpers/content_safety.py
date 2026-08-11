"""Deterministic content guardrail for the Langflow Assistant.

Security: this runs OUTSIDE the model, on both directions. Until now the only thing keeping
the assistant from emitting slurs was the model's own alignment: `sanitize_input` covers
prompt injection only, and the off-topic gate is itself an LLM call on the *user's* chosen
model. Since the assistant supports local providers (Ollama, any OpenAI-compatible base_url),
a deployment can point every one of those layers at an unaligned model and be left with
nothing. OWASP's LLM Top 10 is explicit that a system prompt is not a security control and
that guardrails belong outside the model, so this layer is pure regex: no model, no network,
works offline.

Scope, stated plainly so it is not mistaken for more than it is: this catches the CRUDE
vector -- a slur or explicit profanity in the text. It does NOT judge intent, so a request
to build something harmful that never names a slur passes it. The system prompt's content
policy is what shapes that behavior; this is the floor under it, not a replacement.

The list is deliberately small and high-confidence, word-boundary anchored so an innocent word
containing one as a substring does not trip (the Scunthorpe problem), and free of topic words
-- "hate speech" is absent on purpose, so a moderation component can still be built. It is
English/Portuguese-leaning and no hardcoded list stays complete across languages, so a
deployment needing more coverage than this floor wants a real guardrail service, not a longer
regex list.
"""

import re
from dataclasses import dataclass
from enum import Enum


class ContentCategory(str, Enum):
    SLUR = "slur"
    PROFANITY = "profanity"


REFUSAL_MESSAGE = (
    "I can't help with that. I'm the Langflow Assistant and I won't produce slurs or abusive "
    "content. I'm happy to help you build components, flows, and integrations."
)

_SEED_TERMS: dict[ContentCategory, tuple[str, ...]] = {
    ContentCategory.SLUR: (
        r"n[i1]gg(?:er|a)s?",
        r"f[a4]gg?(?:ot)?s?",
        r"k[i1]kes?",
        r"sp[i1]cs?",
        r"ch[i1]nks?",
        r"tr[a4]nn(?:y|ies)",
        r"ret[a4]rds?",
        r"viad[o0]s?",
        r"cr[i1]oul[o0]s?",
        r"macac[o0]s?\s+de\s+merda",
    ),
    ContentCategory.PROFANITY: (
        r"fuck(?:ing|ers?|ed)?",
        r"sh[i1]t(?:ty|head)?",
        r"b[i1]tch(?:es)?",
        r"c[u4]nts?",
        r"asshol[e3]s?",
        r"p[o0]rr[a4]",
        r"caralh[o0]",
        r"f[o0]d[a4]-s[e3]",
        r"put[a4]s?\s+que\s+pariu",
        r"merd[a4]",
    ),
}


@dataclass(frozen=True)
class ContentSafetyResult:
    """Outcome of a content check."""

    is_safe: bool
    category: ContentCategory | None = None
    matched_term: str | None = None

    @property
    def violation(self) -> str | None:
        if self.is_safe:
            return None
        return f"Content policy: {self.category.value if self.category else 'blocked'} detected"


def _compile(terms: tuple[str, ...]) -> list[re.Pattern[str]]:
    return [re.compile(rf"(?<!\w){t}(?!\w)", re.IGNORECASE) for t in terms]


_SEED_PATTERNS: dict[ContentCategory, list[re.Pattern[str]]] = {
    category: _compile(terms) for category, terms in _SEED_TERMS.items()
}


def check_content(text: str) -> ContentSafetyResult:
    """Scan text for slurs or explicit profanity.

    Used on the assistant's input, its answer, and the component code it generates.
    """
    if not text:
        return ContentSafetyResult(is_safe=True)

    for category, patterns in _SEED_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return ContentSafetyResult(is_safe=False, category=category, matched_term=match.group(0))

    return ContentSafetyResult(is_safe=True)
