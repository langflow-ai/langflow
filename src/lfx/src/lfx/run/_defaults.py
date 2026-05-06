"""Shared helpers for applying run-time defaults to a Graph.

The CLI's ``lfx run`` (``run_flow``) and ``lfx serve``/``execute_graph_with_capture``
both need to:

1. Reject empty/whitespace-only ``session_id`` / ``user_id`` (so a typo or
   empty env var doesn't silently produce a random session and break Memory
   continuity).
2. Auto-generate a UUID when neither is supplied (so component prechecks and
   ``astore_message`` validation don't fail).
3. Propagate ``session_id`` to ``Memory``/``MessageHistory`` vertices the way
   ``langflow.api.utils.flow_utils.build_graph_from_data`` does — preserving
   any value already pinned in the flow JSON.
4. Resolve ``fallback_to_env_vars`` from settings (mirrors the langflow API
   path in ``processing.process.run_graph_internal``).

Both call sites used to inline these steps; consolidating them here prevents
behavior drift between ``lfx run`` and ``lfx serve``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.deps import get_settings_service

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph


def validate_provided_id(name: str, value: str | None) -> None:
    """Reject empty/whitespace strings while allowing None (which means "auto-generate").

    Empty strings reach this code via shell quirks (``--session-id ""``), env-var
    expansion that resolved to empty, or callers that defaulted a missing arg to
    ``""`` instead of ``None``. Treating them the same as ``None`` would silently
    fall through to UUID generation — and the user would only learn their session
    didn't carry over by noticing Memory looks empty on the next run.
    """
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        msg = (
            f"{name} was provided but is empty or whitespace. "
            f"Pass a non-empty value, or omit {name} to auto-generate one."
        )
        raise ValueError(msg)


def apply_run_defaults(
    graph: Graph,
    *,
    session_id: str | None,
    user_id: str | None,
    overwrite_user_id: bool = True,
) -> tuple[str, str]:
    """Apply session_id, user_id, and vertex-propagation defaults to *graph*.

    Validates non-None values are non-empty (raises ``ValueError`` otherwise).
    Auto-generates UUID hex strings for any value left as ``None``. Sets the
    resolved values on the graph and propagates ``session_id`` to vertices in
    ``graph.has_session_id_vertices`` that don't already have a hardcoded value.

    Args:
        graph: The graph to mutate.
        session_id: Caller-supplied session_id. ``None`` -> auto-generate.
        user_id: Caller-supplied user_id. ``None`` -> auto-generate.
        overwrite_user_id: When False, an existing ``graph.user_id`` is preserved
            (matches the prior ``execute_graph_with_capture`` behavior). When True,
            the resolved user_id always wins (matches the prior ``run_flow``
            behavior, which intentionally re-stamps the graph).

    Returns:
        ``(session_id, user_id)`` — the values actually applied to the graph.
    """
    validate_provided_id("session_id", session_id)
    validate_provided_id("user_id", user_id)

    if not user_id:
        user_id = uuid.uuid4().hex
        logger.debug(
            f"No user_id provided; auto-generated {user_id} to satisfy component prechecks. "
            "lfx's variable service is env-backed, so user_id is not used for variable scoping."
        )
    if overwrite_user_id or not getattr(graph, "user_id", None):
        graph.user_id = user_id
    else:
        # Caller-supplied None plus an existing graph.user_id: preserve the existing.
        user_id = graph.user_id

    if not session_id:
        session_id = uuid.uuid4().hex
        # info, not warning: this is the normal case for one-shot CLI runs and
        # would otherwise spam stderr on every invocation. Visible at -v.
        logger.info(
            f"No session_id provided; auto-generated {session_id}. "
            "Memory/MessageHistory components will not see prior conversation state across runs."
        )
    graph.session_id = session_id

    # Mirror langflow's build_graph_from_data: only write when raw_params has no
    # session_id (hardcoded values pinned in the flow JSON win). graph.async_start
    # bypasses the equivalent loop in Graph._run, so without this Memory components
    # would read "" from their input field even when --session-id is set.
    for vertex_id in graph.has_session_id_vertices:
        vertex = graph.get_vertex(vertex_id)
        if vertex is None:
            continue
        if not vertex.raw_params.get("session_id"):
            vertex.update_raw_params({"session_id": session_id}, overwrite=True)

    return session_id, user_id


def resolve_fallback_to_env_vars() -> bool:
    """Read ``fallback_to_env_var`` from settings, defaulting to True if the service is missing.

    Mirrors the langflow API path (``processing.process.run_graph_internal``):
    when a ``load_from_db`` variable misses (e.g. the ceremonial UUID has no
    Variable row), fall through to ``os.environ`` instead of failing the build.
    A missing settings_service is unusual — log a warning so the user can debug.
    """
    settings_service = get_settings_service()
    if settings_service is None:
        logger.warning(
            "settings_service is unavailable; defaulting fallback_to_env_vars=True. "
            "If load_from_db variables are misbehaving, verify the settings service initialized."
        )
        return True
    return bool(settings_service.settings.fallback_to_env_var)
