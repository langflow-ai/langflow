"""Removing secrets from recorded operations and reconstructed graphs before they leave the server.

Stored operations hold exactly what the flow held, secrets included, so that
replay reproduces the flow. Every read strips them with the scrubber flow
export uses: literal secret values are nulled, while fields bound to a global
variable keep the variable's name, which is not a secret and which playback
needs. Only names of the owner's existing variables are kept.

An ``add_nodes`` payload is whole nodes and is scrubbed like any flow. A
``set_field`` carries only a path and a value, so it is scrubbed in place: the
value is set into a stand-in node at its path, next to the field metadata the
diff recorded with it (``template_field``), scrubbed, and read back.
"""

from __future__ import annotations

import copy
import itertools
from typing import TYPE_CHECKING, Any

from langflow.utils.flow_secrets import strip_secret_field_values_in_place, strip_structured_secret_values

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

_TEMPLATE_PATH = ("data", "node", "template")
# data.node.template.<field>.value[<row>].<column>
_CELL_PATH_DEPTH = len(_TEMPLATE_PATH) + 4


def strip_graph_secrets(flow_data: dict[str, Any], known_variable_names: Collection[str]) -> dict[str, Any]:
    """Return a copy of a graph with literal secrets removed."""
    stripped = copy.deepcopy(flow_data)
    strip_secret_field_values_in_place(stripped, variable_references=set(), known_variable_names=known_variable_names)
    return stripped


def strip_operation_secrets(operation: dict[str, Any], known_variable_names: Collection[str]) -> dict[str, Any]:
    """Return a copy of a serialized operation with literal secrets removed."""
    stripped = copy.deepcopy(operation)
    operation_type = stripped.get("type")
    if operation_type == "add_nodes":
        strip_secret_field_values_in_place(
            {"nodes": stripped["nodes"]}, variable_references=set(), known_variable_names=known_variable_names
        )
    elif operation_type == "update_nodes":
        for update in stripped["updates"]:
            if update.get("op") == "set_field":
                update["value"] = _strip_field_value(
                    update["path"], update.get("value"), update.get("template_field"), known_variable_names
                )
    elif operation_type == "update_metadata":
        stripped["fields"] = strip_structured_secret_values(stripped.get("fields", {}))
    return stripped


def _strip_field_value(
    path: Sequence[Any],
    value: Any,
    template_field: dict[str, Any] | None,
    known_variable_names: Collection[str],
) -> Any:
    node: dict[str, Any] = {"data": {"node": {"template": {}}}}
    if tuple(path[: len(_TEMPLATE_PATH)]) == _TEMPLATE_PATH and len(path) > len(_TEMPLATE_PATH) + 1:
        # A write inside one template field: give the stand-in field the
        # metadata that decides whether its value is a secret.
        field_name = path[len(_TEMPLATE_PATH)]
        node["data"]["node"]["template"][field_name] = dict(template_field or {})
    # A selector segment ({"id": ...} or {"key": ...}) addresses one item of a
    # list, such as a table row: the stand-in holds that item as the list's only
    # element, so the scrubber sees the same shape it sees in a stored flow.
    container: Any = node
    for segment, following in itertools.pairwise(path):
        container = _stand_in_child(container, segment, as_list=_is_selector(following))
        if container is None:
            return None
    if _is_selector(path[-1]):
        if not isinstance(container, list):
            return None
        container.append(value)
    else:
        container[path[-1]] = value

    strip_secret_field_values_in_place(
        {"nodes": [node]}, variable_references=set(), known_variable_names=known_variable_names
    )

    # Whether a key/value row's ``value`` cell is a secret depends on the
    # row's key cell (``Authorization``), which a single-cell write does not
    # carry, so such a cell is withheld.
    if len(path) >= _CELL_PATH_DEPTH and _is_selector(path[-2]) and path[-1] == "value":
        return None

    # The scrubber may null a container above the path (a whole secret
    # ``value``), which removes everything written inside it.
    stripped: Any = node
    for segment in path:
        if _is_selector(segment):
            if not isinstance(stripped, list) or not stripped:
                return None
            stripped = stripped[0]
        elif isinstance(stripped, dict) and segment in stripped:
            stripped = stripped[segment]
        else:
            return None
    return stripped


def _is_selector(segment: Any) -> bool:
    return isinstance(segment, dict)


def _stand_in_child(container: Any, segment: Any, *, as_list: bool) -> Any:
    """Return the stand-in child at ``segment``, creating it as a list or an object."""
    if _is_selector(segment):
        if not isinstance(container, list):
            return None
        if not container:
            container.append({})
        return container[0]
    child = container.get(segment) if isinstance(container, dict) else None
    if as_list and not isinstance(child, list):
        child = []
        container[segment] = child
    elif not as_list and not isinstance(child, dict):
        child = {}
        container[segment] = child
    return child
