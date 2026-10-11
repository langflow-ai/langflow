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


def test_rows_are_ordered_by_numeric_position_then_id():
    rows = [{"_id": "a", "_pos": 1}, {"_id": "b", "_pos": 1}, {"_id": "c", "_pos": 1.5}, {"_id": "d", "_pos": 10}]
    index = _table(rows)

    index.add({"_id": "e", "_pos": 2}, context="rows")
    index.add({"_id": "0", "_pos": 1}, context="rows")

    assert [row["_id"] for row in rows] == ["0", "a", "b", "c", "e", "d"]


def test_a_row_whose_position_changed_goes_back_in_order():
    rows = [{"_id": "a", "_pos": 1}, {"_id": "b", "_pos": 2}, {"_id": "c", "_pos": 3}]
    index = _table(rows)
    row = index.by_key["a"]
    before = index.order(row, context="rows")

    row["_pos"] = 2.5
    index.reorder(row, before, context="rows")

    assert [item["_id"] for item in rows] == ["b", "a", "c"]


def test_replacing_and_removing_rows_keeps_the_index_and_the_list_in_step():
    rows = [{"_id": "a", "_pos": 1}, {"_id": "b", "_pos": 2}]
    index = _table(rows)

    index.replace("a", {"_id": "a", "_pos": 3}, context="rows")
    removed = index.remove("b", context="rows")

    assert removed == {"_id": "b", "_pos": 2}
    assert rows == [{"_id": "a", "_pos": 3}]
    assert index.by_key == {"a": rows[0]}


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([{"_pos": 1}], "non-empty string id"),
        ([{"_id": "", "_pos": 1}], "non-empty string id"),
        ([{"_id": "a", "_pos": 1}, {"_id": "a", "_pos": 2}], "two items have the key 'a'"),
        ([{"_id": "a"}], "must be a finite number"),
        ([{"_id": "a", "_pos": "a0"}], "must be a finite number"),
        ([{"_id": "a", "_pos": True}], "must be a finite number"),
        ([{"_id": "a", "_pos": float("nan")}], "must be a finite number"),
        ([{"_id": "a", "_pos": 2}, {"_id": "b", "_pos": 1}], r"must be in \(_pos, _id\) order"),
        ([{"_id": "b", "_pos": 1}, {"_id": "a", "_pos": 1}], r"must be in \(_pos, _id\) order"),
        (["not a row"], "non-empty string id"),
    ],
)
def test_a_table_that_breaks_its_rules_cannot_be_indexed(rows, message):
    with pytest.raises(FlowOperationValidationError, match=message):
        _table(rows)


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
    items = [{"name": "b"}, {"name": "a"}]
    index = _outputs(items)

    index.add({"name": "c"}, context="outputs")
    index.replace("b", {"name": "b", "hidden": True}, context="outputs")
    index.remove("a", context="outputs")

    assert items == [{"name": "b", "hidden": True}, {"name": "c"}]
