"""Diagram refinement logic of the ARCHITECTURE stage (Epic D.8; merged in E.2).

Following the backlog's testing philosophy, these tests inject a fake `call_llm`
(and a controllable `compile_d2`, both on the shared `d2_gate`) and assert *our*
behaviour: the refinement turn the model receives carries the current D2, the
PRD, and the referenced element ids (the backtick-wrapped anchors the D.7
composer serialises into the message), plus the instruction; the model's reply is
carried verbatim on `LLMResponse.diagram_d2` with `next_phase` None (refining
keeps the project in ARCHITECTURE — approval → CODE_GENERATION is the approve
endpoint) and a grounded assistant message. A markdown fence is stripped; an empty
reply fails as a bad round-trip. The compile-validation gate (D.3) is reused from
`d2_gate`, so its retry/failure behaviour is covered there; here we confirm the
engine routes through it. No real LLM, no DB — the engine never persists. Epic E.2
merged it under the `ArchitectureEngine`; the phase-level wiring is covered in
`test_architecture.py`.
"""

import pytest
from langflow.lothal.engines import d2_gate, d2_validator, diagram_refinement
from langflow.lothal.engines.diagram_refinement import DiagramRefinementEngine
from langflow.lothal.llm import LLMConnectionError
from langflow.lothal.router import LLMResponse

# A current diagram with two parallel `api -> db` edges, so an anchor with a
# `#2` suffix has something distinct to point at.
CURRENT_D2 = """\
shape: sequence_diagram
user: User
api: API
db: Database

user -> api: submit form
api -> db: insert row
api -> db: audit log
db -> api: ok
api -> user: 200 OK"""

UPDATED_D2 = """\
shape: sequence_diagram
browser: Browser
api: API
db: Database

browser -> api: submit form
api -> db: insert row
db -> api: ok
api -> browser: 200 OK"""

PRD = "## Overview\nA todo app for individuals.\n## Core Features\nCreate and complete tasks."


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace the gate's `call_llm` with a stub returning queued replies and capturing calls."""
    captured = {"calls": [], "replies": []}

    async def _call_llm(messages, **kwargs):
        captured["calls"].append({"messages": messages, "kwargs": kwargs})
        return captured["replies"][len(captured["calls"]) - 1]

    monkeypatch.setattr(d2_gate, "call_llm", _call_llm)
    return captured


@pytest.fixture
def fake_compile(monkeypatch):
    """Replace the gate's `compile_d2` with a stub returning queued results.

    Any call past the queue's end returns a successful compile, so happy-path
    tests need not configure it. The D2CompileResult import is local to keep this
    fixture's intent obvious alongside `test_d2_compile.py`.
    """
    from langflow.lothal.d2_compile import D2CompileResult

    captured = {"calls": [], "results": []}

    async def _compile_d2(src):
        captured["calls"].append(src)
        idx = len(captured["calls"]) - 1
        outcome = captured["results"][idx] if idx < len(captured["results"]) else D2CompileResult(ok=True)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(d2_gate, "compile_d2", _compile_d2)
    return captured


@pytest.fixture(autouse=True)
def stub_validator(monkeypatch):
    """Stub the D.10 coherence validator's own `call_llm`, defaulting to `VALID`.

    The engine runs `validate_d2_against_prd` (in `d2_validator`) after every
    compile-validated edit; that module has its OWN `call_llm` seam, independent
    of the editor's (`d2_gate.call_llm`). Autoused so the edit tests above never
    reach a real model and assert no warning by default; the D.10 tests below set
    `reply["value"]` to a `WARNING:` line to exercise the contradiction path, and
    capture the messages the validator saw.
    """
    state = {"value": "VALID", "calls": []}

    async def _call_llm(messages, **_kwargs):
        state["calls"].append(messages)
        value = state["value"]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(d2_validator, "call_llm", _call_llm)
    return state


def _composed(fake_llm) -> str:
    """The composed refinement turn the model saw (the last user message)."""
    return fake_llm["calls"][0]["messages"][-1]["content"]


# --- happy path: anchored edit ------------------------------------------------


async def test_anchored_edit_carries_updated_d2_without_transition(fake_llm, fake_compile):
    fake_llm["replies"] = [UPDATED_D2]

    response = await DiagramRefinementEngine().process([], "rename `user` to Browser", prd=PRD, current_d2=CURRENT_D2)

    assert isinstance(response, LLMResponse)
    # The model's updated D2 rides on `.diagram_d2`, verbatim; refining keeps the
    # project in ARCHITECTURE (approval → CODE_GENERATION is the approve endpoint).
    assert response.diagram_d2 == UPDATED_D2
    assert response.next_phase is None
    assert response.suggestions == []
    # A coherent edit (the default `VALID` stub) raises no D.10 warning.
    assert response.warning is None
    # The assistant text is grounded in the refined diagram (its 4 interactions).
    assert "4 interactions" in response.text
    # The gate ran against the extracted D2 reply.
    assert fake_compile["calls"] == [UPDATED_D2]


@pytest.mark.usefixtures("fake_compile")
async def test_prompt_carries_current_d2_prd_and_anchor(fake_llm):
    fake_llm["replies"] = [UPDATED_D2]

    await DiagramRefinementEngine().process([], "rename `user` to Browser", prd=PRD, current_d2=CURRENT_D2)

    system_message = fake_llm["calls"][0]["messages"][0]
    assert system_message["role"] == "system"
    assert "diagram editor" in system_message["content"].lower()

    composed = _composed(fake_llm)
    # The turn carries the PRD, the current D2 to edit, and the referenced id.
    assert "A todo app for individuals." in composed
    assert "user -> api: submit form" in composed
    assert "Referenced elements" in composed
    assert "`user`" in composed
    assert "rename" in composed  # the instruction itself is present


@pytest.mark.usefixtures("fake_compile")
async def test_parallel_edge_anchor_index_reaches_the_prompt(fake_llm):
    """A `#2` anchor (the 2nd parallel `api -> db` edge) is surfaced for the model."""
    fake_llm["replies"] = [UPDATED_D2]

    await DiagramRefinementEngine().process([], "delete `api -> db #2`", prd=PRD, current_d2=CURRENT_D2)

    composed = _composed(fake_llm)
    assert "Referenced elements" in composed
    assert "`api -> db #2`" in composed


@pytest.mark.usefixtures("fake_compile")
async def test_free_text_without_anchor_still_refines(fake_llm):
    """A non-anchored instruction works: no Referenced-elements block, edit still applied."""
    fake_llm["replies"] = [UPDATED_D2]

    response = await DiagramRefinementEngine().process(
        [], "add a logout step at the end", prd=PRD, current_d2=CURRENT_D2
    )

    assert response.diagram_d2 == UPDATED_D2
    composed = _composed(fake_llm)
    assert "Referenced elements" not in composed
    assert "add a logout step at the end" in composed


@pytest.mark.usefixtures("fake_compile")
async def test_empty_current_d2_is_labelled_for_the_model(fake_llm):
    """Defensive: with no current D2, the turn says so rather than sending a blank block."""
    fake_llm["replies"] = [UPDATED_D2]

    await DiagramRefinementEngine().process([], "start with a login flow", prd=PRD, current_d2=None)

    assert "the diagram is empty" in _composed(fake_llm)


# --- D.10 coherence validator -------------------------------------------------


@pytest.mark.usefixtures("fake_compile")
async def test_contradiction_surfaces_as_warning(fake_llm, stub_validator):
    """A `WARNING:` verdict from the validator rides on `LLMResponse.warning`."""
    fake_llm["replies"] = [UPDATED_D2]
    stub_validator["value"] = "WARNING: the diagram drops the Database the spec requires"

    response = await DiagramRefinementEngine().process([], "rename `user` to Browser", prd=PRD, current_d2=CURRENT_D2)

    # The edit still succeeds and is carried; the warning is advisory, not a gate.
    assert response.diagram_d2 == UPDATED_D2
    assert response.warning is not None
    assert "drops the Database the spec requires" in response.warning


@pytest.mark.usefixtures("fake_compile")
async def test_valid_verdict_adds_no_warning(fake_llm, stub_validator):
    fake_llm["replies"] = [UPDATED_D2]
    stub_validator["value"] = "VALID"

    response = await DiagramRefinementEngine().process([], "rename `user` to Browser", prd=PRD, current_d2=CURRENT_D2)

    assert response.warning is None


@pytest.mark.usefixtures("fake_compile")
async def test_validator_sees_prd_and_updated_d2(fake_llm, stub_validator):
    """The validator round-trip carries the PRD and the freshly edited D2."""
    fake_llm["replies"] = [UPDATED_D2]

    await DiagramRefinementEngine().process([], "rename `user` to Browser", prd=PRD, current_d2=CURRENT_D2)

    assert stub_validator["calls"], "the validator should run after a successful edit"
    validator_turn = stub_validator["calls"][0][-1]["content"]
    assert "A todo app for individuals." in validator_turn  # the PRD
    assert "browser -> api: submit form" in validator_turn  # the UPDATED D2, not the old one


@pytest.mark.usefixtures("fake_compile")
async def test_no_prd_skips_validation(fake_llm, stub_validator):
    """With no PRD there is nothing to validate against — the validator never runs."""
    fake_llm["replies"] = [UPDATED_D2]

    response = await DiagramRefinementEngine().process([], "rename `user` to Browser", prd=None, current_d2=CURRENT_D2)

    assert response.warning is None
    assert stub_validator["calls"] == []


@pytest.mark.usefixtures("fake_compile")
async def test_validator_fault_does_not_fail_the_edit(fake_llm, stub_validator):
    """An LLM fault in the advisory validator is swallowed — the edit still lands."""
    fake_llm["replies"] = [UPDATED_D2]
    stub_validator["value"] = LLMConnectionError("validator round-trip failed")

    response = await DiagramRefinementEngine().process([], "rename `user` to Browser", prd=PRD, current_d2=CURRENT_D2)

    assert response.diagram_d2 == UPDATED_D2
    assert response.warning is None


# --- fence + empty round-trip -------------------------------------------------


async def test_reply_wrapped_in_code_fence_is_unwrapped(fake_llm, fake_compile):
    fake_llm["replies"] = [f"```d2\n{UPDATED_D2}\n```"]

    response = await DiagramRefinementEngine().process([], "rename `user` to Browser", current_d2=CURRENT_D2)

    assert response.diagram_d2 == UPDATED_D2
    assert fake_compile["calls"] == [UPDATED_D2]


async def test_empty_reply_raises_connection_error(fake_llm, fake_compile):
    fake_llm["replies"] = ["   \n  "]

    with pytest.raises(LLMConnectionError, match="empty diagram"):
        await DiagramRefinementEngine().process([], "rename `user` to Browser", current_d2=CURRENT_D2)

    assert fake_compile["calls"] == []  # empty reply is rejected before the compile gate


# --- compile-validation gate (D.3, reused via d2_gate) ------------------------


async def test_uncompilable_reply_retries_once_then_succeeds(fake_llm, fake_compile):
    from langflow.lothal.d2_compile import D2CompileResult

    bad_d2 = "user -> : broken"
    fake_llm["replies"] = [bad_d2, UPDATED_D2]
    fake_compile["results"] = [
        D2CompileResult(ok=False, error="1:1: connection missing destination"),
        D2CompileResult(ok=True),
    ]

    response = await DiagramRefinementEngine().process([], "rename `user` to Browser", current_d2=CURRENT_D2)

    assert response.diagram_d2 == UPDATED_D2
    assert len(fake_llm["calls"]) == 2
    # The retry resends the bad reply plus the compiler error as a correction.
    retry_messages = fake_llm["calls"][1]["messages"]
    assert {"role": "assistant", "content": bad_d2} in retry_messages
    assert "connection missing destination" in retry_messages[-1]["content"]


async def test_uncompilable_twice_raises_connection_error(fake_llm, fake_compile):
    from langflow.lothal.d2_compile import D2CompileResult

    fake_llm["replies"] = ["first bad", "second bad"]
    fake_compile["results"] = [
        D2CompileResult(ok=False, error="1:1: connection missing destination"),
        D2CompileResult(ok=False, error="2:1: missing value after colon"),
    ]

    with pytest.raises(LLMConnectionError, match="failed to compile twice"):
        await DiagramRefinementEngine().process([], "rename `user` to Browser", current_d2=CURRENT_D2)

    assert len(fake_llm["calls"]) == 2


# --- prompt sanity -----------------------------------------------------------


def test_system_prompt_forbids_positions():
    prompt = diagram_refinement.SYSTEM_PROMPT.lower()
    assert "d2 owns layout" in prompt
    assert "never write positions" in prompt
