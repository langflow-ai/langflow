"""Diagram *refinement* logic for the ARCHITECTURE stage (Epic D.8; merged in Epic E.2).

Once the first diagram is drafted (the `ArchitectureEngine` delegates here once a
diagram exists), the user iterates on it in conversation. Each turn the engine
receives the **current D2**,
the **PRD**, and the user's instruction — which may reference specific diagram
elements by their exact D2 id (the click-to-anchor composer, Epic D.7, serialises
a referenced element as a backtick-wrapped id inline in the message, e.g.
"rename `user` to browser"). The model is the generic editor: it applies the
instruction to the current D2 and returns the **complete updated D2**, which is
compile-validated (the shared D.3 gate, with one corrective retry) and carried on
`LLMResponse.diagram_d2` for the chat endpoint to persist to
`lothal_project.diagram_d2`. `GET /diagram` then reflects the edit.

`next_phase` stays `None` — refining keeps the project in `ARCHITECTURE`;
approving the diagram (→ `CODE_GENERATION`) is the `/diagram/approve` endpoint.
Like every engine this one is pure turn logic and never touches the DB (the
endpoint owns persistence); it reads the current D2 and PRD from the keyword
arguments the chat endpoint threads through from the project row.

This class is no longer registered directly; the `ArchitectureEngine`
(`architecture.py`) owns the `ARCHITECTURE` phase and delegates the refine turn
here once a diagram exists.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from langflow.lothal.context import build_messages
from langflow.lothal.engines.d2_gate import compile_validated_d2, count_messages
from langflow.lothal.engines.d2_validator import validate_d2_against_prd
from langflow.lothal.router import LLMResponse, PhaseEngine

if TYPE_CHECKING:
    from langflow.services.database.models.lothal_project.model import Message

SYSTEM_PROMPT = """\
You are Lothal's diagram editor. You maintain one D2 diagram (D2 is the text \
diagramming language at d2lang.com) for the user's application. Each turn you are \
given the product spec (PRD), the CURRENT D2 source, optionally a list of \
referenced elements (their exact D2 ids), and an instruction. Apply the \
instruction to the current diagram and reply with the COMPLETE updated D2 source \
— the whole diagram, never a fragment, a diff, or commentary.

Rules:
- Edit the current D2 in place. Keep every participant, message, and detail the \
instruction does not ask you to change — do not restructure, reorder, or rename \
anything you were not asked to.
- When the instruction references elements (listed under "Referenced elements" \
and wrapped in backticks), those backtick-wrapped tokens are the exact D2 ids to \
act on — not free text to add to a label. A connection id may carry a ` #N` \
suffix when several edges share the same endpoints; act on that specific Nth \
edge, leaving the others untouched.
- Stay faithful to the PRD: the diagram must keep describing the same application.
- Preserve the diagram's `shape:` header and the `id: Label` / \
`source -> target: label` structure. Use stable, lowercase, hyphen-free ids.
- D2 owns layout: never write positions, coordinates, or `near`/`width`/`height`.
- Emit raw D2 source only — no markdown fences, no prose, no diff markers.
"""

# A diagram element reference the D.7 composer serialises into the message: an
# exact D2 id wrapped in backticks (e.g. `user`, `api -> db #2`). Pulled out so
# the turn can list them explicitly for the model, on top of leaving them inline.
_ANCHOR_RE = re.compile(r"`([^`]+)`")


def _referenced_ids(instruction: str) -> list[str]:
    """The backtick-wrapped element ids in the instruction, de-duplicated in order."""
    seen: dict[str, None] = {}
    for match in _ANCHOR_RE.findall(instruction):
        token = match.strip()
        if token:
            seen.setdefault(token, None)
    return list(seen)


def _compose_turn(prd: str | None, current_d2: str | None, instruction: str) -> str:
    """Build the refinement turn the model edits: PRD + current D2 + anchors + instruction.

    The current D2 is the authoritative state to edit (the conversation history
    carries the raw instructions for continuity, but not the evolving D2), so it
    is always restated here. Referenced element ids are surfaced explicitly so the
    model can't miss an anchor buried in the prose.
    """
    sections: list[str] = []
    if prd and prd.strip():
        sections.append(f"## Product spec (PRD)\n{prd.strip()}")
    diagram = current_d2.strip() if current_d2 and current_d2.strip() else "(the diagram is empty)"
    sections.append(f"## Current diagram (D2)\n{diagram}")
    anchors = _referenced_ids(instruction)
    if anchors:
        sections.append("## Referenced elements\n" + "\n".join(f"- `{a}`" for a in anchors))
    sections.append(f"## Instruction\n{instruction.strip()}")
    return "\n\n".join(sections)


def _assistant_text(d2: str) -> str:
    """The human-facing reply stored alongside the refined D2, grounded in its size."""
    messages = count_messages(d2)
    if messages:
        return (
            f"I've updated the diagram — it now has {messages} interactions. "
            f"Tell me what else to add, remove, or change, or approve it to generate the code."
        )
    return "I've updated the diagram. Tell me what else to change, or approve it to generate the code."


class DiagramRefinementEngine(PhaseEngine):
    """Applies an anchored (or free-text) instruction to the current D2 and returns the updated source.

    Not registered for a phase of its own (Epic E.2 merged the diagram phases) —
    the `ArchitectureEngine` delegates here once the project has a diagram.
    """

    async def process(
        self,
        history: list[Message],
        user_message: str,
        *,
        prd: str | None = None,
        current_d2: str | None = None,
    ) -> LLMResponse:
        composed = _compose_turn(prd, current_d2, user_message)
        messages = build_messages(SYSTEM_PROMPT, history, composed)
        d2 = await compile_validated_d2(messages)
        # D.10: the edit compiles (D.3 gate) — now check it didn't drift from the
        # spec. A contradiction becomes a user-facing warning the chat endpoint
        # stores as its own message; a coherent edit yields `None` (no message).
        # Advisory only: `validate_d2_against_prd` swallows every fault and returns
        # `None`, so it never raises here — the verdict can't block the compiled
        # edit from being returned (and then persisted by the endpoint).
        warning = await validate_d2_against_prd(prd, d2)
        # Refining keeps the project in ARCHITECTURE; approval (→ CODE_GENERATION) is the approve endpoint.
        return LLMResponse(text=_assistant_text(d2), suggestions=[], next_phase=None, diagram_d2=d2, warning=warning)
