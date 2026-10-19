"""The index a keyed list gets while an apply call addresses it."""

from __future__ import annotations

import pytest
from lfx.services.flow_operations import FlowOperationValidationError, load_node_schema
from lfx.services.flow_operations.keyed_lists import ListIndex


def _table(rows: list[dict]) -> ListIndex:
    return ListIndex(load_node_schema().table, rows, context="rows")


def _outputs(items: list[dict]) -> ListIndex:
    keyed = load_node_schema().keyed_list_at({}, ("data", "node", "outputs"))
    return ListIndex(keyed, items, context="outputs")


def _ids(rows: list[dict]) -> list[str]:
    return [row["__id__"] for row in rows]


def test_a_table_is_indexed_in_any_order_and_rows_are_appended():
    rows = [{"__id__": "b", "__pos__": 2}, {"__id__": "a", "__pos__": 1}]
    index = _table(rows)

    index.add({"__id__": "c", "__pos__": 0.5}, context="rows")

    assert _ids(rows) == ["b", "a", "c"]
    assert index.slots == {"b": 0, "a": 1, "c": 2}


@pytest.mark.parametrize(
    ("removed", "expected_ids"),
    [("a", ["c", "b"]), ("b", ["a", "c"]), ("c", ["a", "b"])],
)
def test_removing_a_row_lets_the_last_row_take_its_slot(removed, expected_ids):
    rows = [{"__id__": "a", "__pos__": 1}, {"__id__": "b", "__pos__": 2}, {"__id__": "c", "__pos__": 3}]
    index = _table(rows)

    assert index.remove(removed)["__id__"] == removed

    assert _ids(rows) == expected_ids
    assert index.slots == {row_id: slot for slot, row_id in enumerate(expected_ids)}
    assert set(index.by_key) == set(expected_ids)


def test_replacing_a_row_keeps_its_slot():
    rows = [{"__id__": "a", "__pos__": 1}, {"__id__": "b", "__pos__": 2}]
    index = _table(rows)

    old = index.replace("a", {"__id__": "a", "__pos__": 5}, context="rows")

    assert old == {"__id__": "a", "__pos__": 1}
    assert rows == [{"__id__": "a", "__pos__": 5}, {"__id__": "b", "__pos__": 2}]
    assert index.by_key["a"] is rows[0]


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([{"__pos__": 1}], "non-empty string key"),
        ([{"__id__": "", "__pos__": 1}], "non-empty string key"),
        ([{"__id__": "a", "__pos__": 1}, {"__id__": "a", "__pos__": 2}], "two items have the key 'a'"),
        ([{"__id__": "a"}], "must be a finite number"),
        ([{"__id__": "a", "__pos__": "a0"}], "must be a finite number"),
        ([{"__id__": "a", "__pos__": True}], "must be a finite number"),
        ([{"__id__": "a", "__pos__": float("nan")}], "must be a finite number"),
        (["not a row"], "non-empty string key"),
    ],
)
def test_a_table_that_breaks_its_rules_cannot_be_indexed(rows, message):
    with pytest.raises(FlowOperationValidationError, match=message):
        _table(rows)


def test_rows_added_or_replaced_need_a_position():
    index = _table([{"__id__": "a", "__pos__": 1}])

    with pytest.raises(FlowOperationValidationError, match="must be a finite number"):
        index.add({"__id__": "b"}, context="rows")
    with pytest.raises(FlowOperationValidationError, match="must be a finite number"):
        index.replace("a", {"__id__": "a", "__pos__": None}, context="rows")


@pytest.mark.parametrize(
    ("items", "message"),
    [
        ([{"name": "a"}, {"name": "a"}], "two items have the key 'a'"),
        ([{"display_name": "no name"}], "non-empty string key"),
        ([{"name": 3}], "non-empty string key"),
    ],
)
def test_a_natural_list_needs_unique_string_keys(items, message):
    with pytest.raises(FlowOperationValidationError, match=message):
        _outputs(items)


def test_natural_lists_keep_the_order_writes_leave_them_in():
    items = [{"name": "b"}, {"name": "a"}, {"name": "d"}]
    index = _outputs(items)

    index.add({"name": "c"}, context="outputs")
    index.replace("b", {"name": "b", "hidden": True}, context="outputs")
    index.remove("a")

    assert items == [{"name": "b", "hidden": True}, {"name": "d"}, {"name": "c"}]
