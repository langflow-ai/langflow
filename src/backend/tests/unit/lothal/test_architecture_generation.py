"""Architecture-stage generation: the full ADR + diagram-set artifact map (Epic E.3).

Following the backlog's testing philosophy, these tests inject fakes for the three
model seams the generation drives — the diagrams' `d2_gate.call_llm`, the ADR's own
`architecture_generation.call_llm`, and the coherence validator's
`d2_validator.call_llm` — plus a controllable `compile_d2`, and assert *our*
behaviour: one turn produces the whole `{adr.md, diagrams/*}` map, mirrors the
sequence diagram onto `diagram_d2`, stays in `ARCHITECTURE` (`next_phase=None`),
and folds per-diagram coherence warnings into one advisory message. No real LLM,
no DB — generation is pure turn logic and never persists.

The diagram replies are returned regardless of call order because the four
diagrams generate concurrently (`asyncio.gather`); the fakes are content-agnostic
so the assertions don't depend on which diagram resolves first.
"""

import pytest
from langflow.lothal.d2_compile import D2CompileResult
from langflow.lothal.engines import architecture_generation, d2_gate, d2_validator
from langflow.lothal.engines.architecture_artifacts import (
    ADR_PATH,
    CONTAINER_PATH,
    CONTEXT_PATH,
    DATA_MODEL_PATH,
    SEQUENCE_PATH,
)
from langflow.lothal.engines.architecture_generation import generate_architecture
from langflow.lothal.llm import LLMConnectionError
from langflow.lothal.router import LLMResponse

SEQUENCE_D2 = """\
shape: sequence_diagram
user: User
api: API
db: Database

user -> api: submit form
api -> db: insert row
db -> api: ok
api -> user: 200 OK"""

ADR_MD = "# Architecture Decision Record\n\n## Context\nA todo app.\n\n## Decision\nMonolith + Postgres."

PRD = "## Overview\nA todo app for individuals.\n## Core Features\nCreate and complete tasks."


@pytest.fixture
def fake_diagram_llm(monkeypatch):
    """Stub the diagrams' `call_llm` (on `d2_gate`); returns a fixed D2 for every call."""
    state = {"reply": SEQUENCE_D2, "calls": []}

    async def _call_llm(messages, **_kwargs):
        state["calls"].append(messages)
        reply = state["reply"]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(d2_gate, "call_llm", _call_llm)
    return state


@pytest.fixture
def fake_adr_llm(monkeypatch):
    """Stub the ADR's `call_llm` (its own seam on `architecture_generation`)."""
    state = {"reply": ADR_MD, "calls": []}

    async def _call_llm(messages, **_kwargs):
        state["calls"].append(messages)
        reply = state["reply"]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(architecture_generation, "call_llm", _call_llm)
    return state


@pytest.fixture
def fake_compile(monkeypatch):
    """Stub `compile_d2` (on `d2_gate`); every call compiles unless told otherwise."""
    state = {"calls": [], "result": D2CompileResult(ok=True)}

    async def _compile_d2(src):
        state["calls"].append(src)
        outcome = state["result"]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(d2_gate, "compile_d2", _compile_d2)
    return state


@pytest.fixture(autouse=True)
def stub_validator(monkeypatch):
    """Stub the coherence validator's `call_llm`, defaulting to `VALID` (no warning)."""
    state = {"value": "VALID", "calls": []}

    async def _call_llm(messages, **_kwargs):
        state["calls"].append(messages)
        value = state["value"]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(d2_validator, "call_llm", _call_llm)
    return state


# --- happy path --------------------------------------------------------------


@pytest.mark.usefixtures("fake_compile")
async def test_generates_the_full_artifact_map(fake_diagram_llm, fake_adr_llm):
    response = await generate_architecture([], "let's design it", prd=PRD)

    assert isinstance(response, LLMResponse)
    # The whole set is produced: the ADR plus the four diagrams.
    assert set(response.artifacts) == {ADR_PATH, CONTEXT_PATH, CONTAINER_PATH, DATA_MODEL_PATH, SEQUENCE_PATH}
    assert response.artifacts[ADR_PATH] == ADR_MD
    assert response.artifacts[SEQUENCE_PATH] == SEQUENCE_D2
    # The sequence diagram is mirrored onto the single-diagram store (E.4 carry-over).
    assert response.diagram_d2 == SEQUENCE_D2
    # Generation keeps the project in ARCHITECTURE; a clean set raises no warning.
    assert response.next_phase is None
    assert response.warning is None
    assert response.suggestions == []
    # Four diagram round-trips + one ADR round-trip.
    assert len(fake_diagram_llm["calls"]) == 4
    assert len(fake_adr_llm["calls"]) == 1
    # The reply is grounded in the set the user can now review.
    assert "4 diagrams" in response.text


@pytest.mark.usefixtures("fake_compile", "fake_adr_llm")
async def test_each_diagram_prompt_is_used(fake_diagram_llm):
    await generate_architecture([], "design it", prd=PRD)

    # Each diagram is asked for with its own prompt — collect the system prompts
    # across the four (concurrent, so order-independent) calls.
    system_prompts = " || ".join(call[0]["content"] for call in fake_diagram_llm["calls"])
    assert "SYSTEM CONTEXT" in system_prompts
    assert "CONTAINER diagram" in system_prompts
    assert "DATA MODEL" in system_prompts
    assert "SEQUENCE diagram" in system_prompts


@pytest.mark.usefixtures("fake_compile", "fake_adr_llm")
async def test_prd_is_restated_in_the_generation_turn(fake_diagram_llm):
    await generate_architecture([], "design it", prd=PRD)

    # Every diagram turn restates the PRD as a labelled block (robust to history truncation).
    turn = fake_diagram_llm["calls"][0][-1]["content"]
    assert "## Product spec (PRD)" in turn
    assert "A todo app for individuals." in turn


@pytest.mark.usefixtures("fake_compile", "fake_diagram_llm")
async def test_adr_turn_restates_the_prd(fake_adr_llm):
    await generate_architecture([], "design it", prd=PRD)

    adr_turn = fake_adr_llm["calls"][0][-1]["content"]
    assert "A todo app for individuals." in adr_turn
    # The ADR prompt asks for Markdown, not D2.
    assert "Markdown" in fake_adr_llm["calls"][0][0]["content"]


# --- coherence warnings ------------------------------------------------------


@pytest.mark.usefixtures("fake_compile", "fake_diagram_llm", "fake_adr_llm")
async def test_coherence_warning_surfaces_labelled_by_diagram(stub_validator):
    stub_validator["value"] = "WARNING: the diagram drops a participant the spec requires"

    response = await generate_architecture([], "design it", prd=PRD)

    # The set is still produced (warnings are advisory, not a gate), and the
    # warning names the offending diagram(s).
    assert response.artifacts[SEQUENCE_PATH] == SEQUENCE_D2
    assert response.warning is not None
    assert "diagram:" in response.warning
    assert "drops a participant the spec requires" in response.warning


# --- ADR round-trip ----------------------------------------------------------


@pytest.mark.usefixtures("fake_compile", "fake_diagram_llm")
async def test_empty_adr_reply_raises_connection_error(fake_adr_llm):
    fake_adr_llm["reply"] = "   \n  "

    with pytest.raises(LLMConnectionError, match="empty ADR"):
        await generate_architecture([], "design it", prd=PRD)


@pytest.mark.usefixtures("fake_compile", "fake_diagram_llm")
async def test_adr_code_fence_is_stripped(fake_adr_llm):
    fake_adr_llm["reply"] = f"```markdown\n{ADR_MD}\n```"

    response = await generate_architecture([], "design it", prd=PRD)

    assert response.artifacts[ADR_PATH] == ADR_MD


# --- compile gate ------------------------------------------------------------


@pytest.mark.usefixtures("fake_adr_llm", "fake_diagram_llm")
async def test_diagrams_run_through_the_compile_gate(fake_compile):
    """Each generated diagram is compile-checked (the shared D.3 gate); its retry is covered in test_d2_gate."""
    await generate_architecture([], "design it", prd=PRD)

    # One compile per diagram on the happy path (all four compile first time).
    assert len(fake_compile["calls"]) == 4
    assert SEQUENCE_D2 in fake_compile["calls"]
