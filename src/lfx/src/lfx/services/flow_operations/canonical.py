"""Canonical form of flow data, for equality and checkpoint hashes.

Two graphs are equal when their canonical forms are the same JSON value. The
form is the graph with its view state removed, and with everything whose order
is not state keyed by id:

- JSON values compare as RFC 8785 (JSON Canonicalization Scheme) prints them:
  ``1`` and ``1.0`` are the same value, ``true`` and ``1`` are not, and key
  order is never a change. JavaScript cannot tell integers from floats, so a
  ``0.0`` that comes back from the editor as ``0`` must not count as an edit.
- ``nodes``, ``edges`` and table rows are collections keyed by id. Their array
  order is not state, so a save that only reorders them changes nothing; a
  table's order is its rows' ``(_pos, _id)``.
- View state is everything ``node_schema.json`` declares display-only: one
  person's view of the canvas (pan and zoom, selection, drag and resize flags,
  sizes), stamps the editor refreshes on its own (``last_updated``,
  ``lf_version``), and the display-only keys of template fields (labels,
  options, help text). It is stored but never recorded and never compared.
- An edge's ``sourceHandle`` and ``targetHandle`` strings are JSON with
  ``œ`` standing for ``"``. They compare by the object they encode, so two
  spellings of one handle are the same value. Edge ids are left as they are.

Equality compares the form structurally and stops at the first difference;
only ``graph_hash`` serializes it, with collections ordered, as RFC 8785 text.
The form is defined for any JSON graph, valid or not: enforcing the rules is
validation's job.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal
from typing import Any, NoReturn

from lfx.services.flow_operations.exceptions import FlowDataValidationError
from lfx.services.flow_operations.schema import load_node_schema

_SCHEMA = load_node_schema()
FLOW_VIEW_STATE_KEYS = _SCHEMA.flow_view_state
NODE_VIEW_STATE_KEYS = _SCHEMA.node_view_state
EDGE_VIEW_STATE_KEYS = _SCHEMA.edge_view_state
EDGE_HANDLE_KEYS = ("sourceHandle", "targetHandle")
_NODE_DATA_VIEW_STATE = frozenset(path[-1] for path in _SCHEMA.node_view_state_paths if path[:-1] == ("data", "node"))
_HANDLE_QUOTE = "œ"

# Largest integer a JavaScript number holds exactly. Larger integers are
# printed as the double the editor would round them to.
_MAX_SAFE_INTEGER = 2**53
# The smallest integer that rounds past the largest double. JavaScript reads
# it, and every larger one, as Infinity, so it is not a finite JSON number.
_DOUBLE_OVERFLOW = 2**1024 - 2**970
# A UTF-16 surrogate. json.loads joins an escaped surrogate pair into one
# character, so a surrogate left in a str is an unpaired one. RFC 8785 needs
# I-JSON (RFC 7493), which forbids them, and UTF-8 cannot encode them.
_SURROGATE = re.compile("[\ud800-\udfff]")
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


def is_finite_number(value: float) -> bool:
    """Return whether a JSON number is finite as the double JavaScript reads it.

    An integer too large for a double reads as Infinity, so it is not finite.
    """
    if isinstance(value, int):
        return abs(value) < _DOUBLE_OVERFLOW
    return math.isfinite(value)


def _non_finite_error() -> FlowDataValidationError:
    return FlowDataValidationError("NaN, Infinity and integers too large for a double are not valid JSON numbers")


def _format_number(value: float) -> str:
    if not is_finite_number(value):
        raise _non_finite_error()
    if isinstance(value, int):
        if abs(value) <= _MAX_SAFE_INTEGER:
            return str(value)
        value = float(value)
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


def is_well_formed(value: str) -> bool:
    """Return whether a string holds no unpaired surrogate, as JavaScript's ``isWellFormed`` tells."""
    return _SURROGATE.search(value) is None


def to_well_formed(value: str) -> str:
    """Return a string with each unpaired surrogate replaced by U+FFFD, as JavaScript's ``toWellFormed`` does."""
    return _SURROGATE.sub("\ufffd", value)


def _canonical_string(value: str) -> str:
    if not is_well_formed(value):
        msg = "strings must not hold an unpaired surrogate"
        raise FlowDataValidationError(msg)
    return json.dumps(value, ensure_ascii=False)


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
        parts.append(_canonical_string(value))
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
            parts.append(_canonical_string(key))
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
    return not isinstance(value, bool) and isinstance(value, (int, float)) and is_finite_number(value)


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


def _reject_constant(token: str) -> NoReturn:
    msg = f"{token} is not valid JSON"
    raise ValueError(msg)


def parse_handle(handle: Any) -> dict[str, Any] | None:
    """Return the object a handle string encodes (JSON with ``œ`` for ``"``), or None when it encodes none.

    The string is parsed as strict JSON, as JavaScript's ``JSON.parse`` reads
    it: the ``NaN``, ``Infinity`` and ``-Infinity`` tokens do not parse.
    """
    if not isinstance(handle, str):
        return None
    try:
        parsed = json.loads(handle.replace(_HANDLE_QUOTE, '"'), parse_constant=_reject_constant)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def canonical_template_field(field: Any) -> Any:
    """Return a template field without its display-only keys."""
    if not isinstance(field, dict):
        return field
    return _without(field, _SCHEMA.field_view_state)


def canonical_node(node: Any, *, keyed: bool = True) -> Any:
    """Return a node without view state and with its table rows as a collection.

    Shares unchanged values with ``node``. With ``keyed``, a table whose rows
    all carry ids becomes a mapping from row id to row; otherwise its rows are
    put in order. A legacy table without row ids keeps its array, which is its
    order.
    """
    if not isinstance(node, dict):
        return node
    node = _without(node, NODE_VIEW_STATE_KEYS)
    data = node.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("node"), dict):
        return node
    node_data = _without(data["node"], _NODE_DATA_VIEW_STATE)
    template = node_data.get("template")
    if isinstance(template, dict):
        node_data["template"] = {
            key: _table_as_collection(node, key, canonical_template_field(field), keyed=keyed)
            for key, field in template.items()
            if key not in _SCHEMA.template_view_state
        }
    node["data"] = {**data, "node": node_data}
    return node


def _table_as_collection(node: dict[str, Any], key: str, field: Any, *, keyed: bool) -> Any:
    if not (isinstance(field, dict) and isinstance(field.get("value"), list)):
        return field
    if _SCHEMA.keyed_list_at(node, ("data", "node", "template", key, "value")) is not _SCHEMA.table:
        return field
    rows = field["value"]
    if keyed:
        by_id = _by_id(rows, _SCHEMA.table.key[0])
        return {**field, "value": by_id} if by_id is not None else field
    return {**field, "value": ordered_rows(rows)}


def canonical_edge(edge: Any) -> Any:
    """Return an edge without view state, its handle strings replaced by the objects they encode."""
    if not isinstance(edge, dict):
        return edge
    edge = _without(edge, EDGE_VIEW_STATE_KEYS)
    for key in EDGE_HANDLE_KEYS:
        if key in edge:
            parsed = parse_handle(edge[key])
            if parsed is not None:
                edge[key] = parsed
    return edge


def canonical_graph(flow_data: dict[str, Any], *, keyed: bool = True) -> dict[str, Any]:
    """Return flow data in canonical form.

    With ``keyed``, nodes, edges and table rows whose ids are unique become
    mappings from id to entry, for comparison. Without it they stay lists,
    ordered by id (rows by ``(_pos, _id)``), for serialization. The result
    shares nested values with ``flow_data``; it is meant to be compared or
    serialized, not mutated.
    """
    graph = _without(flow_data, FLOW_VIEW_STATE_KEYS)
    for key, canonical in (("nodes", canonical_node), ("edges", canonical_edge)):
        entries = graph.get(key)
        if not isinstance(entries, list):
            continue
        if key == "nodes":
            entries = [canonical_node(entry, keyed=keyed) for entry in entries]
        else:
            entries = [canonical(entry) for entry in entries]
        if keyed:
            by_id = _by_id(entries, "id")
            graph[key] = by_id if by_id is not None else entries
        else:
            graph[key] = sorted(entries, key=_id_sort_key)
    return graph


def _by_id(entries: list[Any], id_key: str) -> dict[str, Any] | None:
    """Map each entry's id to it, or return None when an entry has no string id or two share one."""
    by_id: dict[str, Any] = {}
    for entry in entries:
        entry_id = entry.get(id_key) if isinstance(entry, dict) else None
        if not isinstance(entry_id, str) or entry_id in by_id:
            return None
        by_id[entry_id] = entry
    return by_id


def _id_sort_key(entry: Any) -> bytes:
    entry_id = entry.get("id") if isinstance(entry, dict) else None
    # Entries without a string id sort first; a graph that has them fails validation anyway.
    return utf16_sort_key(entry_id) if isinstance(entry_id, str) else b""


def canonical_graph_json(flow_data: dict[str, Any]) -> str:
    """Serialize flow data in canonical graph form, as RFC 8785 text."""
    return canonical_json(canonical_graph(flow_data, keyed=False))


def graph_hash(flow_data: dict[str, Any]) -> str:
    """Return the SHA-256 hex digest of flow data's canonical graph form."""
    encoded = canonical_graph_json(flow_data).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def graphs_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return whether two flow data mappings are the same graph, stopping at the first difference."""
    return values_equal(canonical_graph(left), canonical_graph(right))


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
    if not is_finite_number(value):
        raise _non_finite_error()
    return float(value)
