"""Canonical form of flow data, for equality and checkpoint hashes.

Two graphs are equal when their canonical forms are the same JSON value. The
form is the graph with its view state removed, and with everything whose order
is not state keyed by id:

- JSON values compare as RFC 8785 (JSON Canonicalization Scheme) prints them:
  ``1`` and ``1.0`` are the same value, ``true`` and ``1`` are not, and key
  order is never a change. JavaScript cannot tell integers from floats, so a
  ``0.0`` that comes back from the editor as ``0`` must not count as an edit.
- ``nodes`` and ``edges`` are collections keyed by id, and the items of every
  keyed list (outputs, tool actions, table rows) are collections keyed by item
  key. Their array order is not state; a keyed list's order is its items'
  ``(__pos__, key)``.
- View state is everything ``node_schema.json`` declares display only. It is
  stored but never recorded and never compared.
- An edge's ``sourceHandle`` and ``targetHandle`` strings are JSON with ``œ``
  standing for ``"``. They compare by the object they encode.
- A handle's ``inputTypes`` and ``output_types`` compare as sets. The hash
  keeps their order, so that no stored hash changes.

Equality compares the form structurally and stops at the first difference;
only ``graph_hash`` serializes it, with collections ordered, as RFC 8785 text.
The form is defined for any JSON graph, valid or not: enforcing the rules is
validation's job. It is the form of the Rust engine (``lfx::ops::canonical``),
and it gives the same hashes.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from json.encoder import encode_basestring
from typing import Any, NoReturn

from lfx.services.flow_operations.exceptions import FlowDataValidationError
from lfx.services.flow_operations.limits import broken_limit, check_graph_limits
from lfx.services.flow_operations.schema import (
    DOUBLE_OVERFLOW,
    OUTPUTS_PATH,
    KeyedList,
    field_value_path,
    is_finite_number,
    is_row_position,
    load_node_schema,
)

__all__ = [
    "EDGE_HANDLE_KEYS",
    "EDGE_VIEW_STATE_KEYS",
    "NODE_VIEW_STATE_KEYS",
    "TYPE_LIST_KEYS",
    "canonical_edge",
    "canonical_graph",
    "canonical_graph_json",
    "canonical_json",
    "canonical_node",
    "edge_data_with_type_sets",
    "graph_hash",
    "graphs_equal",
    "handle_with_type_sets",
    "is_finite_number",
    "is_row_position",
    "item_order",
    "json_type",
    "ordered_rows",
    "parse_handle",
    "utf16_sort_key",
    "values_equal",
]

_SCHEMA = load_node_schema()
NODE_VIEW_STATE_KEYS = _SCHEMA.node_view_state
EDGE_VIEW_STATE_KEYS = _SCHEMA.edge_view_state
EDGE_HANDLE_KEYS = ("sourceHandle", "targetHandle")
# The keys of a handle that hold a list of types. Their order is not state.
TYPE_LIST_KEYS = ("inputTypes", "output_types")
_NODE_DATA_VIEW_STATE = _SCHEMA.node_data_view_state
_TEMPLATE_VIEW_STATE = _SCHEMA.template_view_state
_FIELD_VIEW_STATE = _SCHEMA.field_view_state
_OUTPUTS_LIST = _SCHEMA.natural_list_at(OUTPUTS_PATH)
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


def _non_finite_error() -> FlowDataValidationError:
    return FlowDataValidationError("NaN, Infinity and integers too large for a double are not valid JSON numbers")


def _as_double(value: float) -> float:
    """Return a JSON number as the double JavaScript holds, which is what its canonical form prints."""
    if value.__class__ is float:
        if value - value != 0.0:
            raise _non_finite_error()
        return value
    if isinstance(value, float):
        return _as_double(float(value))
    if not -DOUBLE_OVERFLOW < value < DOUBLE_OVERFLOW:
        raise _non_finite_error()
    return float(value)


def _format_number(value: float) -> str:
    if isinstance(value, int) and -_MAX_SAFE_INTEGER <= value <= _MAX_SAFE_INTEGER:
        # An integer prints exactly while JavaScript holds it exactly.
        return str(int(value))
    value = _as_double(value)
    if value == 0:
        return "0"
    # repr() gives the shortest digits that round-trip, which is also what
    # ECMAScript's Number::toString chooses; only the layout differs.
    text = repr(abs(value))
    sign = "-" if value < 0 else ""
    if text.endswith(".0") and "e" not in text:
        # A plain integral double below 1e16: its integer digits are its form.
        return sign + text[:-2]
    _, digit_tuple, exponent = Decimal(text).as_tuple()
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


def _sorted_keys(mapping: dict[str, Any]) -> list[str]:
    keys = list(mapping)
    ascii_only = True
    for key in keys:
        if key.__class__ is not str and not isinstance(key, str):
            msg = f"object key {key!r} is not a string"
            raise FlowDataValidationError(msg)
        if ascii_only and not key.isascii():
            ascii_only = False
    if ascii_only:
        keys.sort()
    else:
        keys.sort(key=utf16_sort_key)
    return keys


def _write_canonical(value: Any, parts: list[str]) -> None:
    append = parts.append
    cls = value.__class__
    if cls is str:
        append(encode_basestring(value))
    elif cls is dict:
        append("{")
        first = True
        for key in _sorted_keys(value):
            if first:
                first = False
            else:
                append(",")
            append(encode_basestring(key))
            append(":")
            item = value[key]
            if item.__class__ is str:
                append(encode_basestring(item))
            else:
                _write_canonical(item, parts)
        append("}")
    elif cls is list:
        append("[")
        first = True
        for item in value:
            if first:
                first = False
            else:
                append(",")
            if item.__class__ is str:
                append(encode_basestring(item))
            else:
                _write_canonical(item, parts)
        append("]")
    elif value is None:
        append("null")
    elif value is True:
        append("true")
    elif value is False:
        append("false")
    elif cls is int or cls is float:
        append(_format_number(value))
    else:
        kind = json_type(value)  # raises for anything that is not JSON
        if kind == "number":
            append(_format_number(value))
        elif kind == "string":
            append(encode_basestring(str(value)))
        elif kind == "array":
            _write_canonical(list(value), parts)
        else:
            _write_canonical(dict(value), parts)


def canonical_json(value: Any) -> str:
    """Serialize a JSON value in RFC 8785 canonical form.

    The value must meet the JSON limits (``limits.py``): RFC 8785 text cannot
    hold a lone surrogate.
    """
    check_graph_limits(value)
    return canonical_text(value)


def canonical_text(value: Any) -> str:
    """``canonical_json`` for a value that is known to meet the JSON limits."""
    parts: list[str] = []
    _write_canonical(value, parts)
    return "".join(parts)


# --- Keyed list order ---------------------------------------------------------------------------


def item_order(keyed: KeyedList, items: list[Any]) -> list[int]:
    """The array indexes of a keyed list's items in its order.

    By ``(__pos__, key)``, or as stored when an item has no numeric position or
    no string key. Positions compare as the doubles JavaScript holds (``-0``
    before ``0``, as Rust's total order puts them), and keys by UTF-16 code
    units.
    """
    position_key = keyed.position
    key_of = keyed.key_of
    keys = []
    for item in items:
        if not isinstance(item, dict) or position_key not in item:
            return list(range(len(items)))
        position = item[position_key]
        if not is_row_position(position):
            return list(range(len(items)))
        key = key_of(item)
        if key is None:
            return list(range(len(items)))
        double = float(position)
        keys.append((double, math.copysign(1.0, double), utf16_sort_key(key)))
    return sorted(range(len(items)), key=keys.__getitem__)


def ordered_rows(rows: list[Any]) -> list[Any]:
    """Return a table's rows in order: by ``(__pos__, __id__)``, or as stored for a legacy table without them.

    A table's order is its rows' positions, not their places in the array.
    Positions compare as the doubles JavaScript holds and ids by UTF-16 code
    units, as the editor sorts them.
    """
    return [rows[slot] for slot in item_order(_SCHEMA.table, rows)]


# --- Handles ------------------------------------------------------------------------------------


def _reject_constant(token: str) -> NoReturn:
    msg = f"{token} is not valid JSON"
    raise ValueError(msg)


def parse_handle(handle: Any) -> dict[str, Any] | None:
    """Return the object a handle string encodes (JSON with ``œ`` for ``"``), or None when it encodes none.

    The string is parsed as strict JSON, as JavaScript's ``JSON.parse`` reads
    it: the ``NaN``, ``Infinity`` and ``-Infinity`` tokens do not parse. A
    handle that breaks the JSON limits (``limits.py``) encodes none either.
    """
    if not isinstance(handle, str):
        return None
    try:
        parsed = json.loads(handle.replace(_HANDLE_QUOTE, '"'), parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        return None
    return parsed if isinstance(parsed, dict) and broken_limit(parsed) is None else None


def handle_with_type_sets(handle: Any) -> Any:
    """A handle object with each type list sorted and without repeats; any other value as it is.

    Two handles that differ only in the order of their types are then equal.
    Raises for a type that holds a number that is not finite.
    """
    if not isinstance(handle, dict):
        return handle
    copied = dict(handle)
    for key in TYPE_LIST_KEYS:
        types = copied.get(key)
        if isinstance(types, list):
            by_text = sorted((canonical_text(item), index) for index, item in enumerate(types))
            kept: list[Any] = []
            last = None
            for text, index in by_text:
                if text != last:
                    kept.append(types[index])
                    last = text
            copied[key] = kept
    return copied


def edge_data_with_type_sets(data: Any) -> Any:
    """An edge's ``data``, with ``handle_with_type_sets`` on each handle object in it."""
    if not isinstance(data, dict):
        return data
    copied = dict(data)
    for key in EDGE_HANDLE_KEYS:
        if key in copied:
            copied[key] = handle_with_type_sets(copied[key])
    return copied


# --- The canonical form of a graph -----------------------------------------------------------------


class _Node:
    """A node of a graph keyed for comparison, taken as it is: made canonical only when it differs as it is."""

    __slots__ = ("node",)

    def __init__(self, node: Any) -> None:
        self.node = node


def _without(mapping: dict[str, Any], keys: frozenset[str]) -> dict[str, Any]:
    return {key: item for key, item in mapping.items() if key not in keys}


def _keyed_items(keyed: KeyedList, items: Any, *, keyed_mode: bool) -> Any:
    """A keyed list's items: by item key for comparison, in the list's order for the hash.

    A list with an item that has no string key, or two items with one key,
    keeps its array, which is then its order.
    """
    if not isinstance(items, list):
        return items
    if keyed_mode:
        by_key: dict[str, Any] = {}
        key_of = keyed.key_of
        for item in items:
            key = key_of(item)
            if key is None or key in by_key:
                return items
            by_key[key] = item
        return by_key
    return [items[slot] for slot in item_order(keyed, items)]


def canonical_template_field(field: Any) -> Any:
    """Return a template field without its display-only keys."""
    if not isinstance(field, dict):
        return field
    return _without(field, _FIELD_VIEW_STATE)


def _canonical_field(node: Any, key: str, field: Any, *, keyed: bool) -> Any:
    if not isinstance(field, dict):
        return field
    canon = _without(field, _FIELD_VIEW_STATE)
    if "value" in field:
        keyed_list = _SCHEMA.keyed_list_at(node, field_value_path(key))
        if keyed_list is not None:
            canon["value"] = _keyed_items(keyed_list, field["value"], keyed_mode=keyed)
    return canon


def canonical_node(node: Any, *, keyed: bool = True) -> Any:
    """Return a node without view state and with its keyed lists as collections.

    Shares unchanged values with ``node``. With ``keyed``, the items of a keyed
    list whose keys are unique become a mapping from key to item; otherwise
    they are put in order. A list with keyless or repeated items keeps its
    array, which is its order.
    """
    if not isinstance(node, dict):
        return node
    canon = _without(node, NODE_VIEW_STATE_KEYS)
    data = node.get("data")
    if not isinstance(data, dict):
        return canon
    body = data.get("node")
    if not isinstance(body, dict):
        return canon
    canon_body = _without(body, _NODE_DATA_VIEW_STATE)
    if "outputs" in body:
        canon_body["outputs"] = _keyed_items(_OUTPUTS_LIST, body["outputs"], keyed_mode=keyed)
    template = body.get("template")
    if isinstance(template, dict):
        canon_body["template"] = {
            key: _canonical_field(node, key, field, keyed=keyed)
            for key, field in template.items()
            if key not in _TEMPLATE_VIEW_STATE
        }
    canon_data = dict(data)
    canon_data["node"] = canon_body
    canon["data"] = canon_data
    return canon


def canonical_edge(edge: Any, *, keyed: bool = True) -> Any:
    """Return an edge without view state, its handle strings replaced by the objects they encode.

    With ``keyed``, for comparison, each handle's type lists are sets. The hash
    keeps their order, so that no stored hash changes.
    """
    if not isinstance(edge, dict):
        return edge
    canon = _without(edge, EDGE_VIEW_STATE_KEYS)
    for key in EDGE_HANDLE_KEYS:
        if key in edge:
            parsed = parse_handle(edge[key])
            if parsed is not None:
                canon[key] = handle_with_type_sets(parsed) if keyed else parsed
    if keyed and "data" in edge:
        canon["data"] = edge_data_with_type_sets(edge["data"])
    return canon


def _entry_id(entry: Any, id_key: str) -> str | None:
    if entry.__class__ is _Node:
        entry = entry.node
    entry_id = entry.get(id_key) if isinstance(entry, dict) else None
    return entry_id if isinstance(entry_id, str) else None


def _by_id(entries: list[Any], id_key: str) -> dict[str, Any] | None:
    """Map each entry's id to it, or return None when an entry has no string id or two share one."""
    by_id: dict[str, Any] = {}
    for entry in entries:
        entry_id = _entry_id(entry, id_key)
        if entry_id is None or entry_id in by_id:
            return None
        by_id[entry_id] = entry
    return by_id


def _id_sort_key(entry: Any) -> tuple[int, bytes]:
    entry_id = _entry_id(entry, "id")
    # Entries without a string id sort first; a graph that has them fails validation anyway.
    return (0, b"") if entry_id is None else (1, utf16_sort_key(entry_id))


def canonical_graph(flow_data: Any, *, keyed: bool = True) -> Any:
    """Return flow data in canonical form.

    With ``keyed``, nodes and edges whose ids are unique become mappings from
    id to entry, for comparison. Without it they stay lists, ordered by id,
    for serialization. The result shares nested values with ``flow_data``; it
    is meant to be compared or serialized, not mutated.
    """
    if not isinstance(flow_data, dict):
        return flow_data
    graph = {key: value for key, value in flow_data.items() if not _SCHEMA.is_flow_view_state(key)}
    for key in ("nodes", "edges"):
        entries = graph.get(key)
        if not isinstance(entries, list):
            continue
        if key == "nodes":
            canon = [canonical_node(entry, keyed=keyed) for entry in entries]
        else:
            canon = [canonical_edge(entry, keyed=keyed) for entry in entries]
        if keyed:
            by_id = _by_id(canon, "id")
            graph[key] = by_id if by_id is not None else canon
        else:
            graph[key] = sorted(canon, key=_id_sort_key)
    return graph


def _comparison_graph(flow_data: Any) -> Any:
    """The canonical form for comparison, with each node taken as it is (``_Node``)."""
    if not isinstance(flow_data, dict):
        return flow_data
    graph = {key: value for key, value in flow_data.items() if not _SCHEMA.is_flow_view_state(key)}
    nodes = graph.get("nodes")
    if isinstance(nodes, list):
        wrapped = [_Node(node) for node in nodes]
        by_id = _by_id(wrapped, "id")
        graph["nodes"] = by_id if by_id is not None else wrapped
    edges = graph.get("edges")
    if isinstance(edges, list):
        canon = [canonical_edge(edge, keyed=True) for edge in edges]
        by_id = _by_id(canon, "id")
        graph["edges"] = by_id if by_id is not None else canon
    return graph


def canonical_graph_json(flow_data: Any) -> str:
    """Serialize flow data in canonical graph form, as RFC 8785 text.

    ``flow_data`` must meet the JSON limits (``limits.py``) as it is given: its
    canonical form drops view state and reads handle strings, so the limits
    are checked before it is built.
    """
    check_graph_limits(flow_data)
    return canonical_graph_text(flow_data)


def canonical_graph_text(flow_data: Any) -> str:
    """``canonical_graph_json`` for a graph that is known to meet the JSON limits."""
    return canonical_text(canonical_graph(flow_data, keyed=False))


def graph_hash(flow_data: Any) -> str:
    """Return the SHA-256 hex digest of flow data's canonical graph form."""
    return hashlib.sha256(canonical_graph_json(flow_data).encode("utf-8")).hexdigest()


def graph_hash_checked(flow_data: Any) -> str:
    """``graph_hash`` for a graph that is known to meet the JSON limits."""
    return hashlib.sha256(canonical_graph_text(flow_data).encode("utf-8")).hexdigest()


# --- Equality -------------------------------------------------------------------------------------


def values_equal(left: Any, right: Any) -> bool:
    """Return whether two JSON values have the same canonical form, stopping at the first difference.

    The comparison never serializes: objects compare key by key in any order,
    arrays item by item, and numbers as the doubles JavaScript would hold. A
    number that is not finite raises when the comparison reaches it.
    """
    left_cls = left.__class__
    right_cls = right.__class__
    if left_cls is str:
        return right_cls is str and left == right
    if left_cls is dict and right_cls is dict:
        if len(left) != len(right):
            return False
        for key, value in left.items():
            if key.__class__ is not str and not isinstance(key, str):
                msg = f"object key {key!r} is not a string"
                raise FlowDataValidationError(msg)
            if key not in right:
                return False
            other = right[key]
            if value.__class__ is str:
                if other.__class__ is not str or value != other:
                    return False
            elif not values_equal(value, other):
                return False
        return True
    if left_cls is list and right_cls is list:
        if len(left) != len(right):
            return False
        return all(values_equal(a, b) for a, b in zip(left, right, strict=True))
    if (left_cls is int or left_cls is float) and (right_cls is int or right_cls is float):
        return _as_double(left) == _as_double(right)
    if left is None or left_cls is bool:
        return left is right
    return _values_equal_slow(left, right)


def _values_equal_slow(left: Any, right: Any) -> bool:
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


def _nodes_equal(left: Any, right: Any) -> bool:
    """Whether two nodes have the same canonical form; nodes equal as they are skip building it."""
    try:
        if values_equal(left, right):
            return True
    except FlowDataValidationError:
        pass
    return _canon_equal(canonical_node(left), canonical_node(right))


def _canon_equal(left: Any, right: Any) -> bool:
    left_node = left.__class__ is _Node
    right_node = right.__class__ is _Node
    if left_node or right_node:
        if left_node and right_node:
            return _nodes_equal(left.node, right.node)
        if left_node:
            return _canon_equal(canonical_node(left.node), right)
        return _canon_equal(left, canonical_node(right.node))
    if left.__class__ is dict and right.__class__ is dict:
        if len(left) != len(right):
            return False
        return all(key in right and _canon_equal(value, right[key]) for key, value in left.items())
    if left.__class__ is list and right.__class__ is list:
        if len(left) != len(right):
            return False
        return all(_canon_equal(a, b) for a, b in zip(left, right, strict=True))
    return values_equal(left, right)


def _check_finite_value(value: Any) -> None:
    """Raise for a number that is not finite anywhere in ``value``."""
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif item.__class__ is _Node:
            try:
                _check_finite_value(item.node)
            except FlowDataValidationError:
                stack.append(canonical_node(item.node))
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            _as_double(item)


def graphs_equal(left: Any, right: Any) -> bool:
    """Return whether two flow data mappings are the same graph, stopping at the first difference.

    Graphs that differ are then checked to the end for numbers that are not
    finite, so which answer such a number gets never depends on where the
    difference is.
    """
    left_canon = _comparison_graph(left)
    right_canon = _comparison_graph(right)
    equal = _canon_equal(left_canon, right_canon)
    if not equal:
        _check_finite_value(left_canon)
        _check_finite_value(right_canon)
    return equal
