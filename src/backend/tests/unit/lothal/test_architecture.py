"""The merged ARCHITECTURE phase engine (Epic E.2).

Epic E collapsed `DIAGRAM_GENERATION` + `DIAGRAM_REFINEMENT` into one
`ARCHITECTURE` stage. These tests assert the *wiring* the merge introduces — the
generation and refinement logic themselves are covered in
`test_diagram_generation.py` / `test_diagram_refinement.py`, so here the
delegates are stubbed and we only check dispatch:

- the engine is what's registered for `ARCHITECTURE`;
- with no diagram yet, a turn routes to *generation*;
- once a diagram exists, a turn routes to *refinement*;
- neither path emits a `next_phase` (the generation→refinement auto-advance is
  gone — the project stays in `ARCHITECTURE` until the user approves).

No real LLM, no DB.
"""

import pytest
from langflow.lothal.engines.architecture import ArchitectureEngine
from langflow.lothal.router import LLMResponse, get_engine
from langflow.services.database.models.lothal_project.model import ProjectPhase


@pytest.fixture
def spy_delegates(monkeypatch):
    """Replace the two delegate engines' `process` with recording stubs.

    Each stub records that it ran and returns a distinct `LLMResponse`, so a test
    can tell which branch the dispatch took without invoking the real LLM/compile
    machinery.
    """
    calls: list[str] = []

    async def _generate(self, history, user_message, *, prd=None, current_d2=None):  # noqa: ARG001
        calls.append("generate")
        return LLMResponse(text="generated", diagram_d2="shape: sequence_diagram\na: A\nb: B\na -> b: x")

    async def _refine(self, history, user_message, *, prd=None, current_d2=None):  # noqa: ARG001
        calls.append("refine")
        return LLMResponse(text="refined", diagram_d2="shape: sequence_diagram\na: A\nb: B\na -> b: y")

    from langflow.lothal.engines import diagram_generation, diagram_refinement

    monkeypatch.setattr(diagram_generation.DiagramGenerationEngine, "process", _generate)
    monkeypatch.setattr(diagram_refinement.DiagramRefinementEngine, "process", _refine)
    return calls


def test_engine_is_registered_under_architecture():
    engine = get_engine(ProjectPhase.ARCHITECTURE)
    assert isinstance(engine, ArchitectureEngine)
    assert engine.phase == "ARCHITECTURE"


async def test_first_turn_without_diagram_routes_to_generation(spy_delegates):
    response = await ArchitectureEngine().process([], "build a todo app", prd="the spec", current_d2=None)

    assert spy_delegates == ["generate"]
    assert response.text == "generated"
    # No auto-advance: generation keeps the project in ARCHITECTURE.
    assert response.next_phase is None


async def test_blank_diagram_still_routes_to_generation(spy_delegates):
    """A whitespace-only store is "no diagram" — the same normalisation `GET /diagram` uses."""
    await ArchitectureEngine().process([], "build it", prd="the spec", current_d2="   \n")

    assert spy_delegates == ["generate"]


async def test_later_turn_with_diagram_routes_to_refinement(spy_delegates):
    existing = "shape: sequence_diagram\nuser: User\napi: API\nuser -> api: go"
    response = await ArchitectureEngine().process([], "rename `user`", prd="the spec", current_d2=existing)

    assert spy_delegates == ["refine"]
    assert response.text == "refined"
    # Refining also stays in ARCHITECTURE (approval is the /diagram/approve endpoint).
    assert response.next_phase is None
