"""The canonical Architecture-stage artifact set and its prompts (Epic E.3a).

`architecture_artifacts` is the single source of the fixed five-artifact map (one
ADR + four D2 diagrams) and the prompts that generate and refine it. These tests
pin the shape of that set and the prompt invariants every generated diagram must
carry — the same guards the retired single-diagram engines used to hold, now
asserted against the live module after Epic E.6.

The most important is the D.14 layout pin: D2 owns layout and the model must emit
no positions, so the position-repair fallback (`auto_layout`, Story 2.5) stays
obsolete. Pinning it on the live diagram and editor prompts stops a future edit
from quietly reintroducing position output and reviving that need.
"""

from langflow.lothal.engines import architecture_artifacts as aa
from langflow.lothal.engines.architecture_artifacts import (
    ADR_PATH,
    CONTAINER_PATH,
    CONTEXT_PATH,
    DATA_MODEL_PATH,
    DIAGRAM_SPECS,
    SEQUENCE_PATH,
    artifact_label,
)


def test_diagram_specs_are_the_four_canonical_diagrams_in_order():
    # The generation engine iterates this and the refinement engine routes against
    # it; the order is the generation order (context → container → data → sequence).
    assert [spec.path for spec in DIAGRAM_SPECS] == [
        CONTEXT_PATH,
        CONTAINER_PATH,
        DATA_MODEL_PATH,
        SEQUENCE_PATH,
    ]
    # The ADR is Markdown, not a D2 diagram, so it is not in the diagram set.
    assert ADR_PATH not in {spec.path for spec in DIAGRAM_SPECS}


def test_every_diagram_prompt_carries_the_shared_d2_output_contract():
    # The contract is appended once to each diagram body so the four can't drift.
    for spec in DIAGRAM_SPECS:
        assert aa.D2_OUTPUT_CONTRACT in spec.system_prompt


def test_diagram_prompts_forbid_positions_so_auto_layout_stays_obsolete():
    """D.14: the diagram prompts must forbid positions (D2 owns layout)."""
    contract = aa.D2_OUTPUT_CONTRACT.lower()
    assert "d2 owns layout" in contract
    assert "never write positions" in contract
    # Carried by every generated diagram, not just the shared contract in isolation.
    for spec in DIAGRAM_SPECS:
        assert "never write positions" in spec.system_prompt.lower()


def test_d2_editor_prompt_forbids_positions_and_fences():
    """The refinement editor edits in place and must keep the same layout/output pins."""
    editor = aa.D2_EDITOR_SYSTEM_PROMPT.lower()
    assert "never write positions" in editor
    assert "no markdown fences" in editor


def test_diagram_prompts_request_d2_source_only():
    # Generation feeds replies straight through the compile gate, which only strips a
    # stray fence — so the prompt must ask for bare D2, no prose or diff markers.
    contract = aa.D2_OUTPUT_CONTRACT.lower()
    assert "no markdown fences" in contract
    assert "d2 source and nothing else" in contract


def test_adr_prompt_is_markdown_and_skips_the_d2_contract():
    prompt = aa.ADR_SYSTEM_PROMPT
    assert "Markdown" in prompt
    # The ADR is not a diagram, so the D2 output contract is not appended to it.
    assert aa.D2_OUTPUT_CONTRACT not in prompt


def test_artifact_label_is_readable_and_falls_back_to_the_path():
    assert artifact_label(ADR_PATH) == "architecture decision record"
    assert artifact_label(SEQUENCE_PATH) == "sequence diagram"
    # An unknown path falls back to itself rather than raising.
    assert artifact_label("diagrams/unknown.d2") == "diagrams/unknown.d2"
