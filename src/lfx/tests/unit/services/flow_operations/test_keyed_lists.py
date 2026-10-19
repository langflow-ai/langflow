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
    return [row["_id"] for row in rows]


def test_a_table_is_indexed_in_any_order_and_rows_are_appended():
    rows = [{"_id": "b", "_pos": 2}, {"_id": "a", "_pos": 1}]
    index = _table(rows)

    index.add({"_id": "c", "_pos": 0.5}, context="rows")

    assert _ids(rows) == ["b", "a", "c"]
    assert index.slots == {"b": 0, "a": 1, "c": 2}


@pytest.mark.parametrize(
    ("removed", "expected_ids"),
    [("a", ["c", "b"]), ("b", ["a", "c"]), ("c", ["a", "b"])],
)
def test_removing_a_row_lets_the_last_row_take_its_slot(removed, expected_ids):
    rows = [{"_id": "a", "_pos": 1}, {"_id": "b", "_pos": 2}, {"_id": "c", "_pos": 3}]
    index = _table(rows)

    assert index.remove(removed)["_id"] == removed

    assert _ids(rows) == expected_ids
    assert index.slots == {row_id: slot for slot, row_id in enumerate(expected_ids)}
    assert set(index.by_key) == set(expected_ids)


def test_replacing_a_row_keeps_its_slot():
    rows = [{"_id": "a", "_pos": 1}, {"_id": "b", "_pos": 2}]
    index = _table(rows)

    old = index.replace("a", {"_id": "a", "_pos": 5}, context="rows")

    assert old == {"_id": "a", "_pos": 1}
    assert rows == [{"_id": "a", "_pos": 5}, {"_id": "b", "_pos": 2}]
    assert index.by_key["a"] is rows[0]


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([{"_pos": 1}], "non-empty string key"),
        ([{"_id": "", "_pos": 1}], "non-empty string key"),
        ([{"_id": "a", "_pos": 1}, {"_id": "a", "_pos": 2}], "two items have the key 'a'"),
        ([{"_id": "a"}], "must be a finite number"),
        ([{"_id": "a", "_pos": "a0"}], "must be a finite number"),
        ([{"_id": "a", "_pos": True}], "must be a finite number"),
        ([{"_id": "a", "_pos": float("nan")}], "must be a finite number"),
        (["not a row"], "non-empty string key"),
    ],
)
def test_a_table_that_breaks_its_rules_cannot_be_indexed(rows, message):
    with pytest.raises(FlowOperationValidationError, match=message):
        _table(rows)


def test_rows_added_or_replaced_need_a_position():
    index = _table([{"_id": "a", "_pos": 1}])

    with pytest.raises(FlowOperationValidationError, match="must be a finite number"):
        index.add({"_id": "b"}, context="rows")
    with pytest.raises(FlowOperationValidationError, match="must be a finite number"):
        index.replace("a", {"_id": "a", "_pos": None}, context="rows")


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
