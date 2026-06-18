"""The DIAGRAM_GENERATION phase engine (Story 2.1, re-pointed to D2 in Epic D.2).

Following the backlog's testing philosophy, these tests inject a fake `call_llm`
and assert *our* behaviour: the engine asks the model for D2 source and carries
the returned D2 verbatim on `LLMResponse.diagram_d2` with `next_phase` None and a
grounded assistant message; a markdown fence is stripped; an empty reply fails as
a bad model round-trip. No real LLM, no DB — the engine is pure generation logic
and never persists (that is the chat endpoint's job).

The "does the D2 compile?" validation gate with one corrective retry is D.3 (it
needs the D2 compiler, D.5), so it is exercised there, not here.
"""

import pytest
from langflow.lothal.engines import diagram_generation
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

    monkeypatch.setattr(diagram_generation, "call_llm", _call_llm)
    return captured


# --- registration ------------------------------------------------------------


def test_engine_is_registered_under_diagram_generation():
    engine = get_engine(ProjectPhase.DIAGRAM_GENERATION)
    assert isinstance(engine, DiagramGenerationEngine)
    assert engine.phase == "DIAGRAM_GENERATION"


# --- happy path --------------------------------------------------------------


async def test_valid_reply_yields_d2_and_no_transition(fake_llm):
    fake_llm["replies"] = [D2_SOURCE]

    response = await DiagramGenerationEngine().process([], "build it")

    assert isinstance(response, LLMResponse)
    assert response.next_phase is None  # generating keeps the project in DIAGRAM_GENERATION
    assert response.suggestions == []
    # The D2 rides on `.diagram_d2`, stored verbatim; the legacy xyflow field is unused.
    assert response.diagram_d2 == D2_SOURCE
    assert response.diagram is None
    # The assistant message is grounded in the actual diagram (its 4 interactions).
    assert "4 interactions" in response.text
    assert len(fake_llm["calls"]) == 1  # no retry on the D.2 path


async def test_prompt_asks_the_model_for_d2(fake_llm):
    fake_llm["replies"] = [D2_SOURCE]

    await DiagramGenerationEngine().process([], "build it")

    system_message = fake_llm["calls"][0]["messages"][0]
    assert system_message["role"] == "system"
    assert "D2" in system_message["content"]
    assert "shape: sequence_diagram" in system_message["content"]


async def test_reply_wrapped_in_code_fence_is_unwrapped(fake_llm):
    fake_llm["replies"] = [f"```d2\n{D2_SOURCE}\n```"]

    response = await DiagramGenerationEngine().process([], "build it")

    # The fence is stripped; the stored D2 is the bare source, ready to compile.
    assert response.diagram_d2 == D2_SOURCE
    assert len(fake_llm["calls"]) == 1


# --- empty round-trip --------------------------------------------------------


async def test_empty_reply_raises_connection_error(fake_llm):
    fake_llm["replies"] = ["   \n  "]

    with pytest.raises(LLMConnectionError, match="empty diagram"):
        await DiagramGenerationEngine().process([], "build it")

    assert len(fake_llm["calls"]) == 1


# --- prompt sanity -----------------------------------------------------------


def test_system_prompt_states_the_minimum_diagram_size():
    assert str(MIN_PARTICIPANTS) in diagram_generation.SYSTEM_PROMPT
    assert str(MIN_MESSAGES) in diagram_generation.SYSTEM_PROMPT
