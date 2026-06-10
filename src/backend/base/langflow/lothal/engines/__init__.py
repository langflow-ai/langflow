"""Built-in phase engines for the Lothal router (Epic 0, Story 0.3 seam).

Each phase's engine lives in its own module here and self-registers via
`@register_engine` (see `langflow.lothal.router`). Importing this package
imports those modules, so the router's `process_turn` can route to them.

No engines ship in Epic 0 — the router is pure infrastructure until Epic 1
adds the `CLARIFICATION` engine and onward. As each engine lands, add its
import below so registration runs::

    from langflow.lothal.engines import clarification  # noqa: F401
"""
