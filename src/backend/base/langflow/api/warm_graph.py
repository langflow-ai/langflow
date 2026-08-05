"""Shared warm-graph resolution for the PROD execution plane.

Under ``LANGFLOW_DEPLOYMENT_PROFILE=prod`` the deployed flows are pre-built once and
kept warm in the process-local registry. Run paths (v1 ``simple_run_flow``, v2 sync,
and later stream/background) resolve a **deepcopy of the pre-built template** and apply
this run's identity to the copy — skipping the per-request ``Graph.from_payload`` (CPU)
and the flow-row read (DB pool checkout).

Core model: warm deepcopy + set-values. A run falls back to the normal cold rebuild
whenever the per-request work can't be layered onto a shared template — see the
per-caller gates (tweaks, request context/globals, auto-bindable globals, HITL) and
the built-in gates here (not prod, cache miss, store unavailable).
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


def is_prod_deployment(settings: Any) -> bool:
    """True when the production deployment profile is active.

    Consumes ``settings.deployment_profile`` (env ``LANGFLOW_DEPLOYMENT_PROFILE``) — the
    umbrella flag owned by the deployment-profile preflight feature. Read defensively via
    ``getattr`` so this is safe on branches where that setting does not exist yet:
    absent -> ``"dev"`` -> production behavior stays off. The warm registry + authz-lean
    behavior therefore activate only under the same ``prod`` profile the preflight gate
    validates.
    """
    return getattr(settings, "deployment_profile", "dev") == "prod"


def flow_needs_auto_globals(data: dict | None) -> bool:
    """True if the flow has any field an auto-bound global variable COULD target.

    Conservative over-approximation (the caller's variables aren't known here): if the
    flow has at least one empty, global-eligible str field with a display_name, some
    user's variable ``default_fields`` might auto-bind it at run time — so that flow must
    take the cold path (only ``apply_global_variable_defaults`` performs that binding, and
    it mutates graph_data per user, never the stored flow.data). If there is no such
    field, no auto-binding is possible for anyone and the warm template is complete.
    Explicit ``load_from_db`` fields ARE in flow.data and resolve warm (identity threaded).
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


async def warm_deepcopy(flow_id: str, *, user_id: Any, session_id: str | None) -> Graph | None:
    """Return a run-ready deepcopy of the warm template, or ``None`` to rebuild cold.

    Built-in fall-backs: not the prod profile, cache miss (and not lazily warmable), or a
    transient store-availability failure. The returned graph carries the flow's structure
    (built at warm time) plus this run's ``user_id``/``session_id`` (applied to the copy),
    so callers use it exactly like a freshly-built graph. Per-request *policy* gates
    (tweaks / context / auto-bind / HITL) are the caller's responsibility — they differ by
    run path — and must be checked BEFORE calling this.
    """
    from lfx.run._defaults import apply_run_defaults

    from langflow.services.deps import get_settings_service
    from langflow.services.warm_registry.reconcile import warm_one
    from langflow.services.warm_registry.service import FlowStoreUnavailableError, get_warm_registry

    if not is_prod_deployment(get_settings_service().settings):
        return None

    flow_id_str = str(flow_id)
    registry = get_warm_registry()
    hit = registry.get(flow_id_str)
    if hit is None:
        try:
            hit = await warm_one(flow_id_str)
        except FlowStoreUnavailableError:
            # Let the caller's cold path do its own row read and surface errors normally.
            return None
    if hit is None:
        return None

    graph = deepcopy(hit[0])
    # Thread this run's identity onto the copy (the template is user-agnostic). This is
    # what lets explicit load_from_db fields resolve for the calling user, exactly like a
    # cold from_payload(user_id=...).
    apply_run_defaults(
        graph,
        session_id=session_id,
        user_id=str(user_id) if user_id is not None else None,
        overwrite_user_id=user_id is not None,
    )
    return graph


async def try_warm_run_graph(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    *,
    user_id: Any,
    context: dict | None,
) -> Graph | None:
    """v1 ``simple_run_flow`` warm resolver: gate on the v1 signals, then ``warm_deepcopy``.

    Cold-falls-back (returns ``None``) for tweaks, request context, auto-bindable-globals
    flows, or HITL flows — everything the shared template can't represent — so the caller
    rebuilds exactly as before.
    """
    if input_request.tweaks or context is not None:
        return None
    data = flow.data or {}
    if flow_needs_auto_globals(data) or flow_requires_hitl(data):
        return None
    return await warm_deepcopy(str(flow.id), user_id=user_id, session_id=input_request.session_id)
