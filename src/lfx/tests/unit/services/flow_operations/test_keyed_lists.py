"""The index a keyed list gets the first time a write reads it."""

from __future__ import annotations

import pytest
from lfx.services.flow_operations import FlowOperationValidationError, load_node_schema
from lfx.services.flow_operations.keyed_lists import ListIndex


def _table(rows: list) -> ListIndex:
    return ListIndex(load_node_schema().table, rows)


def _outputs(items: list) -> ListIndex:
    keyed = load_node_schema().keyed_list_at({}, ("data", "node", "outputs"))
    return ListIndex(keyed, items)


def _ids(rows: list[dict]) -> list[str]:
    return [row["__id__"] for row in rows]


def test_a_table_is_indexed_in_any_order_and_rows_are_appended():
    rows = [{"__id__": "b", "__pos__": 2}, {"__id__": "a", "__pos__": 1}]
    index = _table(rows)

    index.add("c", {"__id__": "c", "__pos__": 0.5})

    assert _ids(rows) == ["b", "a", "c"]
    assert index.slots == {"b": 0, "a": 1, "c": 2}
    assert index.problem() is None


@pytest.mark.parametrize(
    ("removed", "expected_ids"),
    [("a", ["c", "b"]), ("b", ["a", "c"]), ("c", ["a", "b"])],
)
def test_removing_a_positioned_item_lets_the_last_item_take_its_slot(removed, expected_ids):
    rows = [{"__id__": "a", "__pos__": 1}, {"__id__": "b", "__pos__": 2}, {"__id__": "c", "__pos__": 3}]
    index = _table(rows)

    assert index.remove(removed)["__id__"] == removed

    assert _ids(rows) == expected_ids
    assert index.slots == {row_id: slot for slot, row_id in enumerate(expected_ids)}
    assert index.remove(removed) is None


def test_removing_an_item_without_a_position_keeps_the_array_order():
    items = [{"name": "b"}, {"name": "a"}, {"name": "d"}]
    index = _outputs(items)

    index.remove("b")

    assert items == [{"name": "a"}, {"name": "d"}]
    assert index.slots == {"a": 0, "d": 1}
    assert index.unpositioned == 2


def test_replacing_an_item_keeps_its_slot():
    rows = [{"__id__": "a", "__pos__": 1}, {"__id__": "b", "__pos__": 2}]
    index = _table(rows)

    index.replace(index.slot("a"), {"__id__": "a", "__pos__": 5})

    assert rows == [{"__id__": "a", "__pos__": 5}, {"__id__": "b", "__pos__": 2}]
    assert index.slots == {"a": 0, "b": 1}


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
def test_a_list_that_breaks_its_rules_is_indexed_and_reports_the_first_problem(rows, message):
    assert message in _table(rows).problem()


def test_a_key_two_items_have_cannot_be_found():
    index = _table([{"__id__": "a", "__pos__": 1}, {"__id__": "a", "__pos__": 2}, {"__id__": "b", "__pos__": 3}])

    assert index.find("b", "rows") == 2
    assert index.find("missing", "rows") is None
    with pytest.raises(FlowOperationValidationError, match="rows: two items have the key 'a'"):
        index.find("a", "rows")


def test_items_without_a_position_are_counted_as_writes_change_them():
    index = _table([{"__id__": "a", "__pos__": 1}])

    index.add("b", {"__id__": "b"})
    assert index.unpositioned == 1
    index.replace(index.slot("b"), {"__id__": "b", "__pos__": 2})
    assert index.problem() is None
    index.position_changed(before=True, after=False)
    assert index.unpositioned == 1


@pytest.mark.parametrize(
    ("items", "message"),
    [
        ([{"name": "a", "__pos__": 1}, {"name": "a", "__pos__": 2}], "two items have the key 'a'"),
        ([{"display_name": "no name", "__pos__": 1}], "non-empty string key"),
        ([{"name": 3, "__pos__": 1}], "non-empty string key"),
    ],
)
def test_a_natural_list_needs_unique_string_keys(items, message):
    with pytest.raises(FlowOperationValidationError, match=message):
        _outputs(items).check_keys("outputs")
