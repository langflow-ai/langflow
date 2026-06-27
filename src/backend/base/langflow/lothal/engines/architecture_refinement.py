"""Architecture-stage *refinement*: edit one artifact in the existing map (Epic E.3).

Once the artifact set exists (the `ArchitectureEngine` dispatches here whenever
`artifacts` is populated), the user iterates on it in conversation. With four
diagrams plus the ADR, each refine turn edits **one** artifact — the active one
the user is looking at — so the turn carries a `target_artifact` key (the chat
endpoint threads it from the request; it defaults to the sequence diagram, which
is what the single-diagram canvas still shows). The engine feeds the editor only
that artifact's current source and writes the result back into a copy of the map,
leaving the other artifacts untouched.

A `.d2` target is edited by the generic D2 editor and run through the shared D.3
compile gate (`compile_validated_d2`, one corrective retry) and the advisory D.10
coherence check (`validate_d2_against_prd`); `adr.md` is Markdown, edited by the
ADR editor with no compile/coherence gate. As in generation, the sequence diagram
is mirrored onto `diagram_d2` so the single-diagram read/approve flow stays
correct. `next_phase` stays `None` — refining keeps the project in `ARCHITECTURE`;
approval (→ `CODE_GENERATION`) is the `/diagram/approve` endpoint. Pure turn
logic; the endpoint owns persistence.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from langflow.lothal.context import build_messages
from langflow.lothal.engines.architecture_artifacts import (
    ADR_EDITOR_SYSTEM_PROMPT,
    D2_EDITOR_SYSTEM_PROMPT,
    SEQUENCE_PATH,
    artifact_label,
)
from langflow.lothal.engines.d2_gate import compile_validated_d2, count_messages
from langflow.lothal.engines.d2_validator import validate_d2_against_prd
from langflow.lothal.engines.parsing import strip_code_fences
from langflow.lothal.llm import LLMConnectionError, call_llm
from langflow.lothal.router import LLMResponse

if TYPE_CHECKING:
    from langflow.services.database.models.lothal_project.model import Message

# A diagram element reference the D.7 composer serialises into the message: an
# exact D2 id wrapped in backticks (e.g. `user`, `api -> db #2`). Surfaced
# explicitly so the editor can't miss an anchor buried in the prose.
_ANCHOR_RE = re.compile(r"`([^`]+)`")


def _resolve_target(target_artifact: str | None, artifacts: dict[str, str]) -> str:
    """Pick the artifact to edit: the requested one if present, else the sequence diagram.

    The sequence diagram is the default because it is what the single-diagram
    canvas/read still shows (it mirrors `diagram_d2`), so a refine turn that
    doesn't name a target (e.g. before the multi-diagram frontend lands, E.5)
    edits the artifact the user is actually looking at. A requested target that
    isn't in the map falls back the same way rather than erroring.
    """
    if target_artifact and target_artifact in artifacts:
        return target_artifact
    if SEQUENCE_PATH in artifacts:
        return SEQUENCE_PATH
    # No sequence diagram (a partial/legacy map) — edit whatever is first so the
    # turn still does something rather than failing on an empty target.
    return next(iter(artifacts))


def _referenced_ids(instruction: str) -> list[str]:
    """The backtick-wrapped element ids in the instruction, de-duplicated in order."""
    seen: dict[str, None] = {}
    for match in _ANCHOR_RE.findall(instruction):
        token = match.strip()
        if token:
            seen.setdefault(token, None)
    return list(seen)


def _compose_diagram_turn(prd: str | None, target: str, current: str, instruction: str) -> str:
    """Build the diagram refine turn: PRD + which diagram + current D2 + anchors + instruction."""
    sections: list[str] = []
    if prd and prd.strip():
        sections.append(f"## Product spec (PRD)\n{prd.strip()}")
    sections.append(f"## Editing\nThe {artifact_label(target)} (`{target}`).")
    diagram = current.strip() if current and current.strip() else "(the diagram is empty)"
    sections.append(f"## Current diagram (D2)\n{diagram}")
    anchors = _referenced_ids(instruction)
    if anchors:
        sections.append("## Referenced elements\n" + "\n".join(f"- `{a}`" for a in anchors))
    sections.append(f"## Instruction\n{instruction.strip()}")
    return "\n\n".join(sections)


def _compose_adr_turn(prd: str | None, current: str, instruction: str) -> str:
    """Build the ADR refine turn: PRD + current ADR Markdown + instruction."""
    sections: list[str] = []
    if prd and prd.strip():
        sections.append(f"## Product spec (PRD)\n{prd.strip()}")
    adr = current.strip() if current and current.strip() else "(the ADR is empty)"
    sections.append(f"## Current ADR (Markdown)\n{adr}")
    sections.append(f"## Instruction\n{instruction.strip()}")
    return "\n\n".join(sections)


def _diagram_text(target: str, d2: str) -> str:
    """Human-facing reply for a diagram edit, grounded in its interaction count."""
    label = artifact_label(target)
    messages = count_messages(d2)
    if messages:
        return (
            f"I've updated the {label} — it now has {messages} interactions. Tell me what else to "
            "change, or approve the architecture to generate the code."
        )
    return f"I've updated the {label}. Tell me what else to change, or approve the architecture to generate the code."


async def _refine_diagram(
    history: list[Message], target: str, current: str, prd: str | None, instruction: str
) -> tuple[str, str | None]:
    """Edit one diagram through the compile gate + advisory coherence check. Returns `(d2, warning)`."""
    composed = _compose_diagram_turn(prd, target, current, instruction)
    messages = build_messages(D2_EDITOR_SYSTEM_PROMPT, history, composed)
    d2 = await compile_validated_d2(messages)
    warning = await validate_d2_against_prd(prd, d2)
    return d2, warning


async def _refine_adr(history: list[Message], current: str, prd: str | None, instruction: str) -> str:
    """Edit the ADR Markdown. No compile/coherence gate; an empty reply is a 502."""
    composed = _compose_adr_turn(prd, current, instruction)
    messages = build_messages(ADR_EDITOR_SYSTEM_PROMPT, history, composed)
    raw = await call_llm(messages)
    adr = strip_code_fences(raw).strip()
    if not adr:
        msg = "Model returned an empty ADR."
        raise LLMConnectionError(msg)
    return adr


async def refine_architecture(
    history: list[Message],
    user_message: str,
    *,
    prd: str | None = None,
    artifacts: dict[str, str],
    target_artifact: str | None = None,
) -> LLMResponse:
    """Apply the user's instruction to one artifact in the map and return the updated map.

    Resolves which artifact the turn targets, edits just that one (the rest are
    carried verbatim), re-validates a diagram edit, and mirrors the sequence
    diagram onto `diagram_d2`. `next_phase` stays `None` (refining keeps the
    project in `ARCHITECTURE`).
    """
    target = _resolve_target(target_artifact, artifacts)
    current = artifacts.get(target, "")

    if target.endswith(".d2"):
        new_source, warning = await _refine_diagram(history, target, current, prd, user_message)
        text = _diagram_text(target, new_source)
    else:
        new_source = await _refine_adr(history, current, prd, user_message)
        warning = None
        text = (
            f"I've updated the {artifact_label(target)}. Tell me what else to change, or approve "
            "the architecture to generate the code."
        )

    updated = {**artifacts, target: new_source}
    return LLMResponse(
        text=text,
        suggestions=[],
        next_phase=None,
        # Keep the single-diagram mirror in sync with the sequence diagram (the
        # one `GET /diagram` shows), whether or not this turn edited it.
        diagram_d2=updated.get(SEQUENCE_PATH),
        artifacts=updated,
        warning=warning,
    )
