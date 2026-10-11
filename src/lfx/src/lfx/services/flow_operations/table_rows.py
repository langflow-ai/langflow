"""Row identity in table values.

Every row of a table value stored in a flow carries a stable ``_id`` and a
numeric position ``_pos``, so that concurrent edits address rows instead of
indexes. The table's order is its rows' ``(_pos, _id)``, not their places in
the stored array, which nothing keeps sorted. Both keys are bookkeeping for the
flow's history, not data: components never see them, so every place that
hands a stored table to anything outside the engine strips them first, and
puts the rows in order as it does.
"""

from __future__ import annotations

from typing import Any

from lfx.services.flow_operations.canonical import is_row_position, ordered_rows, values_equal
from lfx.services.flow_operations.ids import new_table_row_id
from lfx.services.flow_operations.schema import load_node_schema

ROW_ID_KEY = load_node_schema().table.key[0]
ROW_POSITION_KEY = load_node_schema().table.position
ROW_KEYS = frozenset({ROW_ID_KEY, ROW_POSITION_KEY})


def strip_row_keys(rows: Any) -> Any:
    """Return table rows in order and without ``_id`` and ``_pos``; a value that is not a list is returned as is."""
    if not isinstance(rows, list):
        return rows
    return [
        {key: value for key, value in row.items() if key not in ROW_KEYS} if isinstance(row, dict) else row
        for row in ordered_rows(rows)
    ]


def strip_node_table_row_keys(node: Any) -> Any:
    """Order the rows of every table value of a flow node and strip ``_id`` and ``_pos``, in place.

    Returns the node.
    """
    for value_path, field in _table_fields(node):
        field[value_path[-1]] = strip_row_keys(field[value_path[-1]])
    return node


def strip_flow_table_row_keys(flow_data: Any) -> Any:
    """Order and strip the table values of every node of ``flow_data``, in place, and return it."""
    for node in _nodes(flow_data):
        strip_node_table_row_keys(node)
    return flow_data


def assign_row_ids(rows: list[Any], previous: Any = None) -> list[Any]:
    """Give one table value's rows the ids and positions a write needs, in place, and return them.

    Rows that already have a unique ``_id`` keep it, and rows with a position
    keep it. A row without an id that equals a not yet matched row of
    ``previous`` (the stored value, apart from ids and positions) takes that
    row's id and position; the others get a new random id. Rows still without
    a position get one that keeps them where they are stored
    (``fill_missing_positions``), so a legacy table keeps its order. A table
    with a row that is not an object is left for validation to report.
    """
    if not all(isinstance(row, dict) for row in rows):
        return rows
    match_row_ids(rows, previous)
    fill_missing_positions(rows)
    return rows


def match_row_ids(rows: list[dict[str, Any]], previous: Any = None) -> None:
    """Give every row without a unique ``_id`` one, in place, keeping stored ids.

    A row that equals a not yet matched row of ``previous`` (the stored value,
    apart from ids and positions) takes that row's id, and its position when it
    has none; the others get a new random id. So a table rewritten with the rows
    it already held keeps them, and a new row changes nothing about the others.
    """
    used: set[str] = set()
    need_id: list[dict[str, Any]] = []
    for row in rows:
        row_id = row.get(ROW_ID_KEY)
        if _is_id(row_id) and row_id not in used:
            used.add(row_id)
        else:
            need_id.append(row)
    candidates = [
        row
        for row in (previous if isinstance(previous, list) else [])
        if isinstance(row, dict) and _is_id(row.get(ROW_ID_KEY))
    ]
    for row in need_id:
        content = _without_row_keys(row)
        match = next(
            (
                candidate
                for candidate in candidates
                if candidate[ROW_ID_KEY] not in used and values_equal(_without_row_keys(candidate), content)
            ),
            None,
        )
        if match is not None:
            new_id = match[ROW_ID_KEY]
            if not is_row_position(row.get(ROW_POSITION_KEY)) and is_row_position(match.get(ROW_POSITION_KEY)):
                row[ROW_POSITION_KEY] = match[ROW_POSITION_KEY]
        else:
            new_id = new_table_row_id()
            while new_id in used:
                new_id = new_table_row_id()
        used.add(new_id)
        row[ROW_ID_KEY] = new_id


def fill_missing_positions(rows: list[dict[str, Any]]) -> list[int]:
    """Give each row without a valid position one that keeps it where it is stored, in place.

    Positioned rows keep their positions. A run of rows without one is spread
    evenly between the positioned rows stored before and after it, or placed one
    apart before the first or after the last; when those neighbours are out of
    order, the run follows the one before it. A table with no positions at all
    gets ``1..n``. Returns the indexes of the rows it gave a position.
    """
    filled: list[int] = []
    index = 0
    while index < len(rows):
        if is_row_position(rows[index].get(ROW_POSITION_KEY)):
            index += 1
            continue
        end = index
        while end < len(rows) and not is_row_position(rows[end].get(ROW_POSITION_KEY)):
            end += 1
        count = end - index
        before = rows[index - 1][ROW_POSITION_KEY] if index > 0 else None
        after = rows[end][ROW_POSITION_KEY] if end < len(rows) else None
        if before is not None and after is not None and before < after:
            positions = [before + (after - before) * step / (count + 1) for step in range(1, count + 1)]
        elif before is not None:
            positions = [before + step for step in range(1, count + 1)]
        elif after is not None:
            positions = [after - count + step for step in range(count)]
        else:
            positions = list(range(1, count + 1))
        for offset, position in enumerate(positions):
            rows[index + offset][ROW_POSITION_KEY] = position
            filled.append(index + offset)
        index = end
    return filled


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
            if field_name in stored_tables and values_equal(stored_tables[field_name], field["value"]):
                continue
            assign_row_ids(field["value"], previous=stored_tables.get(field_name))
    return target


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


def _is_id(value: Any) -> bool:
    return isinstance(value, str) and bool(value)
