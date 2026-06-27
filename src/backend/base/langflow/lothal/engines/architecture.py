"""The `ARCHITECTURE` phase engine — the merged diagram stage (Epic E.2).

Epic E collapses the old `DIAGRAM_GENERATION` and `DIAGRAM_REFINEMENT` phases into
a single `ARCHITECTURE` stage. One engine owns the whole stage and dispatches each
turn on whether the project already has a diagram:

- **no diagram yet** → *generate* the first diagram from the clarified spec
  (delegates to `DiagramGenerationEngine`);
- **a diagram exists** → *refine* it with the user's instruction (delegates to
  `DiagramRefinementEngine`).

There is no auto-advance between the two: generation now returns `next_phase=None`,
so the project simply stays in `ARCHITECTURE` and the following turn refines the
diagram the user is looking at. Leaving `ARCHITECTURE` happens only when the user
approves (`POST /diagram/approve` → `CODE_GENERATION`).

The entry condition here keys off `current_d2` because the E.2 artifact is still a
single D2 diagram (`lothal_project.diagram_d2`). Epic E.3 swaps this for the full
artifact map (ADR + a set of D2 diagrams) and re-keys the condition off
`artifacts`; the generate-vs-refine dispatch stays the same shape. Like every
engine this one is pure turn logic and never touches the DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.lothal.engines.diagram_generation import DiagramGenerationEngine
from langflow.lothal.engines.diagram_refinement import DiagramRefinementEngine
from langflow.lothal.router import LLMResponse, PhaseEngine, register_engine
from langflow.services.database.models.lothal_project.model import ProjectPhase

if TYPE_CHECKING:
    from langflow.services.database.models.lothal_project.model import Message


@register_engine
class ArchitectureEngine(PhaseEngine):
    """Generates the first diagram on stage entry, then refines it on every later turn."""

    phase = ProjectPhase.ARCHITECTURE

    def __init__(self) -> None:
        # The two delegates are pure turn logic with no per-turn state, so a single
        # instance of each is reused across turns (mirrors how `get_engine` caches
        # one engine instance per phase).
        self._generation = DiagramGenerationEngine()
        self._refinement = DiagramRefinementEngine()

    async def process(
        self,
        history: list[Message],
        user_message: str,
        *,
        prd: str | None = None,
        current_d2: str | None = None,
    ) -> LLMResponse:
        # First turn of the stage (no diagram drafted yet) → generate; otherwise the
        # user is iterating on an existing diagram → refine. A blank/whitespace-only
        # store counts as "no diagram" (same normalisation `GET /diagram` applies).
        if not (current_d2 and current_d2.strip()):
            return await self._generation.process(history, user_message, prd=prd, current_d2=current_d2)
        return await self._refinement.process(history, user_message, prd=prd, current_d2=current_d2)
