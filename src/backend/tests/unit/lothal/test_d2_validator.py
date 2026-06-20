"""The D2 coherence validator (Epic D.10).

Following the testing philosophy, these tests inject a fake `call_llm` on the
validator module and assert *our* behaviour: a `WARNING:` reply becomes a
user-facing warning, anything else (including `VALID`) is `None`, an absent PRD
or diagram short-circuits without a model call, and any LLM fault is swallowed
(the validator is advisory and must never fail the turn). No real LLM.
"""

import pytest
from langflow.lothal.engines import d2_validator
from langflow.lothal.engines.d2_validator import validate_d2_against_prd
from langflow.lothal.llm import LLMConfigError, LLMConnectionError

PRD = "## Overview\nA todo app.\n## Features\nCreate and complete tasks."
D2 = "shape: sequence_diagram\nuser: User\napi: API\nuser -> api: add task"


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace the validator's own `call_llm` with a stub returning a queued reply."""
    state = {"reply": "VALID", "calls": []}

    async def _call_llm(messages, **_kwargs):
        state["calls"].append(messages)
        reply = state["reply"]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(d2_validator, "call_llm", _call_llm)
    return state


async def test_valid_reply_returns_no_warning(fake_llm):
    fake_llm["reply"] = "VALID"
    assert await validate_d2_against_prd(PRD, D2) is None


async def test_warning_reply_returns_user_facing_warning(fake_llm):
    fake_llm["reply"] = "WARNING: the diagram is missing the auth step the spec requires"
    warning = await validate_d2_against_prd(PRD, D2)
    assert warning is not None
    assert "missing the auth step the spec requires" in warning


async def test_warning_without_colon_is_still_recognised(fake_llm):
    fake_llm["reply"] = "WARNING the database is never written to"
    warning = await validate_d2_against_prd(PRD, D2)
    assert warning is not None
    assert "the database is never written to" in warning


async def test_warning_keyword_is_case_insensitive_and_uses_first_line(fake_llm):
    fake_llm["reply"] = "warning: contradicts the spec\n(some extra chatter)"
    warning = await validate_d2_against_prd(PRD, D2)
    assert warning is not None
    assert "contradicts the spec" in warning
    assert "chatter" not in warning  # only the first line is used


async def test_chatty_non_warning_reply_is_treated_as_valid(fake_llm):
    fake_llm["reply"] = "The diagram looks consistent with the spec to me."
    assert await validate_d2_against_prd(PRD, D2) is None


@pytest.mark.parametrize("reply", ["Warnings: none", "Warning-free", "Warningless", "Warnings were not found"])
async def test_word_starting_with_warning_does_not_misfire(fake_llm, reply):
    """A VALID-intent reply that merely starts with the letters 'warning' is not a warning."""
    fake_llm["reply"] = reply
    assert await validate_d2_against_prd(PRD, D2) is None


async def test_empty_reply_is_no_warning(fake_llm):
    fake_llm["reply"] = "   \n  "
    assert await validate_d2_against_prd(PRD, D2) is None


async def test_blank_prd_skips_the_model_call(fake_llm):
    assert await validate_d2_against_prd(None, D2) is None
    assert await validate_d2_against_prd("   ", D2) is None
    assert fake_llm["calls"] == []  # no PRD → never calls the model


async def test_blank_d2_skips_the_model_call(fake_llm):
    assert await validate_d2_against_prd(PRD, "") is None
    assert fake_llm["calls"] == []


async def test_validator_passes_prd_and_d2_to_the_model(fake_llm):
    await validate_d2_against_prd(PRD, D2)
    assert fake_llm["calls"]
    turn = fake_llm["calls"][0][-1]["content"]
    assert "A todo app." in turn
    assert "user -> api: add task" in turn


@pytest.mark.parametrize(
    "exc",
    [LLMConnectionError("down"), LLMConfigError("not configured"), RuntimeError("unexpected"), ValueError("boom")],
)
async def test_any_fault_is_swallowed(fake_llm, exc):
    """Any fault is swallowed, not just typed LLM errors.

    The validator runs before the edit is persisted, so a raise here would roll
    back the user's already-compiled edit — it must never propagate.
    """
    fake_llm["reply"] = exc
    assert await validate_d2_against_prd(PRD, D2) is None
