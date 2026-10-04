"""Row identity in table values.

Every row of a table value stored in a flow carries a stable ``_id`` and a
fractional position ``_pos`` so that concurrent edits address rows instead of
indexes. They are bookkeeping for the flow's history, not data: components
never see them, so every place that hands a stored table to component code
strips them first.
"""

from __future__ import annotations

import itertools
from typing import Any

from lfx.services.flow_operations.canonical import values_equal
from lfx.services.flow_operations.exceptions import FlowDataValidationError
from lfx.services.flow_operations.fractional_index import generate_n_keys_between, is_order_key
from lfx.services.flow_operations.ids import new_table_row_id
from lfx.services.flow_operations.schema import load_node_schema

ROW_ID_KEY = "_id"
ROW_POSITION_KEY = "_pos"
ROW_KEYS = frozenset({ROW_ID_KEY, ROW_POSITION_KEY})


def strip_row_keys(rows: Any) -> Any:
    """Return table rows without ``_id`` and ``_pos``; anything that is not a list of rows is returned as is."""
    if not isinstance(rows, list):
        return rows
    return [
        {key: value for key, value in row.items() if key not in ROW_KEYS} if isinstance(row, dict) else row
        for row in rows
    ]


def strip_node_table_row_keys(node: Any) -> Any:
    """Strip ``_id`` and ``_pos`` from every table value of a flow node, in place, and return the node."""
    for value_path, field in _table_fields(node):
        field[value_path[-1]] = strip_row_keys(field[value_path[-1]])
    return node


def strip_flow_table_row_keys(flow_data: Any) -> Any:
    """Strip ``_id`` and ``_pos`` from the table values of every node of ``flow_data``, in place, and return it."""
    for node in _nodes(flow_data):
        strip_node_table_row_keys(node)
    return flow_data


def assign_row_ids(rows: list[Any], previous: Any = None) -> list[Any]:
    """Give one table value's rows the ids and positions a write needs, in place, and return them.

    Rows that already have a unique ``_id`` keep it. A row without one that
    equals a not yet matched row of ``previous`` (the stored value, apart from
    ids and positions) takes that row's id and position, so rewriting a table
    with the rows it already held does not turn every row into a new one; the
    others get a new random id. Rows keep their order: valid positions that
    already follow it are kept and the rest are filled in between them (or all
    rows get evenly spaced positions when the existing ones are out of order).
    A table with a row that is not an object is left for validation to report.
    """
    if not all(isinstance(row, dict) for row in rows):
        return rows
    used: set[str] = set()
    need_id: list[dict[str, Any]] = []
    for row in rows:
        row_id = row.get(ROW_ID_KEY)
        if _is_key(row_id) and row_id not in used:
            used.add(row_id)
        else:
            need_id.append(row)
    candidates = [
        row
        for row in (previous if isinstance(previous, list) else [])
        if isinstance(row, dict) and _is_key(row.get(ROW_ID_KEY))
    ]
    for row in need_id:
        content = _without_row_keys(row)
        match = next(
            (
                candidate
                for candidate in candidates
                if candidate[ROW_ID_KEY] not in used and _without_row_keys(candidate) == content
            ),
            None,
        )
        if match is not None:
            new_id = match[ROW_ID_KEY]
            if not _is_key(row.get(ROW_POSITION_KEY)) and _is_key(match.get(ROW_POSITION_KEY)):
                row[ROW_POSITION_KEY] = match[ROW_POSITION_KEY]
        else:
            new_id = new_table_row_id()
            while new_id in used:
                new_id = new_table_row_id()
        used.add(new_id)
        row[ROW_ID_KEY] = new_id
    positions = [row.get(ROW_POSITION_KEY) for row in rows]
    if not all(_is_key(position) for position in positions) or positions_keeping_order(positions) is None:
        filled = positions_keeping_order(positions) or generate_n_keys_between(None, None, len(rows))
        for row, position in zip(rows, filled, strict=True):
            row[ROW_POSITION_KEY] = position
    load_node_schema().table.sort(rows)
    return rows


def assign_table_row_ids(node: Any) -> Any:
    """Give every table value of a node being added row ids and positions (``assign_row_ids``), in place.

    Returns the node.
    """
    for value_path, field in _table_fields(node):
        assign_row_ids(field[value_path[-1]])
    return node


def assign_changed_table_row_ids(base: Any, target: Any) -> Any:
    """Give row ids and positions to the table values ``target`` adds or changes relative to ``base``, in place.

    This is what a writer that is not the editor (the assistant) does before
    saving, so its write passes the table rules: tables of new nodes get ids,
    a changed table keeps the ids of rows it still holds, and a table equal to
    the stored one is left as it is, ids or not. Returns ``target``.
    """
    stored: dict[str, dict[str, Any]] = {}
    for node in _nodes(base):
        if isinstance(node.get("id"), str):
            stored.setdefault(node["id"], {path[-2]: field.get("value") for path, field in _table_fields(node)})
    for node in _nodes(target):
        stored_tables = stored.get(node.get("id"), {})
        for value_path, field in _table_fields(node):
            field_name = value_path[-2]
            if field_name in stored_tables and _equal(stored_tables[field_name], field["value"]):
                continue
            assign_row_ids(field["value"], previous=stored_tables.get(field_name))
    return target


def positions_keeping_order(positions: list[Any]) -> list[str] | None:
    """Fill missing positions between their neighbours, or return None when the others are out of order."""
    present = [position for position in positions if _is_key(position)]
    if not all(is_order_key(position) for position in present):
        return None
    if any(left >= right for left, right in itertools.pairwise(present)):
        return None
    filled = list(positions)
    index = 0
    while index < len(filled):
        if _is_key(filled[index]):
            index += 1
            continue
        end = index
        while end < len(filled) and not _is_key(filled[end]):
            end += 1
        before = filled[index - 1] if index > 0 else None
        after = filled[end] if end < len(filled) else None
        filled[index:end] = generate_n_keys_between(before, after, end - index)
        index = end
    return filled


def _table_fields(node: Any) -> list[tuple[tuple[str, ...], dict[str, Any]]]:
    """Return ``(value path, field)`` for every template field of ``node`` whose value is a table list."""
    template: Any = node
    for key in ("data", "node", "template"):
        template = template.get(key) if isinstance(template, dict) else None
    if not isinstance(template, dict):
        return []
    schema = load_node_schema()
    fields = []
    for field_name, field in template.items():
        value_path = ("data", "node", "template", field_name, "value")
        if (
            isinstance(field, dict)
            and isinstance(field.get("value"), list)
            and schema.keyed_list_at(node, value_path) is schema.table
        ):
            fields.append((value_path, field))
    return fields


def _nodes(graph: Any) -> list[dict[str, Any]]:
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    return [node for node in nodes if isinstance(node, dict)] if isinstance(nodes, list) else []


def _without_row_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in ROW_KEYS}


def _equal(left: Any, right: Any) -> bool:
    try:
        return values_equal(left, right)
    except FlowDataValidationError:
        return False


def _is_key(value: Any) -> bool:
    return isinstance(value, str) and bool(value)
