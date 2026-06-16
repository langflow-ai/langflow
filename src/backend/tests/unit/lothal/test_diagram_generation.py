"""Story 2.1 — the DIAGRAM_GENERATION phase engine.

Following the backlog's testing philosophy, these tests inject a fake `call_llm`
and assert *our* behaviour: a valid xyflow graph reply becomes an `LLMResponse`
carrying that graph on `.diagram` with `next_phase` None; an invalid first reply
is retried exactly once with the validator's complaint fed back; two invalid
replies fail as a bad model round-trip. No real LLM, no DB — the engine is pure
generation logic and never persists (that is the chat endpoint's job).
"""

import json

import pytest
from langflow.lothal.diagram import MIN_EDGES, MIN_NODES, validate_diagram
from langflow.lothal.engines import diagram_generation
from langflow.lothal.engines.diagram_generation import DiagramGenerationEngine
from langflow.lothal.llm import LLMConnectionError
from langflow.lothal.router import LLMResponse, get_engine
from langflow.services.database.models.lothal_project.model import ProjectPhase


def _graph() -> dict:
    """A minimal valid xyflow graph: 2 nodes, 3 ordered edges, full positions."""
    return {
        "nodes": [
            {"id": "user", "type": "actorNode", "position": {"x": 0, "y": 0}, "data": {"label": "User"}},
            {"id": "api", "type": "systemNode", "position": {"x": 240, "y": 0}, "data": {"label": "API"}},
        ],
        "edges": [
            {"id": "e1", "source": "user", "target": "api", "data": {"order": 1, "label": "submit"}},
            {"id": "e2", "source": "api", "target": "user", "animated": True, "data": {"order": 2, "label": "200 OK"}},
            {"id": "e3", "source": "user", "target": "api", "data": {"order": 3, "label": "poll"}},
        ],
    }


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


async def test_valid_reply_yields_diagram_and_no_transition(fake_llm):
    fake_llm["replies"] = [json.dumps(_graph())]

    response = await DiagramGenerationEngine().process([], "build it")

    assert isinstance(response, LLMResponse)
    assert response.next_phase is None  # generating keeps the project in DIAGRAM_GENERATION
    assert response.suggestions == []
    assert response.text.strip()  # a grounded, storable assistant message
    # The graph rides on `.diagram` as a plain dict and round-trips the validator.
    assert response.diagram is not None
    parsed = validate_diagram(response.diagram)
    assert [n.id for n in parsed.nodes] == ["user", "api"]
    assert [e.data.order for e in parsed.edges] == [1, 2, 3]
    assert len(fake_llm["calls"]) == 1  # a valid first reply needs no retry


async def test_reply_wrapped_in_code_fence_is_parsed(fake_llm):
    fake_llm["replies"] = [f"```json\n{json.dumps(_graph())}\n```"]

    response = await DiagramGenerationEngine().process([], "build it")

    assert response.diagram is not None
    assert len(fake_llm["calls"]) == 1


# --- retry-once on invalid output --------------------------------------------


async def test_invalid_first_reply_is_retried_once_then_succeeds(fake_llm):
    # First reply has too few edges (1 < MIN_EDGES); the retry returns a valid graph.
    too_few = _graph()
    too_few["edges"] = too_few["edges"][:1]
    fake_llm["replies"] = [json.dumps(too_few), json.dumps(_graph())]

    response = await DiagramGenerationEngine().process([], "build it")

    assert response.diagram is not None
    assert validate_diagram(response.diagram).edges  # the valid retry graph won
    assert len(fake_llm["calls"]) == 2  # exactly one retry

    # The retry resends the invalid reply and the validator's complaint as a nudge.
    retry_messages = fake_llm["calls"][1]["messages"]
    assert retry_messages[-2]["role"] == "assistant"
    assert retry_messages[-1]["role"] == "user"
    assert "validator" in retry_messages[-1]["content"]


async def test_two_invalid_replies_raise_connection_error(fake_llm):
    dangling = _graph()
    dangling["edges"][0]["target"] = "ghost"  # edge points at a non-existent node
    fake_llm["replies"] = [json.dumps(dangling), json.dumps(dangling)]

    with pytest.raises(LLMConnectionError, match="invalid diagram twice"):
        await DiagramGenerationEngine().process([], "build it")

    assert len(fake_llm["calls"]) == 2  # tried once, retried once, then gave up


async def test_non_json_reply_is_retried(fake_llm):
    fake_llm["replies"] = ["Sure! Here is your diagram:", json.dumps(_graph())]

    response = await DiagramGenerationEngine().process([], "build it")

    assert response.diagram is not None
    assert len(fake_llm["calls"]) == 2


# --- prompt sanity -----------------------------------------------------------


def test_system_prompt_states_the_minimum_graph_size():
    assert str(MIN_NODES) in diagram_generation.SYSTEM_PROMPT
    assert str(MIN_EDGES) in diagram_generation.SYSTEM_PROMPT
