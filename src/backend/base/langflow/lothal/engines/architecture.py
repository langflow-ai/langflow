"""The `ARCHITECTURE` phase engine — the merged diagram stage (Epic E.2, grown in E.3).

Epic E collapsed the old `DIAGRAM_GENERATION` and `DIAGRAM_REFINEMENT` phases into
a single `ARCHITECTURE` stage, and E.3 grew its output from one diagram into the
full **artifact map**: an ADR plus a fixed set of D2 diagrams (`adr.md`,
`diagrams/{context,container,data-model,sequence}.d2`), stored in
`lothal_project.artifacts`. One engine owns the whole stage and dispatches each
turn on whether that map exists yet:

- **no artifacts yet** → *generate* the full ADR + diagram set from the clarified
  spec (`architecture_generation.generate_architecture`);
- **artifacts exist** → *refine* one artifact of the map with the user's
  instruction (`architecture_refinement.refine_architecture`).

The entry condition keys off `artifacts` (E.3 re-keyed it from E.2's single
`current_d2`). There is no auto-advance: generation returns `next_phase=None`, so
the project stays in `ARCHITECTURE` and the following turn refines the set the
user is looking at. Leaving `ARCHITECTURE` happens only when the user approves
(`POST /diagram/approve` → `CODE_GENERATION`).

Both paths also mirror the sequence diagram onto `LLMResponse.diagram_d2` so the
single-diagram read/approve flow keeps working until the multi-diagram read
endpoints land (E.4). Like every engine this one is pure turn logic and never
touches the DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.lothal.engines.architecture_generation import generate_architecture
from langflow.lothal.engines.architecture_refinement import refine_architecture
from langflow.lothal.router import LLMResponse, PhaseEngine, register_engine
from langflow.services.database.models.lothal_project.model import ProjectPhase

if TYPE_CHECKING:
    from langflow.services.database.models.lothal_project.model import Message


@register_engine
class ArchitectureEngine(PhaseEngine):
    """Generates the full artifact set on stage entry, then refines one artifact per later turn."""

    phase = ProjectPhase.ARCHITECTURE

    async def process(
        self,
        history: list[Message],
        user_message: str,
        *,
        prd: str | None = None,
        artifacts: dict[str, str] | None = None,
        target_artifact: str | None = None,
        **_kwargs,
    ) -> LLMResponse:
        # `**_kwargs` absorbs `current_d2` (the E.2 single-diagram store): E.3
        # re-keys the stage on the artifact map, so the single diagram no longer
        # drives the generate-vs-refine decision.
        #
        # First turn of the stage (no artifact map yet) → generate the whole set;
        # otherwise the user is iterating on it → refine the active artifact. An
        # empty map counts as "not generated yet".
        if not artifacts:
            return await generate_architecture(history, user_message, prd=prd)
        return await refine_architecture(
            history, user_message, prd=prd, artifacts=artifacts, target_artifact=target_artifact
        )
