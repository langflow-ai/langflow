"""Story 0.3 — Phase Router.

The router is pure infrastructure: it dispatches a turn to the engine registered
for a phase and returns that engine's `LLMResponse`. These tests register fake
engines (no real LLM, no DB) and assert routing, the open/closed registry, and
the `LLMResponse` contract. Each test runs against a clean registry so global
state never leaks between tests.
"""

import pytest
from langflow.lothal import router as phase_router
from langflow.lothal.router import (
    LLMResponse,
    PhaseEngine,
    available_phases,
    get_engine,
    process_turn,
    register_engine,
)


@pytest.fixture(autouse=True)
def clean_registry(monkeypatch):
    """Isolate each test with empty engine and instance registries."""
    monkeypatch.setattr(phase_router, "_ENGINES", {})
    monkeypatch.setattr(phase_router, "_INSTANCES", {})


# --- LLMResponse contract ----------------------------------------------------


def test_llm_response_defaults_to_no_suggestions_and_no_transition():
    response = LLMResponse(text="hello")

    assert response.text == "hello"
    assert response.suggestions == []
    assert response.next_phase is None


def test_llm_response_rejects_empty_text():
    with pytest.raises(ValueError, match="text must be a non-empty string"):
        LLMResponse(text="   ")


def test_llm_response_rejects_non_string_suggestions():
    with pytest.raises(ValueError, match="suggestions must be a list of strings"):
        LLMResponse(text="hi", suggestions=["ok", 3])


# --- routing -----------------------------------------------------------------


async def test_process_turn_routes_to_registered_engine():
    @register_engine
    class FakeEngine(PhaseEngine):
        phase = "CLARIFICATION"

        async def process(self, _history, _user_message, **_kwargs):
            return LLMResponse(text="hello", suggestions=[], next_phase="NEXT_PHASE")

    result = await process_turn("CLARIFICATION", [], "build me a todo app")

    assert isinstance(result, LLMResponse)
    assert result.text == "hello"
    assert result.suggestions == []
    assert result.next_phase == "NEXT_PHASE"


async def test_process_turn_passes_history_and_message_to_engine():
    captured = {}

    @register_engine
    class CapturingEngine(PhaseEngine):
        phase = "CLARIFICATION"

        async def process(self, history, user_message, *, prd=None, current_d2=None):
            captured["history"] = history
            captured["user_message"] = user_message
            captured["prd"] = prd
            captured["current_d2"] = current_d2
            return LLMResponse(text="ok")

    history = ["turn-1", "turn-2"]  # opaque to the router; engines interpret them
    await process_turn("CLARIFICATION", history, "go", prd="the spec", current_d2="a -> b")

    assert captured["history"] is history
    assert captured["user_message"] == "go"
    # The router threads the project's PRD and current D2 straight through to the engine.
    assert captured["prd"] == "the spec"
    assert captured["current_d2"] == "a -> b"


async def test_unknown_phase_raises_value_error():
    with pytest.raises(ValueError, match="No engine registered for phase 'DIAGRAM_GENERATION'"):
        await process_turn("DIAGRAM_GENERATION", [], "hi")


async def test_engine_returning_non_response_raises_type_error():
    @register_engine
    class BadEngine(PhaseEngine):
        phase = "CLARIFICATION"

        async def process(self, _history, _user_message, **_kwargs):
            return "just a string"  # type: ignore[return-value]

    with pytest.raises(TypeError, match="expected LLMResponse"):
        await process_turn("CLARIFICATION", [], "hi")


# --- registry (open/closed) --------------------------------------------------


def test_registering_a_second_engine_does_not_disturb_the_first():
    @register_engine
    class EngineA(PhaseEngine):
        phase = "CLARIFICATION"

        async def process(self, _history, _user_message, **_kwargs):
            return LLMResponse(text="a")

    @register_engine
    class EngineB(PhaseEngine):
        phase = "ARCHITECTURE"

        async def process(self, _history, _user_message, **_kwargs):
            return LLMResponse(text="b")

    assert available_phases() == ["ARCHITECTURE", "CLARIFICATION"]
    assert isinstance(get_engine("CLARIFICATION"), EngineA)
    assert isinstance(get_engine("ARCHITECTURE"), EngineB)


def test_get_engine_caches_the_instance():
    @register_engine
    class CountingEngine(PhaseEngine):
        phase = "CLARIFICATION"

        async def process(self, _history, _user_message, **_kwargs):
            return LLMResponse(text="x")

    assert get_engine("CLARIFICATION") is get_engine("CLARIFICATION")


def test_duplicate_phase_registration_is_rejected():
    @register_engine
    class First(PhaseEngine):
        phase = "CLARIFICATION"

        async def process(self, _history, _user_message, **_kwargs):
            return LLMResponse(text="1")

    with pytest.raises(ValueError, match="already has an engine"):

        @register_engine
        class Second(PhaseEngine):
            phase = "CLARIFICATION"

            async def process(self, _history, _user_message, **_kwargs):
                return LLMResponse(text="2")


def test_engine_without_phase_is_rejected():
    with pytest.raises(ValueError, match="must define a non-empty string `phase`"):

        @register_engine
        class NoPhase(PhaseEngine):
            phase = "  "

            async def process(self, _history, _user_message, **_kwargs):
                return LLMResponse(text="x")
