"""Shared warm-graph resolution for opt-in cached execution.

When ``LANGFLOW_WARM_REGISTRY_ENABLED=true`` flows are pre-built once and
kept warm in the process-local registry. The v1 ``simple_run_flow`` and v2 sync paths
resolve a **deepcopy of the pre-built template** and apply this run's identity to the
copy — skipping per-request ``Graph.from_payload`` work and, on metadata-validated v2
hits, avoiding a repeat read of the large ``Flow.data`` column. Stream/background and
public execution retain their established graph-build paths.

Core model: warm deepcopy + set-values. A run falls back to the normal cold rebuild
whenever the per-request work can't be layered onto a shared template — see the
per-caller gates (tweaks, request context/globals, auto-bindable globals, HITL) and
the built-in gates here (warming disabled, cache miss, store unavailable).
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from langflow.api.global_variable_fields import is_global_variable_eligible_field
from langflow.services.warm_registry.service import flow_version

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph

    from langflow.api.v1.schemas import SimplifiedAPIRequest
    from langflow.services.database.models.flow.model import Flow


def is_warm_registry_enabled(settings: Any) -> bool:
    """Return whether the independently opt-in warm graph registry is enabled."""
    return bool(getattr(settings, "warm_registry_enabled", False))


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
            if is_global_variable_eligible_field(field) and isinstance(field.get("display_name"), str):
                return True
    return False


def _apply_implicit_stream_tweak(graph: Graph, *, stream: bool) -> None:
    """Apply ``process_tweaks(..., stream=...)`` semantics to an already-built graph.

    Registry entries are built before the request's execution mode is known. The
    cold path injects a global ``stream`` tweak before ``Graph.from_payload``;
    mirror that on the request-local deepcopy by overriding only vertices that
    actually declare a ``stream`` parameter. ``update_raw_params`` makes the value
    survive subsequent parameter preparation, and removing the DB marker matches
    the cold tweak path's ``load_from_db = False`` behavior.
    """
    # Apply the implicit tweak to the original top-level frontend shape, exactly
    # where the cold path runs ``process_tweaks``. Grouped children that do not
    # expose a stream proxy must retain their persisted value. If a top-level
    # field changes, rebuild the still-lazy vertex structure so ``process_flow``
    # propagates exposed group proxies before constructors run.
    raw_graph_data = getattr(graph, "raw_graph_data", None)
    raw_nodes = raw_graph_data.get("nodes") if isinstance(raw_graph_data, dict) else None
    raw_edges = raw_graph_data.get("edges") if isinstance(raw_graph_data, dict) else None
    if isinstance(raw_nodes, list) and isinstance(raw_edges, list):
        for node in raw_nodes:
            if not isinstance(node, dict):
                continue
            node_data = node.get("data")
            component_data = node_data.get("node") if isinstance(node_data, dict) else None
            template = component_data.get("template") if isinstance(component_data, dict) else None
            stream_field = template.get("stream") if isinstance(template, dict) else None
            if not isinstance(stream_field, dict):
                continue
            stream_field["value"] = stream
            if "load_from_db" in stream_field:
                stream_field["load_from_db"] = False
        # ``Graph.copy_for_run`` invokes this before its first structural build.
        # Returning even when no top-level stream field exists deliberately
        # preserves hidden grouped-child values.
        return

    # Compatibility fallback for programmatic/test graphs without retained raw
    # frontend data. Warm registry templates always take the raw-shape path.
    for vertex in graph.vertices:
        raw_params = getattr(vertex, "raw_params", None)
        if not isinstance(raw_params, dict) or "stream" not in raw_params:
            continue
        # Constructors receive the Vertex and may inspect its original template,
        # while ``update_raw_params`` changes only prepared parameter maps. Mirror
        # cold ``process_tweaks`` in both representations before construction.
        full_data = getattr(vertex, "full_data", None)
        if isinstance(full_data, dict):
            vertex_data = full_data.get("data")
            node_data = vertex_data.get("node") if isinstance(vertex_data, dict) else None
            template = node_data.get("template") if isinstance(node_data, dict) else None
            stream_field = template.get("stream") if isinstance(template, dict) else None
            if isinstance(stream_field, dict):
                stream_field["value"] = stream
                if "load_from_db" in stream_field:
                    stream_field["load_from_db"] = False
        vertex.update_raw_params({"stream": stream}, overwrite=True)  # type: ignore[dict-item]
        load_from_db_fields = getattr(vertex, "load_from_db_fields", None)
        if isinstance(load_from_db_fields, list):
            while "stream" in load_from_db_fields:
                load_from_db_fields.remove("stream")


async def warm_deepcopy(
    flow_id: str,
    *,
    expected_version: str,
    user_id: Any,
    session_id: str | None,
    stream: bool = False,
) -> Graph | None:
    """Return a run-ready deepcopy of the warm template, or ``None`` to rebuild cold.

    Built-in fall-backs: warming disabled, cache miss (and not lazily warmable), or a
    transient store-availability failure. The returned graph carries the flow's structure
    (built at warm time) plus this run's ``user_id``/``session_id`` (applied to the copy),
    so callers use it exactly like a freshly-built graph. Per-request *policy* gates
    (tweaks / context / auto-bind / HITL) are the caller's responsibility — they differ by
    run path — and must be checked BEFORE calling this.
    """
    from lfx.run._defaults import apply_run_defaults
    from lfx.utils.flow_validation import validate_flow_for_current_settings

    from langflow.services.deps import get_settings_service
    from langflow.services.warm_registry.reconcile import warm_one
    from langflow.services.warm_registry.service import (
        FlowStoreUnavailableError,
        WarmRegistryCapacityError,
        get_warm_registry,
    )

    if not is_warm_registry_enabled(get_settings_service().settings):
        return None

    flow_id_str = str(flow_id)
    registry = get_warm_registry()
    hit = registry.get(flow_id_str)
    if hit is None:
        if registry.rejects_version(flow_id_str, expected_version):
            return None
        try:
            hit = await warm_one(flow_id_str)
        except (FlowStoreUnavailableError, WarmRegistryCapacityError):
            # Let the caller's cold path do its own row read and surface errors normally.
            return None
    if hit is None:
        return None
    if hit[1] != expected_version:
        # Bind execution to the revision the caller fetched and authorized. A stale
        # hit or a reconcile swap after authorization must use the cold FlowRead path.
        return None
    if getattr(hit[0], "requires_extension_event_replay", False):
        # Warm parsing intentionally has no caller keyspace. Rebuild legacy/error
        # payloads on the request path so Graph.from_payload emits the same
        # per-user extension events as the historical cold execution path.
        return None

    # Catalog and custom-component policy can change without touching the Flow
    # row. Revalidate the cached raw payload on every hit, matching the defense
    # in depth in Graph.from_payload instead of letting a newly blocked
    # component survive until the next flow revision.
    validate_flow_for_current_settings(hit[0])

    run_user_id = str(user_id) if user_id is not None else None
    copy_for_run = getattr(hit[0], "copy_for_run", None)
    if callable(copy_for_run):
        graph = copy_for_run(
            user_id=run_user_id,
            before_instantiate=lambda run_graph: _apply_implicit_stream_tweak(run_graph, stream=stream),
        )
    else:
        graph = deepcopy(hit[0])
        _apply_implicit_stream_tweak(graph, stream=stream)
    # Thread this run's identity onto the copy (the template is user-agnostic). This is
    # what lets explicit load_from_db fields resolve for the calling user, exactly like a
    # cold from_payload(user_id=...).
    apply_run_defaults(
        graph,
        session_id=session_id,
        user_id=run_user_id,
        overwrite_user_id=user_id is not None,
    )
    return graph


async def try_warm_run_graph(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    *,
    user_id: Any,
    context: dict | None,
    stream: bool = False,
) -> Graph | None:
    """v1 ``simple_run_flow`` warm resolver: gate on the v1 signals, then ``warm_deepcopy``.

    Cold-falls-back (returns ``None``) for tweaks, request context, auto-bindable-globals
    flows, or HITL flows — everything the shared template can't represent — so the caller
    rebuilds exactly as before.
    """
    if input_request.tweaks or context is not None:
        return None
    # Keep v1 router initialization out of this module's clean-import path.
    from langflow.api.v1.run_validation import flow_requires_hitl

    data = flow.data or {}
    if flow_needs_auto_globals(data) or flow_requires_hitl(data):
        return None
    return await warm_deepcopy(
        str(flow.id),
        expected_version=flow_version(flow.updated_at),
        user_id=user_id,
        session_id=input_request.session_id,
        stream=stream,
    )
