"""The DIAGRAM_GENERATION phase engine (Story 2.1; D2 in D.2; compile-validation in D.3).

Following the backlog's testing philosophy, these tests inject a fake `call_llm`
(and a controllable `compile_d2`) and assert *our* behaviour: the engine asks the
model for D2 source and carries the returned D2 verbatim on
`LLMResponse.diagram_d2` with `next_phase` None and a grounded assistant message;
a markdown fence is stripped; an empty reply fails as a bad model round-trip. No
real LLM, no DB — the engine is pure generation logic and never persists (that is
the chat endpoint's job).

D.3's validation gate is exercised here: D2 that fails to compile triggers one
corrective retry carrying the compiler's error; a second failure raises
`LLMConnectionError` (→ 502); an unavailable compiler degrades to storing the
source unvalidated. The compiler itself (the `d2` subprocess) is covered in
`test_d2_compile.py`; here `compile_d2` is stubbed so the engine logic is tested
deterministically without the binary.
"""

import pytest
from langflow.lothal.d2_compile import D2CompileResult, D2CompilerUnavailableError
from langflow.lothal.engines import d2_gate, diagram_generation
from langflow.lothal.engines.diagram_generation import (
    MIN_MESSAGES,
    MIN_PARTICIPANTS,
    DiagramGenerationEngine,
)
from langflow.lothal.llm import LLMConnectionError
from langflow.lothal.router import LLMResponse, get_engine
from langflow.services.database.models.lothal_project.model import ProjectPhase

D2_SOURCE = """\
shape: sequence_diagram
user: User
api: API
db: Database

user -> api: submit form
api -> db: insert row
db -> api: ok
api -> user: 200 OK"""


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace `call_llm` with a stub returning queued replies and capturing calls."""
    captured = {"calls": [], "replies": []}

    async def _call_llm(messages, **kwargs):
        captured["calls"].append({"messages": messages, "kwargs": kwargs})
        return captured["replies"][len(captured["calls"]) - 1]

    # The engine drives the model through the shared `d2_gate`, so patch it there.
    monkeypatch.setattr(d2_gate, "call_llm", _call_llm)
    return captured


@pytest.fixture
def fake_compile(monkeypatch):
    """Replace `compile_d2` with a stub returning queued results and capturing calls.

    Queue `results` with `D2CompileResult`s (or a `D2CompilerUnavailableError`
    instance to simulate a missing binary). Any call past the queue's end returns
    a successful compile, so happy-path tests need not configure it.
    """
    captured = {"calls": [], "results": []}

    async def _compile_d2(src):
        captured["calls"].append(src)
        results = captured["results"]
        idx = len(captured["calls"]) - 1
        outcome = results[idx] if idx < len(results) else D2CompileResult(ok=True)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(d2_gate, "compile_d2", _compile_d2)
    return captured


# --- registration ------------------------------------------------------------


def test_engine_is_registered_under_diagram_generation():
    engine = get_engine(ProjectPhase.DIAGRAM_GENERATION)
    assert isinstance(engine, DiagramGenerationEngine)
    assert engine.phase == "DIAGRAM_GENERATION"


# --- happy path --------------------------------------------------------------


async def test_valid_reply_yields_d2_and_hands_off_to_refinement(fake_llm, fake_compile):
    fake_llm["replies"] = [D2_SOURCE]

    response = await DiagramGenerationEngine().process([], "build it")

    assert isinstance(response, LLMResponse)
    # Having drafted the first diagram, generation hands off to refinement (D.8).
    assert response.next_phase == ProjectPhase.DIAGRAM_REFINEMENT
    assert response.suggestions == []
    # The D2 rides on `.diagram_d2`, stored verbatim.
    assert response.diagram_d2 == D2_SOURCE
    # Generation drafts; it doesn't run the D.10 coherence validator (that's refinement).
    assert response.warning is None
    # The assistant message is grounded in the actual diagram (its 4 interactions).
    assert "4 interactions" in response.text
    assert len(fake_llm["calls"]) == 1  # compiled first time → no retry
    # The gate ran against the extracted D2 (not the raw reply).
    assert fake_compile["calls"] == [D2_SOURCE]


async def test_prompt_asks_the_model_for_d2(fake_llm, fake_compile):
    fake_llm["replies"] = [D2_SOURCE]
    fake_compile["results"] = [D2CompileResult(ok=True)]

    await DiagramGenerationEngine().process([], "build it")

    system_message = fake_llm["calls"][0]["messages"][0]
    assert system_message["role"] == "system"
    assert "D2" in system_message["content"]
    assert "shape: sequence_diagram" in system_message["content"]


async def test_reply_wrapped_in_code_fence_is_unwrapped(fake_llm, fake_compile):
    fake_llm["replies"] = [f"```d2\n{D2_SOURCE}\n```"]

    response = await DiagramGenerationEngine().process([], "build it")

    # The fence is stripped; the stored D2 is the bare source, and the compile
    # gate sees that bare source — not the fenced reply.
    assert response.diagram_d2 == D2_SOURCE
    assert fake_compile["calls"] == [D2_SOURCE]
    assert len(fake_llm["calls"]) == 1


# --- empty round-trip --------------------------------------------------------


async def test_empty_reply_raises_connection_error(fake_llm, fake_compile):
    fake_llm["replies"] = ["   \n  "]

    with pytest.raises(LLMConnectionError, match="empty diagram"):
        await DiagramGenerationEngine().process([], "build it")

    assert len(fake_llm["calls"]) == 1
    assert fake_compile["calls"] == []  # empty reply is rejected before the compile gate


# --- compile-validation gate (D.3) -------------------------------------------


async def test_uncompilable_d2_retries_once_then_succeeds(fake_llm, fake_compile):
    bad_d2 = "user -> : broken"
    fake_llm["replies"] = [bad_d2, D2_SOURCE]
    fake_compile["results"] = [
        D2CompileResult(ok=False, error="1:1: connection missing destination"),
        D2CompileResult(ok=True),
    ]

    response = await DiagramGenerationEngine().process([], "build it")

    # Second, compilable attempt is what gets stored.
    assert response.diagram_d2 == D2_SOURCE
    assert len(fake_llm["calls"]) == 2
    assert fake_compile["calls"] == [bad_d2, D2_SOURCE]

    # The retry resends the conversation plus the bad reply and the compiler error
    # as a correction, so attempt two is a fix rather than a blind redo.
    retry_messages = fake_llm["calls"][1]["messages"]
    assert {"role": "assistant", "content": bad_d2} in retry_messages
    correction = retry_messages[-1]
    assert correction["role"] == "user"
    assert "connection missing destination" in correction["content"]


async def test_uncompilable_twice_raises_connection_error(fake_llm, fake_compile):
    fake_llm["replies"] = ["first bad", "second bad"]
    fake_compile["results"] = [
        D2CompileResult(ok=False, error="1:1: connection missing destination"),
        D2CompileResult(ok=False, error="2:1: missing value after colon"),
    ]

    with pytest.raises(LLMConnectionError, match="failed to compile twice"):
        await DiagramGenerationEngine().process([], "build it")

    # Exactly one corrective retry; the final (second) compiler error is surfaced.
    assert len(fake_llm["calls"]) == 2
    assert len(fake_compile["calls"]) == 2


async def test_compiler_unavailable_skips_gate_and_stores(fake_llm, fake_compile):
    # A missing binary is an environment fault, not a bad diagram: store the source
    # unvalidated rather than fail the turn or wrongly trigger a retry.
    fake_llm["replies"] = [D2_SOURCE]
    fake_compile["results"] = [D2CompilerUnavailableError("no d2 on PATH")]

    response = await DiagramGenerationEngine().process([], "build it")

    assert response.diagram_d2 == D2_SOURCE
    assert len(fake_llm["calls"]) == 1  # no retry — the gate was skipped, not failed


# --- prompt sanity -----------------------------------------------------------


def test_system_prompt_states_the_minimum_diagram_size():
    assert str(MIN_PARTICIPANTS) in diagram_generation.SYSTEM_PROMPT
    assert str(MIN_MESSAGES) in diagram_generation.SYSTEM_PROMPT


def test_system_prompt_forbids_positions_so_no_auto_layout_is_needed():
    """D.14: the prompt must forbid positions so the `auto_layout` fallback stays obsolete.

    D2 owns layout and the model emits no positions, so the position-repair
    fallback (`auto_layout`, Story 2.5) is unnecessary. Pin the prompt instruction
    so a future edit can't reintroduce position output and quietly revive that need.
    """
    prompt = diagram_generation.SYSTEM_PROMPT.lower()
    assert "never write positions" in prompt
    assert "d2 owns layout" in prompt
