"""Architecture-stage refinement: editing one artifact in the map (Epic E.3).

The refine turn edits a single artifact — the active one the turn targets — and
carries the rest of the map verbatim. These tests inject the same fakes the
generation tests use (the diagram editor's `d2_gate.call_llm`, the ADR editor's
`architecture_refinement.call_llm`, the coherence validator's
`d2_validator.call_llm`, plus a controllable `compile_d2`) and assert *our*
behaviour: the right artifact is edited, the others are untouched, the sequence
diagram stays mirrored onto `diagram_d2`, anchors reach the editor, a diagram edit
is coherence-checked, and refining keeps the project in `ARCHITECTURE`. No real
LLM, no DB — the engine never persists.
"""

import pytest
from langflow.lothal.d2_compile import D2CompileResult
from langflow.lothal.engines import architecture_refinement, d2_gate, d2_validator
from langflow.lothal.engines.architecture_artifacts import (
    ADR_PATH,
    CONTAINER_PATH,
    CONTEXT_PATH,
    DATA_MODEL_PATH,
    SEQUENCE_PATH,
)
from langflow.lothal.engines.architecture_refinement import refine_architecture
from langflow.lothal.llm import LLMConnectionError
from langflow.lothal.router import LLMResponse

CURRENT_SEQUENCE = """\
shape: sequence_diagram
user: User
api: API
db: Database

user -> api: submit form
api -> db: insert row
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

CONTEXT_D2 = "direction: right\nuser: End User {shape: person}\napp: App\nuser -> app: uses"
UPDATED_ADR = "# Architecture Decision Record\n\n## Context\nUpdated."

PRD = "## Overview\nA todo app for individuals.\n## Core Features\nCreate and complete tasks."


def _artifacts() -> dict[str, str]:
    """A full, freshly-generated artifact map (a new dict per test so edits don't leak)."""
    return {
        ADR_PATH: "# Architecture Decision Record\n\n## Context\nA todo app.",
        CONTEXT_PATH: CONTEXT_D2,
        CONTAINER_PATH: "direction: right\nsystem: App {\n  api: API\n}",
        DATA_MODEL_PATH: "users: {\n  shape: sql_table\n  id: int\n}",
        SEQUENCE_PATH: CURRENT_SEQUENCE,
    }


@pytest.fixture
def fake_diagram_llm(monkeypatch):
    """Stub the diagram editor's `call_llm` (on `d2_gate`)."""
    state = {"reply": UPDATED_D2, "calls": []}

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
    """Stub the ADR editor's `call_llm` (its own seam on `architecture_refinement`)."""
    state = {"reply": UPDATED_ADR, "calls": []}

    async def _call_llm(messages, **_kwargs):
        state["calls"].append(messages)
        reply = state["reply"]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(architecture_refinement, "call_llm", _call_llm)
    return state


@pytest.fixture(autouse=True)
def fake_compile(monkeypatch):
    """Stub `compile_d2` (on `d2_gate`); every call compiles."""
    state = {"calls": []}

    async def _compile_d2(src):
        state["calls"].append(src)
        return D2CompileResult(ok=True)

    monkeypatch.setattr(d2_gate, "compile_d2", _compile_d2)
    return state


@pytest.fixture(autouse=True)
def stub_validator(monkeypatch):
    """Stub the coherence validator's `call_llm`, defaulting to `VALID`."""
    state = {"value": "VALID", "calls": []}

    async def _call_llm(messages, **_kwargs):
        state["calls"].append(messages)
        value = state["value"]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(d2_validator, "call_llm", _call_llm)
    return state


def _composed(fake_diagram_llm) -> str:
    """The composed diagram-refine turn the editor saw (its last user message)."""
    return fake_diagram_llm["calls"][0][-1]["content"]


# --- default target: the sequence diagram ------------------------------------


@pytest.mark.usefixtures("fake_diagram_llm")
async def test_no_target_defaults_to_the_sequence_diagram():
    artifacts = _artifacts()

    response = await refine_architecture([], "rename `user` to Browser", prd=PRD, artifacts=artifacts)

    assert isinstance(response, LLMResponse)
    # Only the sequence diagram changed; every other artifact is carried verbatim.
    assert response.artifacts[SEQUENCE_PATH] == UPDATED_D2
    assert response.artifacts[CONTEXT_PATH] == CONTEXT_D2
    assert response.artifacts[ADR_PATH] == artifacts[ADR_PATH]
    # The single-diagram mirror follows the sequence edit.
    assert response.diagram_d2 == UPDATED_D2
    assert response.next_phase is None
    assert response.warning is None
    assert "sequence diagram" in response.text
    assert "4 interactions" in response.text


@pytest.mark.usefixtures("fake_diagram_llm")
async def test_input_map_is_not_mutated():
    artifacts = _artifacts()

    await refine_architecture([], "rename `user`", prd=PRD, artifacts=artifacts)

    # The engine returns a new map; the caller's dict is untouched (the JSON column
    # tracks the reassignment the endpoint makes, not an in-place mutation).
    assert artifacts[SEQUENCE_PATH] == CURRENT_SEQUENCE


# --- explicit diagram target -------------------------------------------------


async def test_explicit_diagram_target_is_edited(fake_diagram_llm):
    artifacts = _artifacts()
    fake_diagram_llm["reply"] = "direction: right\nuser: End User {shape: person}\napp: App\nuser -> app: opens"

    response = await refine_architecture(
        [], "relabel the edge", prd=PRD, artifacts=artifacts, target_artifact=CONTEXT_PATH
    )

    # The context diagram changed; the sequence diagram (and its mirror) did not.
    assert response.artifacts[CONTEXT_PATH] == fake_diagram_llm["reply"]
    assert response.artifacts[SEQUENCE_PATH] == CURRENT_SEQUENCE
    assert response.diagram_d2 == CURRENT_SEQUENCE
    assert "system context diagram" in response.text
    # The turn told the editor which diagram it is editing.
    composed = _composed(fake_diagram_llm)
    assert CONTEXT_PATH in composed
    assert "user -> app: uses" in composed  # the current context source, not the sequence


@pytest.mark.usefixtures("fake_diagram_llm")
async def test_unknown_target_falls_back_to_sequence():
    artifacts = _artifacts()

    response = await refine_architecture(
        [], "change it", prd=PRD, artifacts=artifacts, target_artifact="diagrams/does-not-exist.d2"
    )

    assert response.artifacts[SEQUENCE_PATH] == UPDATED_D2
    assert response.diagram_d2 == UPDATED_D2


# --- ADR target --------------------------------------------------------------


async def test_adr_target_edits_markdown_without_compile_or_warning(fake_adr_llm, fake_compile, stub_validator):
    artifacts = _artifacts()

    response = await refine_architecture(
        [], "add a risks section", prd=PRD, artifacts=artifacts, target_artifact=ADR_PATH
    )

    assert response.artifacts[ADR_PATH] == UPDATED_ADR
    # Editing the ADR (Markdown) skips the D2 compile gate and the coherence check.
    assert fake_compile["calls"] == []
    assert stub_validator["calls"] == []
    assert response.warning is None
    # The sequence mirror is unchanged.
    assert response.diagram_d2 == CURRENT_SEQUENCE
    # The ADR editor turn carries the current ADR and asks for Markdown.
    adr_turn = fake_adr_llm["calls"][0][-1]["content"]
    assert "## Current ADR (Markdown)" in adr_turn
    assert "A todo app." in adr_turn


async def test_empty_adr_reply_raises(fake_adr_llm):
    artifacts = _artifacts()
    fake_adr_llm["reply"] = "   "

    with pytest.raises(LLMConnectionError, match="empty ADR"):
        await refine_architecture([], "edit it", prd=PRD, artifacts=artifacts, target_artifact=ADR_PATH)


# --- anchors + coherence -----------------------------------------------------


async def test_anchor_ids_are_surfaced_to_the_editor(fake_diagram_llm):
    artifacts = _artifacts()

    await refine_architecture([], "rename `user` to Browser", prd=PRD, artifacts=artifacts)

    composed = _composed(fake_diagram_llm)
    assert "Referenced elements" in composed
    assert "`user`" in composed
    assert "A todo app for individuals." in composed  # the PRD rides along


@pytest.mark.usefixtures("fake_diagram_llm")
async def test_diagram_contradiction_surfaces_as_warning(stub_validator):
    artifacts = _artifacts()
    stub_validator["value"] = "WARNING: the edit drops the Database the spec requires"

    response = await refine_architecture([], "rename `user`", prd=PRD, artifacts=artifacts)

    # The edit still lands; the warning is advisory.
    assert response.artifacts[SEQUENCE_PATH] == UPDATED_D2
    assert response.warning is not None
    assert "drops the Database the spec requires" in response.warning
