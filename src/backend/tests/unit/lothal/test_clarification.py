"""Story 1.1 — the CLARIFICATION phase engine.

Per the backlog's testing philosophy these tests inject a fake `call_llm` and
assert *our* behaviour: that a structured reply becomes `text` + `suggestions`
with the phase unchanged, that a `[CLARITY_REACHED]` reply strips the token,
clears the suggestions, and drafts the PRD on `prd` while HOLDING the phase (no
auto-advance — leaving is an explicit approve), and that a further turn with a
PRD present revises it. No real LLM, no DB — the engine is pure conversation logic.
"""

import pytest
from langflow.lothal.engines import clarification
from langflow.lothal.engines.clarification import (
    CLARITY_TOKEN,
    SYSTEM_PROMPT,
    ClarificationEngine,
    _parse_reply,
)
from langflow.lothal.router import LLMResponse, get_engine
from langflow.services.database.models.lothal_project.model import Message, MessageRole, ProjectPhase


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace `call_llm` with a stub returning `_reply` and capturing its args."""
    captured = {}

    async def _call_llm(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return captured["_reply"]

    captured["_reply"] = ""
    monkeypatch.setattr(clarification, "call_llm", _call_llm)
    return captured


# --- registration ------------------------------------------------------------


def test_engine_is_registered_under_clarification():
    engine = get_engine(ProjectPhase.CLARIFICATION)
    assert isinstance(engine, ClarificationEngine)
    assert engine.phase == "CLARIFICATION"


# --- structured (clarification) reply ----------------------------------------


async def test_structured_reply_populates_text_and_suggestions_phase_stays(fake_llm):
    fake_llm["_reply"] = '{"message": "Who is this todo app for?", "suggestions": ["Just me", "My team", "Clients"]}'
    response = await ClarificationEngine().process([], "build me a todo app")

    assert isinstance(response, LLMResponse)
    assert response.text == "Who is this todo app for?"
    assert response.suggestions == ["Just me", "My team", "Clients"]
    assert response.next_phase is None


async def test_process_builds_messages_with_system_prompt_history_and_turn(fake_llm):
    fake_llm["_reply"] = '{"message": "What next?", "suggestions": ["A", "B"]}'
    history = [
        Message(project_id="p", role=MessageRole.USER, content="hi", phase=ProjectPhase.CLARIFICATION),
        Message(project_id="p", role=MessageRole.ASSISTANT, content="hello", phase=ProjectPhase.CLARIFICATION),
    ]
    await ClarificationEngine().process(history, "a budgeting app")

    messages = fake_llm["messages"]
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert messages[1] == {"role": "user", "content": "hi"}
    assert messages[2] == {"role": "assistant", "content": "hello"}
    assert messages[-1] == {"role": "user", "content": "a budgeting app"}


# --- clarity reached (transition) --------------------------------------------


async def test_clarity_reached_drafts_prd_holds_phase_and_hands_off(fake_llm):
    fake_llm["_reply"] = f"{CLARITY_TOKEN}\n# PRD\n\n## Overview\nA personal todo app."
    response = await ClarificationEngine().process([], "that's everything")

    # Holds in CLARIFICATION — leaving is now an explicit `POST /prd/approve`.
    assert response.next_phase is None
    assert response.suggestions == []
    # The PRD rides on `prd` (→ the main page), not `text` (a short chat handoff).
    assert response.prd is not None
    assert CLARITY_TOKEN not in response.prd
    assert response.prd.startswith("# PRD")
    assert "personal todo app" in response.prd
    assert response.text.strip() and "# PRD" not in response.text


async def test_clarity_token_alone_yields_non_empty_prd(fake_llm):
    fake_llm["_reply"] = CLARITY_TOKEN
    response = await ClarificationEngine().process([], "done")

    assert response.next_phase is None
    assert response.text.strip()  # the handoff line (LLMResponse forbids empty text)
    assert response.prd and response.prd.strip()  # a non-empty placeholder PRD


async def test_revise_mode_rewrites_the_prd_when_one_already_exists(fake_llm):
    # A drafted PRD already on the project → a further turn revises it (no
    # questions, no transition), carrying the new spec back on `prd`.
    fake_llm["_reply"] = "# PRD\n\n## Overview\nA personal todo app, now dark-mode first."
    response = await ClarificationEngine().process([], "make it dark-mode first", prd="# PRD\n\n## Overview\nA todo app.")

    assert response.next_phase is None
    assert response.suggestions == []
    assert response.prd is not None
    assert "dark-mode first" in response.prd


async def test_revise_mode_keeps_existing_prd_on_empty_reply(fake_llm):
    # Never blank the spec if the model returns nothing on a revise turn.
    current = "# PRD\n\n## Overview\nA todo app."
    fake_llm["_reply"] = "   "
    response = await ClarificationEngine().process([], "tweak it", prd=current)
    assert response.prd == current


# --- parsing robustness (unit, no LLM) ---------------------------------------


def test_parse_reply_strips_markdown_fences():
    raw = '```json\n{"message": "Pick a data store", "suggestions": ["SQLite", "Postgres"]}\n```'
    response = _parse_reply(raw)
    assert response.text == "Pick a data store"
    assert response.suggestions == ["SQLite", "Postgres"]
    assert response.next_phase is None


def test_parse_reply_caps_suggestions_at_four_and_drops_non_strings():
    raw = '{"message": "Pick features", "suggestions": ["a", "b", "c", "d", "e", 7, "  "]}'
    response = _parse_reply(raw)
    assert response.suggestions == ["a", "b", "c", "d"]


def test_parse_reply_falls_back_to_prose_when_not_json():
    response = _parse_reply("Tell me more about your idea.")
    assert response.text == "Tell me more about your idea."
    assert response.suggestions == []
    assert response.next_phase is None


def test_parse_reply_handles_whitespace_only_reply():
    # call_llm normally guarantees non-empty, but _parse_reply must stay total:
    # an all-whitespace reply still yields a storable (non-empty) message.
    response = _parse_reply("   \n  ")
    assert response.text.strip()
    assert response.suggestions == []
    assert response.next_phase is None


def test_parse_reply_handles_clarity_token_wrapped_in_json():
    raw = f'{CLARITY_TOKEN} {{"message": "Spec: a todo app for teams."}}'
    response = _parse_reply(raw)
    assert response.next_phase is None
    assert response.prd == "Spec: a todo app for teams."
    assert response.suggestions == []


def test_parse_reply_keeps_full_prd_when_it_contains_an_embedded_json_object():
    # Regression: a clarity PRD that legitimately contains a `{"message": ...}`
    # example (common for chat/notification/webhook apps) must be stored whole,
    # not greedily sliced down to that embedded fragment.
    prd = (
        "# PRD\n\n## Overview\nA team chat app.\n\n## Key Flows\n"
        'Clients send messages as JSON like {"message": "hello team"} over the socket.'
    )
    response = _parse_reply(f"{CLARITY_TOKEN}\n{prd}")
    assert response.next_phase is None
    assert response.prd == prd  # whole spec preserved, not "hello team"
    assert "## Overview" in response.prd


def test_parse_reply_strips_only_the_leading_clarity_token():
    # Only the control prefix is removed; an occurrence inside the PRD body is
    # preserved rather than silently rewritten by a blanket replace.
    body = "# PRD\n\n## Overview\nThe app shows a [CLARITY_REACHED] banner when a spec is locked."
    response = _parse_reply(f"{CLARITY_TOKEN}\n{body}")
    assert response.next_phase is None
    assert response.prd == body
    assert response.prd.count(CLARITY_TOKEN) == 1  # the body mention survived


def test_parse_reply_does_not_transition_when_token_only_mentioned_mid_reply():
    # Regression: the control token appearing inside a clarification question (not
    # leading the reply) must NOT transition — it stays a clarification turn with
    # its chips intact and its message untouched.
    raw = (
        f'{{"message": "When ready I will emit {CLARITY_TOKEN}. Who is this app for?", '
        '"suggestions": ["Just me", "My team"]}'
    )
    response = _parse_reply(raw)
    assert response.next_phase is None  # stayed in CLARIFICATION
    assert response.suggestions == ["Just me", "My team"]
    assert "Who is this app for?" in response.text


def test_system_prompt_documents_the_clarity_token():
    # The transition only fires if the model knows to emit the token.
    assert CLARITY_TOKEN in SYSTEM_PROMPT
