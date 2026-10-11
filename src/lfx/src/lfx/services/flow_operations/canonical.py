"""Canonical form of flow data, for equality and checkpoint hashes.

Two graphs are equal when their canonical forms are byte-identical. The form is
RFC 8785 (JSON Canonicalization Scheme) applied to the graph with its view
state removed and its nodes and edges ordered by ID:

- JCS sorts object keys and prints numbers the way JavaScript does, so ``1``
  and ``1.0`` are the same value, ``true`` and ``1`` are not, and key order is
  never a change. JavaScript cannot tell integers from floats, so a ``0.0``
  that comes back from the editor as ``0`` must not count as an edit.
- ``nodes`` and ``edges`` are collections keyed by ID. Their array order is not
  state, so a save that only reorders them changes nothing.
- View state is everything ``node_schema.json`` declares display-only: one
  person's view of the canvas (pan and zoom, selection, drag and resize flags,
  sizes), stamps the editor refreshes on its own (``last_updated``,
  ``lf_version``), and the display-only keys of template fields (labels,
  options, help text). It is stored but never recorded and never compared.
- An edge's ``sourceHandle`` and ``targetHandle`` strings are JSON with
  ``œ`` standing for ``"``. They are compared by what they encode, so two
  spellings of one handle are the same value. Edge ids are left as they are.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from typing import Any

from lfx.services.flow_operations.exceptions import FlowDataValidationError
from lfx.services.flow_operations.schema import load_node_schema

_SCHEMA = load_node_schema()
FLOW_VIEW_STATE_KEYS = _SCHEMA.flow_view_state
NODE_VIEW_STATE_KEYS = _SCHEMA.node_view_state
EDGE_VIEW_STATE_KEYS = _SCHEMA.edge_view_state
EDGE_HANDLE_KEYS = ("sourceHandle", "targetHandle")
_HANDLE_QUOTE = "œ"

# Largest integer a JavaScript number holds exactly. Larger integers are
# printed as the double the editor would round them to.
_MAX_SAFE_INTEGER = 2**53
# ECMAScript prints numbers below 1e21 in plain notation.
_MAX_PLAIN_EXPONENT = 21
_MIN_PLAIN_EXPONENT = -6


def json_type(value: Any) -> str:
    """Return the JSON type of a Python value: object, array, string, number, boolean or null."""
    # bool is a subclass of int, so it must be checked first.
    if isinstance(value, bool):
        return "boolean"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    msg = f"value of type {type(value).__name__} is not JSON"
    raise FlowDataValidationError(msg)


def _format_number(value: float) -> str:
    if isinstance(value, int):
        if abs(value) <= _MAX_SAFE_INTEGER:
            return str(value)
        value = float(value)
    if not math.isfinite(value):
        msg = "NaN and Infinity are not valid JSON numbers"
        raise FlowDataValidationError(msg)
    if value == 0:
        return "0"

    # repr() gives the shortest digits that round-trip, which is also what
    # ECMAScript's Number::toString chooses; only the layout differs.
    sign = "-" if value < 0 else ""
    _, digit_tuple, exponent = Decimal(repr(abs(value))).as_tuple()
    digits = "".join(str(digit) for digit in digit_tuple).rstrip("0")
    exponent += len(digit_tuple) - len(digits)
    digits = digits.lstrip("0")
    k = len(digits)
    n = k + exponent  # value == 0.<digits> * 10**n

    if k <= n <= _MAX_PLAIN_EXPONENT:
        return sign + digits + "0" * (n - k)
    if 0 < n <= _MAX_PLAIN_EXPONENT:
        return sign + digits[:n] + "." + digits[n:]
    if _MIN_PLAIN_EXPONENT < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    e = n - 1
    mantissa = digits if k == 1 else digits[0] + "." + digits[1:]
    return f"{sign}{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"


def utf16_sort_key(value: str) -> bytes:
    """Order strings by UTF-16 code units, the order JavaScript's default sort uses."""
    return value.encode("utf-16-be", "surrogatepass")


def _write_canonical(value: Any, parts: list[str]) -> None:
    if value is None:
        parts.append("null")
    elif value is True:
        parts.append("true")
    elif value is False:
        parts.append("false")
    elif isinstance(value, (int, float)):
        parts.append(_format_number(value))
    elif isinstance(value, str):
        parts.append(json.dumps(value, ensure_ascii=False))
    elif isinstance(value, list):
        parts.append("[")
        for index, item in enumerate(value):
            if index:
                parts.append(",")
            _write_canonical(item, parts)
        parts.append("]")
    elif isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                msg = f"object key {key!r} is not a string"
                raise FlowDataValidationError(msg)
        parts.append("{")
        for index, key in enumerate(sorted(value, key=utf16_sort_key)):
            if index:
                parts.append(",")
            parts.append(json.dumps(key, ensure_ascii=False))
            parts.append(":")
            _write_canonical(value[key], parts)
        parts.append("}")
    else:
        json_type(value)  # raises for anything that is not JSON


def canonical_json(value: Any) -> str:
    """Serialize a JSON value in RFC 8785 canonical form."""
    parts: list[str] = []
    _write_canonical(value, parts)
    return "".join(parts)


def is_row_position(value: Any) -> bool:
    """Return whether ``value`` is a valid table row position: a finite number."""
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def ordered_rows(rows: list[Any]) -> list[Any]:
    """Return a table's rows in order: by ``(_pos, _id)``, or as stored for a legacy table without them.

    A table's order is its rows' positions, not their places in the array.
    Positions compare as the doubles JavaScript holds and ids by UTF-16 code
    units, as the editor sorts them.
    """
    id_key, position_key = _SCHEMA.table.key[0], _SCHEMA.table.position
    if not all(
        isinstance(row, dict) and is_row_position(row.get(position_key)) and isinstance(row.get(id_key), str)
        for row in rows
    ):
        return list(rows)
    return sorted(rows, key=lambda row: (float(row[position_key]), utf16_sort_key(row[id_key])))


def _without(mapping: dict[str, Any], keys: frozenset[str]) -> dict[str, Any]:
    return {key: item for key, item in mapping.items() if key not in keys}


def _by_id(entries: list[Any]) -> list[Any]:
    return sorted(
        entries,
        key=lambda entry: utf16_sort_key(entry["id"])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        else b"",
    )


def canonical_handle(handle: Any) -> Any:
    """Return a handle string re-serialized canonically, or the value unchanged if it is not one.

    ``{œaœ: 1}`` and ``{œaœ:1}`` encode the same handle and give the same result.
    """
    if not isinstance(handle, str):
        return handle
    try:
        parsed = json.loads(handle.replace(_HANDLE_QUOTE, '"'))
        if not isinstance(parsed, (dict, list)):
            return handle
        return canonical_json(parsed).replace('"', _HANDLE_QUOTE)
    except (ValueError, FlowDataValidationError):
        return handle


def canonical_template_field(field: Any) -> Any:
    """Return a template field without its display-only keys."""
    if not isinstance(field, dict):
        return field
    return _without(field, _SCHEMA.field_view_state)


def canonical_node(node: Any) -> Any:
    """Return a node without view state. Shares unchanged values with ``node``."""
    if not isinstance(node, dict):
        return node
    node = _without(node, NODE_VIEW_STATE_KEYS)
    data = node.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("node"), dict):
        return node
    node_data = data["node"]
    hidden = {path[-1] for path in _SCHEMA.node_view_state_paths if path[:-1] == ("data", "node")}
    node_data = _without(node_data, frozenset(hidden))
    template = node_data.get("template")
    if isinstance(template, dict):
        node_data["template"] = {
            key: _ordered_table(node, key, canonical_template_field(field))
            for key, field in template.items()
            if key not in _SCHEMA.template_view_state
        }
    node["data"] = {**data, "node": node_data}
    return node


def _ordered_table(node: dict[str, Any], key: str, field: Any) -> Any:
    """Put a table field's rows in order, since their places in the array are not state."""
    if not (isinstance(field, dict) and isinstance(field.get("value"), list)):
        return field
    if _SCHEMA.keyed_list_at(node, ("data", "node", "template", key, "value")) is not _SCHEMA.table:
        return field
    return {**field, "value": ordered_rows(field["value"])}


def canonical_edge(edge: Any) -> Any:
    """Return an edge without view state and with its handle strings spelled canonically."""
    if not isinstance(edge, dict):
        return edge
    edge = _without(edge, EDGE_VIEW_STATE_KEYS)
    for key in EDGE_HANDLE_KEYS:
        if key in edge:
            edge[key] = canonical_handle(edge[key])
    return edge


def canonical_graph(flow_data: dict[str, Any]) -> dict[str, Any]:
    """Return flow data without view state, with canonical handles, and nodes and edges ordered by ID.

    The result shares nested values with ``flow_data``; it is meant to be
    serialized or compared, not mutated.
    """
    graph = _without(flow_data, FLOW_VIEW_STATE_KEYS)
    if isinstance(graph.get("nodes"), list):
        graph["nodes"] = _by_id([canonical_node(node) for node in graph["nodes"]])
    if isinstance(graph.get("edges"), list):
        graph["edges"] = _by_id([canonical_edge(edge) for edge in graph["edges"]])
    return graph


def canonical_graph_json(flow_data: dict[str, Any]) -> str:
    """Serialize flow data in canonical graph form."""
    return canonical_json(canonical_graph(flow_data))


def graph_hash(flow_data: dict[str, Any]) -> str:
    """Return the SHA-256 hex digest of flow data's canonical graph form."""
    encoded = canonical_graph_json(flow_data).encode("utf-8", "surrogatepass")
    return hashlib.sha256(encoded).hexdigest()


def graphs_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return whether two flow data mappings are the same graph."""
    return canonical_graph_json(left) == canonical_graph_json(right)


def values_equal(left: Any, right: Any) -> bool:
    """Return whether two JSON values have the same canonical form, stopping at the first difference.

    The comparison never serializes: objects compare key by key in any order,
    arrays item by item, and numbers as the doubles JavaScript would hold.
    """
    if left is right:
        return True
    left_type = json_type(left)
    if left_type != json_type(right):
        return False
    if left_type == "number":
        return _as_double(left) == _as_double(right)
    if left_type == "array":
        return len(left) == len(right) and all(values_equal(a, b) for a, b in zip(left, right, strict=True))
    if left_type == "object":
        if len(left) != len(right):
            return False
        for key, value in left.items():
            if not isinstance(key, str):
                msg = f"object key {key!r} is not a string"
                raise FlowDataValidationError(msg)
            if key not in right or not values_equal(value, right[key]):
                return False
        return True
    return left == right


def _as_double(value: float) -> float:
    """Return a JSON number as the double JavaScript holds, which is what its canonical form prints."""
    double = float(value)
    if not math.isfinite(double):
        msg = "NaN and Infinity are not valid JSON numbers"
        raise FlowDataValidationError(msg)
    return double
