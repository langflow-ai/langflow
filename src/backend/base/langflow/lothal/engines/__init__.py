"""Built-in phase engines for the Lothal router (Epic 0, Story 0.3 seam).

Each phase's engine lives in its own module here and self-registers via
`@register_engine` (see `langflow.lothal.router`). Importing this package
imports those modules, so the router's `process_turn` can route to them.

As each engine lands, add its import below so registration runs on import of
this package (the router imports it last, after its names are defined).
"""

from langflow.lothal.engines import (
    clarification,  # noqa: F401  -- registers the CLARIFICATION engine
    diagram_generation,  # noqa: F401  -- registers the DIAGRAM_GENERATION engine
    diagram_refinement,  # noqa: F401  -- registers the DIAGRAM_REFINEMENT engine
)
