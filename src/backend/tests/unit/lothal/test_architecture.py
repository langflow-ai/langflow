"""The merged ARCHITECTURE phase engine (Epic E.2, re-keyed on the artifact map in E.3).

Epic E collapsed `DIAGRAM_GENERATION` + `DIAGRAM_REFINEMENT` into one
`ARCHITECTURE` stage, and E.3 grew its output from a single diagram into the full
artifact map (an ADR + four D2 diagrams). These tests assert the *dispatch* the
engine performs — the generation and refinement logic themselves are covered in
`test_architecture_generation.py` / `test_architecture_refinement.py`, so here the
two are stubbed and we only check routing:

- the engine is what's registered for `ARCHITECTURE`;
- with no artifact map yet, a turn routes to *generation*;
- once artifacts exist, a turn routes to *refinement*, threading the active
  artifact key (`target_artifact`) through;
- neither path emits a `next_phase` (the project stays in `ARCHITECTURE` until the
  user approves).

No real LLM, no DB.
"""

import pytest
from langflow.lothal.engines import architecture
from langflow.lothal.engines.architecture import ArchitectureEngine
from langflow.lothal.router import LLMResponse, get_engine
from langflow.services.database.models.lothal_project.model import ProjectPhase

_SEQUENCE = "shape: sequence_diagram\nuser: User\napi: API\nuser -> api: go"
_MAP = {"adr.md": "# ADR", "diagrams/sequence.d2": _SEQUENCE}


@pytest.fixture
def spy_dispatch(monkeypatch):
    """Replace the generate/refine delegates with recording stubs.

    Each stub records the branch (and, for refine, the target artifact it was
    handed) and returns a distinct `LLMResponse`, so a test can tell which way the
    dispatch went without the real LLM/compile machinery.
    """
    calls: list[tuple] = []

    async def _generate(history, user_message, *, prd=None):  # noqa: ARG001
        calls.append(("generate", None))
        return LLMResponse(text="generated", artifacts=_MAP, diagram_d2=_SEQUENCE)

    async def _refine(history, user_message, *, prd=None, artifacts, target_artifact=None):  # noqa: ARG001
        calls.append(("refine", target_artifact))
        return LLMResponse(text="refined", artifacts=artifacts, diagram_d2=_SEQUENCE)

    monkeypatch.setattr(architecture, "generate_architecture", _generate)
    monkeypatch.setattr(architecture, "refine_architecture", _refine)
    return calls


def test_engine_is_registered_under_architecture():
    engine = get_engine(ProjectPhase.ARCHITECTURE)
    assert isinstance(engine, ArchitectureEngine)
    assert engine.phase == "ARCHITECTURE"


async def test_first_turn_without_artifacts_routes_to_generation(spy_dispatch):
    response = await ArchitectureEngine().process([], "build a todo app", prd="the spec", artifacts=None)

    assert spy_dispatch == [("generate", None)]
    assert response.text == "generated"
    # The full artifact map is carried; no auto-advance.
    assert response.artifacts == _MAP
    assert response.next_phase is None


async def test_empty_artifact_map_still_routes_to_generation(spy_dispatch):
    """An empty `{}` map is "not generated yet" — the same truthiness the engine keys on."""
    await ArchitectureEngine().process([], "build it", prd="the spec", artifacts={})

    assert spy_dispatch == [("generate", None)]


async def test_later_turn_with_artifacts_routes_to_refinement(spy_dispatch):
    response = await ArchitectureEngine().process(
        [], "rename `user`", prd="the spec", artifacts=_MAP, target_artifact="diagrams/context.d2"
    )

    # Refinement ran, and the active artifact key was threaded through to it.
    assert spy_dispatch == [("refine", "diagrams/context.d2")]
    assert response.text == "refined"
    assert response.next_phase is None


async def test_legacy_current_d2_does_not_drive_dispatch(spy_dispatch):
    """E.3 re-keys the stage on `artifacts`: a leftover `current_d2` no longer means "refine"."""
    await ArchitectureEngine().process([], "build it", prd="the spec", current_d2=_SEQUENCE, artifacts=None)

    assert spy_dispatch == [("generate", None)]
