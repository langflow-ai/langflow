"""The `CLARIFICATION` phase engine (Story 1.1).

The first conversational phase: it turns a vague app idea into a clear product
spec by asking focused questions. Each turn the LLM replies with a small JSON
object — a question plus 2-4 tappable example answers — and the engine maps that
to clarification `suggestions` for the chat UI (the user can always free-text an
"Other" answer instead). When the model has heard enough to write the spec it
emits a `[CLARITY_REACHED]` token followed by a PRD summary; the engine strips
the token, clears the suggestions, and carries the summary out on
`LLMResponse.prd` — the spec the user reviews on the main page. The turn does
NOT advance the phase: the project holds in `CLARIFICATION` with a drafted PRD,
and leaving for `ARCHITECTURE` is an explicit `POST /prd/approve` the user
triggers after reviewing/editing. The `text` on that turn is a short chat handoff
line, not the PRD itself (the PRD lives on the main page, not in the chat).

Once a PRD exists, a further turn is a **revision**: the engine rewrites the
whole PRD from the user's feedback (revise mode) and returns the new spec on
`prd` again — still without advancing — so the user can iterate by chat as well
as by direct edit.

The engine is pure conversation logic: it builds the message array (Story 0.2),
calls the LLM (Story 0.1), parses the reply, and returns an `LLMResponse`. It
never touches the DB — persistence of the assistant message and PRD is the chat
endpoint's job.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.lothal.context import build_messages
from langflow.lothal.engines.parsing import extract_json_object, parse_json_object
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

# Once the PRD exists, a chat turn revises it instead of asking questions. The
# current PRD is spliced in below (concatenated, never `str.format`, so literal
# braces in the Markdown can't break the template).
REVISE_PROMPT_HEAD = """\
You are Lothal's clarification assistant, revising a draft product spec (PRD) from \
the user's feedback. Here is the current PRD:

--- CURRENT PRD ---
"""
REVISE_PROMPT_TAIL = """
--- END PRD ---

Apply the user's requested change and output the COMPLETE revised PRD in Markdown, \
keeping the sections Overview, Target Users, Core Features, and Key Flows. Output \
ONLY the PRD Markdown — no commentary, no code fences, no preamble."""

# Short chat lines that accompany a drafted / revised PRD; the PRD itself goes to
# the main page (LLMResponse.prd), not the chat, so the chat stays a handoff.
CLARITY_HANDOFF = (
    "I've drafted the spec from our conversation — review and edit it on the right, "
    "then approve it to design the architecture."
)
REVISE_HANDOFF = "I've updated the spec — review the changes on the right, then approve when you're ready."


def _coerce_suggestions(value: object) -> list[str]:
    """Keep only non-empty string suggestions, trimmed and capped at the max."""
    if not isinstance(value, list):
        return []
    cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return cleaned[:MAX_SUGGESTIONS]


def _parse_reply(raw: str) -> LLMResponse:
    """Turn one raw LLM reply into the engine's `LLMResponse`.

    Two shapes: a `[CLARITY_REACHED]` reply drafts the PRD (token stripped, no
    suggestions, the remaining text carried on `prd`; a short handoff line is the
    chat `text`; the phase does NOT advance); any other reply is a clarification
    turn (JSON question + suggestions, phase unchanged).
    """
    # Anchor the transition to the *start* of the reply. The system prompt asks
    # for the token "on its own", leading the PRD, so a clarity turn begins with
    # it. A bare `CLARITY_TOKEN in raw` substring test would misfire on any
    # clarification turn whose question or a suggestion merely mentions the token,
    # falsely transitioning out of CLARIFICATION with a half-sentence PRD.
    stripped = raw.strip()
    if stripped.startswith(CLARITY_TOKEN):
        # Strip only the leading control token, not every occurrence: a PRD body
        # may legitimately mention `[CLARITY_REACHED]`, and `replace` would
        # silently rewrite that content.
        summary = stripped.removeprefix(CLARITY_TOKEN).strip()
        # Defensive: if the model wrapped the *entire* summary as a JSON object
        # (`{"message": "<the PRD>"}`), surface the message rather than raw braces.
        # Use the strict whole-reply parse — never the greedy first-{..last-}
        # slice — so a free-form Markdown PRD that merely contains a JSON example
        # is not truncated to that embedded fragment.
        data = parse_json_object(summary)
        if data is not None and isinstance(data.get("message"), str) and data["message"].strip():
            summary = data["message"].strip()
        if not summary:
            # The token was the entire reply; keep a non-empty PRD placeholder that
            # mirrors the four-section scaffold the prompt asks for, so the drafted
            # spec is still shaped for review/editing (not just a lone Overview).
            summary = (
                "## Overview\n\n_Specification confirmed — review and fill in the details below._\n\n"
                "## Target Users\n\n_TBD_\n\n"
                "## Core Features\n\n_TBD_\n\n"
                "## Key Flows\n\n_TBD_"
            )
        # Hold in CLARIFICATION: the PRD rides on `prd` (persisted to the main
        # page), the chat gets a short handoff, and the phase advances only when
        # the user approves.
        return LLMResponse(text=CLARITY_HANDOFF, suggestions=[], prd=summary)

    data = extract_json_object(raw)
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

    async def process(
        self, history: list[Message], user_message: str, *, prd: str | None = None, **_kwargs
    ) -> LLMResponse:
        # `**_kwargs` absorbs the other refinement inputs (`current_d2`/`artifacts`,
        # see `PhaseEngine.process`); clarification uses only `prd`.
        #
        # A drafted PRD already on the project → this turn REVISES it (rewrite the
        # whole spec from the user's feedback), still without advancing. Otherwise
        # the idea isn't captured yet → keep asking questions until clarity.
        if prd and prd.strip():
            system = REVISE_PROMPT_HEAD + prd.strip() + REVISE_PROMPT_TAIL
            revised = (await call_llm(build_messages(system, history, user_message))).strip()
            # Never drop the spec on an empty model reply — keep the current PRD.
            return LLMResponse(text=REVISE_HANDOFF, suggestions=[], prd=revised or prd.strip())
        messages = build_messages(SYSTEM_PROMPT, history, user_message)
        raw = await call_llm(messages)
        return _parse_reply(raw)
