"""Apply global-variable ``default_fields`` to an in-memory flow graph at API-run time.

When a flow is uploaded and run purely via API, no frontend ever sees the template,
so the ``load_from_db`` flag is never written back to the stored flow. This module
mirrors the frontend behaviour in-memory, just before ``Graph.from_payload``:

* Builds a ``{display_name: variable_name}`` map from each user variable's
  ``default_fields`` -- same as the frontend's ``getUnavailableFields``.
* For every empty template field whose ``display_name`` is in the map, sets
  ``value = variable_name`` and ``load_from_db = True`` -- same as the frontend's
  ``useInitialLoad`` hook (``InputGlobalComponent``).

The mutation is local to the request; the stored flow is unchanged. The vertex-time
resolver (``update_params_with_load_from_db_fields``) and its skip rules (incoming
edge / connected model / connection mode) remain the source of truth at runtime.

Bug: https://github.com/langflow-ai/langflow/issues/11781
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from lfx.utils.constants import DIRECT_TYPES

from langflow.services.deps import get_variable_service, session_scope

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID


# Field ``type`` values that should be considered for automatic global-variable
# binding. Mirrors what the frontend's ``StrRenderComponent`` actually delegates
# to ``InputGlobalComponent`` -- str-like inputs without options. Other DIRECT_TYPES
# entries (dict, code, table, NestedDict, sortableList, ...) never render the
# global-variable picker, so we leave them alone here too.
_GLOBAL_VARIABLE_ELIGIBLE_TYPES: frozenset[str] = frozenset({"str"})


def build_unavailable_fields_map(
    variables: Iterable[tuple[str, list[str] | None]],
) -> dict[str, str]:
    """Build a ``{display_name: variable_name}`` map from user variables.

    Mirrors ``getUnavailableFields`` in
    ``src/frontend/src/stores/globalVariablesStore/utils/get-unavailable-fields.tsx``.

    Iteration order follows the input; if two variables claim the same
    ``default_field``, the later entry wins (matching the frontend's forEach
    last-write-wins).
    """
    result: dict[str, str] = {}
    for name, default_fields in variables:
        if not name or not default_fields:
            continue
        for field in default_fields:
            if isinstance(field, str) and field:
                result[field] = name
    return result


def _is_eligible_field(field: dict[str, Any]) -> bool:
    """Return True if this template field can accept an auto-bound global variable."""
    if not isinstance(field, dict):
        return False
    # Field must be visible (mirrors frontend rendering gate) and a text-ish input.
    if field.get("show") is False:
        return False
    field_type = field.get("type")
    if field_type not in DIRECT_TYPES or field_type not in _GLOBAL_VARIABLE_ELIGIBLE_TYPES:
        return False
    # Don't clobber an explicit user choice already persisted to the template.
    if field.get("load_from_db") is True:
        return False
    # Only fill empty fields -- never overwrite a real value.
    existing = field.get("value")
    return existing in (None, "")


def apply_unavailable_fields_to_graph(
    graph_data: dict[str, Any],
    unavailable_fields: dict[str, str],
) -> dict[str, Any]:
    """Return a new ``graph_data`` with global-variable defaults applied.

    Pure function: does not read the DB, does not mutate the input. Walks every
    node's template and, for each eligible field whose ``display_name`` matches a
    key in ``unavailable_fields``, sets ``value = variable_name`` and
    ``load_from_db = True``.

    Args:
        graph_data: The flow graph payload (``{"nodes": [...], "edges": [...], ...}``)
            as produced by ``flow.data``.
        unavailable_fields: Map from field ``display_name`` to global-variable name,
            typically produced by :func:`build_unavailable_fields_map`.

    Returns:
        A deep-copied graph_data with the relevant fields updated. If
        ``unavailable_fields`` is empty, returns the input dict unchanged (no copy).
    """
    if not unavailable_fields or not isinstance(graph_data, dict):
        return graph_data

    nodes = graph_data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return graph_data

    new_graph_data = copy.deepcopy(graph_data)
    for node in new_graph_data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        template = (node.get("data") or {}).get("node", {}).get("template")
        if not isinstance(template, dict):
            continue
        for field_name, field in template.items():
            if field_name == "_type" or not _is_eligible_field(field):
                continue
            display_name = field.get("display_name")
            if not isinstance(display_name, str):
                continue
            variable_name = unavailable_fields.get(display_name)
            if variable_name is None:
                continue
            field["value"] = variable_name
            field["load_from_db"] = True

    return new_graph_data


async def apply_global_variable_defaults(
    graph_data: dict[str, Any],
    user_id: UUID | str,
) -> dict[str, Any]:
    """Look up the user's variables and apply ``default_fields`` to ``graph_data``.

    This is the entry point called by ``simple_run_flow``. Errors from the
    variable service are logged and swallowed so a transient lookup failure
    cannot block flow execution -- the original (pre-fix) behaviour is preserved
    in that case, and the vertex-time resolver still serves as a backstop for
    fields already marked ``load_from_db`` in the stored template.
    """
    if user_id is None:
        return graph_data

    try:
        variable_service = get_variable_service()
        async with session_scope() as session:
            variables = await variable_service.get_all(user_id=user_id, session=session)
    except Exception as exc:  # noqa: BLE001 - never block flow runs on variable lookup
        await logger.awarning(
            "Could not load global variables for user %s while applying default_fields: %s",
            user_id,
            exc,
        )
        return graph_data

    pairs = [(v.name, v.default_fields) for v in variables if v.name]
    unavailable_fields = build_unavailable_fields_map(pairs)
    return apply_unavailable_fields_to_graph(graph_data, unavailable_fields)
