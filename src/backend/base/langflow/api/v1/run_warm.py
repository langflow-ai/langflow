"""Warm fast-path for v1 flow runs (webhook / /run / MCP).

``simple_run_flow`` normally rebuilds the graph with ``Graph.from_payload`` on every
request. Under the production deployment profile we can instead serve a **deepcopy of
a pre-built template** from the warm registry and apply per-request identity to the
copy — the same trick the v2 workflow host uses — which removes the per-request
``from_payload`` (CPU) and the flow-row read (DB pool checkout).

Core model: warm deepcopy + set-values. We fall back to the normal cold rebuild only
when the per-request work can't be layered onto a shared template:

- **not prod** — feature off; behave exactly as before.
- **tweaks present** — tweaks mutate the payload before build; no post-build applier
  exists, so rebuild.
- **context present** — the template was built context-free.
- **auto-bindable globals** — a flow with an empty, global-eligible str field may need
  the per-user ``apply_global_variable_defaults`` binding, which is NOT in the stored
  flow.data (only added at run time). Detectable statically from flow.data, so we
  cold-fall-back for those flows. (Explicit ``load_from_db`` fields ARE in flow.data and
  work warm; ``apply_run_defaults`` threads the run's user_id so they resolve per-user.)
- **HITL flow** — a v1 run of a HITL flow is rejected by the cold path; let it.
- **cache miss / store unavailable** — let the cold path do its own DB read + errors.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from langflow.api.v1.global_variable_defaults import _is_eligible_field
from langflow.api.v1.run_validation import flow_requires_hitl

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph

    from langflow.api.v1.schemas import SimplifiedAPIRequest
    from langflow.services.database.models.flow.model import Flow


def _flow_needs_auto_globals(data: dict | None) -> bool:
    """True if the flow has any field an auto-bound global variable COULD target.

    Conservative over-approximation (we don't know the caller's variables here): if the
    flow has at least one empty, global-eligible str field with a display_name, some
    user's variable ``default_fields`` might auto-bind it at run time — so that flow must
    take the cold path. If there is no such field, no auto-binding is possible for anyone
    and the warm template is complete.
    """
    for node in (data or {}).get("nodes", []):
        if not isinstance(node, dict):
            continue
        template = (node.get("data") or {}).get("node", {}).get("template")
        if not isinstance(template, dict):
            continue
        for field_name, field in template.items():
            if field_name == "_type":
                continue
            if _is_eligible_field(field) and isinstance(field.get("display_name"), str):
                return True
    return False


async def try_warm_run_graph(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    *,
    user_id: Any,
    context: dict | None,
) -> Graph | None:
    """Return a run-ready deepcopy from the warm registry, or ``None`` to use cold rebuild.

    See the module docstring for the fall-back conditions. When a graph is returned it
    already carries the flow's structure (built at warm time) plus this run's
    ``user_id``/``session_id`` (applied to the copy); the caller continues exactly as it
    would with a freshly-built graph.
    """
    from lfx.run._defaults import apply_run_defaults

    from langflow.api.v2.host_selection import is_prod_deployment
    from langflow.services.deps import get_settings_service
    from langflow.services.warm_registry.reconcile import warm_one
    from langflow.services.warm_registry.service import FlowStoreUnavailableError, get_warm_registry

    if not is_prod_deployment(get_settings_service().settings):
        return None
    if input_request.tweaks or context is not None:
        return None
    data = flow.data or {}
    if _flow_needs_auto_globals(data) or flow_requires_hitl(data):
        return None

    flow_id_str = str(flow.id)
    registry = get_warm_registry()
    hit = registry.get(flow_id_str)
    if hit is None:
        try:
            hit = await warm_one(flow_id_str)
        except FlowStoreUnavailableError:
            # Let the cold path do its own row read; it surfaces availability errors
            # through the normal v1 machinery rather than silently going warm.
            return None
    if hit is None:
        return None

    graph = deepcopy(hit[0])
    # Thread this run's identity onto the copy (the template is user-agnostic). This is
    # what lets explicit load_from_db fields resolve for the calling user, exactly like a
    # cold from_payload(user_id=...).
    apply_run_defaults(
        graph,
        session_id=input_request.session_id,
        user_id=str(user_id) if user_id is not None else None,
        overwrite_user_id=user_id is not None,
    )
    return graph
