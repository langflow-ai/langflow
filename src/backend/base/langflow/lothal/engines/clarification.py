"""The `CLARIFICATION` phase engine (Story 1.1).

The first conversational phase: it turns a vague app idea into a clear product
spec by asking focused questions. Each turn the LLM replies with a small JSON
object — a question plus 2-4 tappable example answers — and the engine maps that
to clarification `suggestions` for the chat UI (the user can always free-text an
"Other" answer instead). When the model has heard enough to write the spec it
emits a `[CLARITY_REACHED]` token followed by a PRD summary; the engine strips
the token, clears the suggestions, and transitions the project to
`DIAGRAM_GENERATION`. The returned `text` on that turn is the PRD summary the
chat endpoint stores (Story 1.2).

The engine is pure conversation logic: it builds the message array (Story 0.2),
calls the LLM (Story 0.1), parses the reply, and returns an `LLMResponse`. It
never touches the DB — persistence of the assistant message and PRD is the chat
endpoint's job.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from langflow.lothal.context import build_messages
from langflow.lothal.llm import call_llm
from langflow.lothal.router import LLMResponse, PhaseEngine, register_engine
from langflow.services.database.models.lothal_project.model import ProjectPhase

if TYPE_CHECKING:
    from langflow.services.database.models.lothal_project.model import Message

# The model emits this token (anywhere in its reply) once it has enough to write
# the PRD. Detecting it is what triggers the transition out of CLARIFICATION.
CLARITY_TOKEN = "[CLARITY_REACHED]"  # noqa: S105  -- a control token, not a secret

# A clarification turn offers 2-4 tappable answers; we never show more than this
# even if the model over-produces (the UI's free-text box covers everything else).
MAX_SUGGESTIONS = 4

SYSTEM_PROMPT = f"""\
You are Lothal's clarification assistant. Your job is to help a user turn a vague \
app idea into a clear product specification by asking focused questions — one \
topic at a time. Be concise and friendly; never write code or diagrams in this \
phase.

While you still need information, reply with a SINGLE JSON object and nothing \
else, in exactly this shape:

{{"message": "<your question>", "suggestions": ["<option>", "<option>", "<option>"]}}

Rules for that JSON:
- "message" is one focused question that fills the most important remaining gap \
(purpose, target users, core features, key data, or main user flows).
- "suggestions" is a list of 2 to 4 SHORT example answers (a few words each) the \
user can tap. They are examples only — the user may type their own answer — so \
do not try to be exhaustive.
- Emit raw JSON only: no markdown fences, no commentary before or after.

Once you have enough to write a useful product spec (you understand the core \
purpose, who it is for, and the key features and flows), STOP asking. On that \
final turn, do NOT use the JSON shape. Instead reply with the literal token \
{CLARITY_TOKEN} on its own, followed by a concise PRD summary in Markdown with \
these sections: Overview, Target Users, Core Features, Key Flows. Do not include \
any suggestions on that turn."""


def _strip_code_fences(text: str) -> str:
    """Drop a surrounding ```...``` markdown fence if the model added one."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9]*\s*\n", "", stripped)
        stripped = re.sub(r"\n```\s*$", "", stripped)
    return stripped.strip()


def _extract_json_object(text: str) -> dict | None:
    """Best-effort parse of a single JSON object from the model's reply.

    Tolerates a surrounding markdown fence and leading/trailing prose by falling
    back to the first balanced-looking ``{...}`` slice. Returns ``None`` when no
    JSON object can be recovered.
    """
    candidate = _strip_code_fences(text)
    try:
        data = json.loads(candidate)
    except (ValueError, TypeError):
        start, end = candidate.find("{"), candidate.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(candidate[start : end + 1])
        except (ValueError, TypeError):
            return None
    return data if isinstance(data, dict) else None


def _coerce_suggestions(value: object) -> list[str]:
    """Keep only non-empty string suggestions, trimmed and capped at the max."""
    if not isinstance(value, list):
        return []
    cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return cleaned[:MAX_SUGGESTIONS]


def _parse_reply(raw: str) -> LLMResponse:
    """Turn one raw LLM reply into the engine's `LLMResponse`.

    Two shapes: a `[CLARITY_REACHED]` reply transitions to DIAGRAM_GENERATION
    (token stripped, no suggestions, the remaining text is the PRD summary); any
    other reply is a clarification turn (JSON question + suggestions, phase
    unchanged).
    """
    if CLARITY_TOKEN in raw:
        summary = raw.replace(CLARITY_TOKEN, "").strip()
        # Defensive: if the model still wrapped the summary as JSON, surface the
        # message rather than raw braces.
        data = _extract_json_object(summary)
        if data is not None and isinstance(data.get("message"), str) and data["message"].strip():
            summary = data["message"].strip()
        if not summary:
            # The token was the entire reply; keep a non-empty PRD placeholder so
            # the transition still carries a storable assistant message.
            summary = "Specification confirmed. Generating the diagram next."
        return LLMResponse(text=summary, suggestions=[], next_phase=ProjectPhase.DIAGRAM_GENERATION)

    data = _extract_json_object(raw)
    if data is not None and isinstance(data.get("message"), str) and data["message"].strip():
        return LLMResponse(text=data["message"].strip(), suggestions=_coerce_suggestions(data.get("suggestions")))

    # The model ignored the JSON contract — show its prose verbatim with no chips
    # rather than failing the turn. Guard the all-whitespace case so a degenerate
    # reply still yields a storable assistant message instead of a ValueError.
    text = raw.strip() or "Could you tell me a bit more about what you want to build?"
    return LLMResponse(text=text, suggestions=[])


@register_engine
class ClarificationEngine(PhaseEngine):
    """Asks focused questions until the idea is clear, then hands off a PRD."""

    phase = ProjectPhase.CLARIFICATION

    async def process(self, history: list[Message], user_message: str) -> LLMResponse:
        messages = build_messages(SYSTEM_PROMPT, history, user_message)
        raw = await call_llm(messages)
        return _parse_reply(raw)
