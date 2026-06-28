"""Architecture-stage *generation*: the full ADR + diagram-set artifact map (Epic E.3).

Once clarification produces a PRD and the project enters `ARCHITECTURE`, the first
turn generates the whole artifact set in one pass — the ADR plus the four D2
diagrams fixed in `architecture_artifacts.py` (E.3a) — and returns it as the
`{path: content}` map on `LLMResponse.artifacts` for the chat endpoint to persist
to `lothal_project.artifacts`. The sequence diagram is also mirrored onto
`LLMResponse.diagram_d2` so the single-diagram read/approve flow keeps working
until the multi-diagram read endpoints land (E.4).

Each diagram goes through the shared D.3 compile gate (`compile_validated_d2`, one
corrective retry) and then the advisory D.10 coherence check
(`validate_d2_against_prd`) — a contradiction becomes a user-facing warning, never
a hard failure. The ADR is Markdown, so it skips both gates; an empty ADR reply is
a bad model round-trip (`LLMConnectionError` → 502), the same way the D2 gate
treats an empty diagram.

The five model round-trips (four diagrams + the ADR) are independent, so they run
concurrently (`asyncio.gather`) rather than serially — architecture generation is
a heavy, infrequent operation and the latency would otherwise stack. Like every
engine this is pure turn logic and never touches the DB.

`call_llm` is a module-level name here (not re-resolved per call) so a test can
monkeypatch the ADR's model round-trip independently of the diagrams' (which drive
`d2_gate.call_llm`) and the coherence checks' (`d2_validator.call_llm`).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from langflow.lothal.context import build_messages
from langflow.lothal.engines.architecture_artifacts import (
    ADR_PATH,
    ADR_SYSTEM_PROMPT,
    DIAGRAM_SPECS,
    SEQUENCE_PATH,
    artifact_label,
)
from langflow.lothal.engines.d2_gate import compile_validated_d2
from langflow.lothal.engines.d2_validator import validate_d2_against_prd
from langflow.lothal.engines.parsing import strip_code_fences
from langflow.lothal.llm import LLMConnectionError, call_llm
from langflow.lothal.router import LLMResponse

if TYPE_CHECKING:
    from langflow.lothal.engines.architecture_artifacts import DiagramSpec
    from langflow.services.database.models.lothal_project.model import Message


def _compose_generation_turn(prd: str | None, instruction: str) -> str:
    """Build the generation turn: the PRD restated as a labelled block + the instruction.

    The full clarification conversation (and the PRD, which is its last assistant
    turn) already rides in `history`, but the PRD is restated here as the
    distilled, confirmed anchor so generation stays robust if history is ever
    truncated for a long conversation (mirrors `diagram_refinement._compose_turn`).
    """
    sections: list[str] = []
    if prd and prd.strip():
        sections.append(f"## Product spec (PRD)\n{prd.strip()}")
    sections.append(f"## Instruction\n{instruction.strip()}")
    return "\n\n".join(sections)


async def _generate_diagram(
    spec: DiagramSpec, history: list[Message], turn: str, prd: str | None
) -> tuple[str, str, str | None]:
    """Generate one diagram: compile-validate it, then coherence-check it (advisory).

    Returns `(path, d2, warning)` — the warning is `None` when the diagram is
    coherent with the PRD, or for an empty PRD (the validator no-ops).
    """
    messages = build_messages(spec.system_prompt, history, turn)
    d2 = await compile_validated_d2(messages)
    warning = await validate_d2_against_prd(prd, d2)
    return spec.path, d2, warning


async def _generate_adr(history: list[Message], turn: str) -> str:
    """Generate the ADR Markdown. No compile/coherence gate; an empty reply is a 502."""
    messages = build_messages(ADR_SYSTEM_PROMPT, history, turn)
    raw = await call_llm(messages)
    adr = strip_code_fences(raw).strip()
    if not adr:
        msg = "Model returned an empty ADR."
        raise LLMConnectionError(msg)
    return adr


def _combine_warnings(warnings: list[tuple[str, str]]) -> str | None:
    """Join per-diagram coherence warnings into one message, labelled by diagram.

    `warnings` is `(path, warning)` for each diagram that flagged a contradiction;
    returns `None` when none did, so a clean generation adds no warning message.
    """
    if not warnings:
        return None
    return "\n\n".join(f"{artifact_label(path)}: {warning}" for path, warning in warnings)


def _generation_text(diagram_count: int) -> str:
    """The human-facing reply for a generation turn, grounded in the artifact set."""
    return (
        f"I've drafted the architecture: an ADR plus {diagram_count} diagrams — the system "
        "context, the containers, the data model, and the core runtime sequence. Review them on "
        "the canvas and tell me what to refine, or approve to generate the code."
    )


async def generate_architecture(history: list[Message], user_message: str, *, prd: str | None = None) -> LLMResponse:
    """Generate the whole `{adr.md, diagrams/*}` artifact map for a fresh ARCHITECTURE stage.

    Runs the four diagram generations and the ADR generation concurrently, then
    assembles the artifact map, mirrors the sequence diagram onto `diagram_d2`,
    and folds any per-diagram coherence warnings into a single advisory message.
    `next_phase` is `None`: the project stays in `ARCHITECTURE` and the next turn
    refines this set (the engine dispatches generate-vs-refine on whether
    `artifacts` exists). Never persists — the chat endpoint owns that.
    """
    turn = _compose_generation_turn(prd, user_message)

    # Independent round-trips → run them together. gather preserves argument order,
    # so the diagram results line up with DIAGRAM_SPECS.
    adr, *diagram_results = await asyncio.gather(
        _generate_adr(history, turn),
        *(_generate_diagram(spec, history, turn, prd) for spec in DIAGRAM_SPECS),
    )

    artifacts: dict[str, str] = {ADR_PATH: adr}
    warnings: list[tuple[str, str]] = []
    for path, d2, warning in diagram_results:
        artifacts[path] = d2
        if warning is not None:
            warnings.append((path, warning))

    diagram_count = len(diagram_results)
    return LLMResponse(
        text=_generation_text(diagram_count),
        suggestions=[],
        next_phase=None,
        # Mirror the sequence diagram onto the single-diagram store so `GET /diagram`
        # and `/diagram/approve` keep working until the E.4 read endpoints land.
        diagram_d2=artifacts[SEQUENCE_PATH],
        artifacts=artifacts,
        warning=_combine_warnings(warnings),
    )
