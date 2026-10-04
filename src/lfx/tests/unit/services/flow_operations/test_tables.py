"""Table rows: diff-aware validation, repair and stripping."""

from __future__ import annotations

import copy
import re

import pytest
from lfx.services.flow_operations import (
    FlowDataValidationError,
    GraphViolationCode,
    find_graph_violations,
    repair_flow_data,
    validate_flow_data,
)
from lfx.services.flow_operations.table_rows import (
    assign_changed_table_row_ids,
    assign_table_row_ids,
    strip_flow_table_row_keys,
    strip_row_keys,
)

TABLE_PATH = ("nodes", 0, "data", "node", "template", "headers", "value")


def _graph(rows) -> dict:
    return {
        "nodes": [
            {
                "id": "api",
                "data": {
                    "node": {
                        "template": {
                            "headers": {"type": "table", "_input_type": "TableInput", "value": rows},
                            "url": {"type": "str", "value": "http://x"},
                        }
                    }
                },
            }
        ],
        "edges": [],
    }


LEGACY = [{"key": "Accept", "value": "json"}, {"key": "Auth", "value": "token"}]
KEYED = [
    {"_id": "r1", "_pos": "a0", "key": "Accept", "value": "json"},
    {"_id": "r2", "_pos": "a1", "key": "Auth", "value": "token"},
]
EMPTY = {"nodes": [], "edges": []}


def _codes(violations) -> list[tuple[GraphViolationCode, tuple]]:
    return [(violation.code, violation.path) for violation in violations]


def test_tables_are_not_checked_without_a_base():
    assert find_graph_violations(_graph(LEGACY)) == []


def test_an_unchanged_legacy_table_is_accepted():
    graph = _graph(LEGACY)
    changed_elsewhere = copy.deepcopy(graph)
    changed_elsewhere["nodes"][0]["data"]["node"]["template"]["url"]["value"] = "http://y"

    assert find_graph_violations(changed_elsewhere, base=graph) == []


def test_an_added_legacy_table_is_refused():
    assert _codes(find_graph_violations(_graph(LEGACY), base=EMPTY)) == [
        (GraphViolationCode.TABLE_ROW_ID_MISSING, (*TABLE_PATH, 0, "_id")),
        (GraphViolationCode.TABLE_ROW_POS_INVALID, (*TABLE_PATH, 0, "_pos")),
        (GraphViolationCode.TABLE_ROW_ID_MISSING, (*TABLE_PATH, 1, "_id")),
        (GraphViolationCode.TABLE_ROW_POS_INVALID, (*TABLE_PATH, 1, "_pos")),
    ]


def test_a_keyed_table_is_accepted_when_added_or_changed():
    changed = copy.deepcopy(KEYED)
    changed[1]["value"] = "other"

    assert find_graph_violations(_graph(KEYED), base=EMPTY) == []
    assert find_graph_violations(_graph(changed), base=_graph(KEYED)) == []


def test_replacing_a_keyed_table_with_id_less_rows_is_refused():
    violations = find_graph_violations(_graph([*LEGACY[:1]]), base=_graph(KEYED))

    assert {violation.code for violation in violations} == {
        GraphViolationCode.TABLE_ROW_ID_MISSING,
        GraphViolationCode.TABLE_ROW_POS_INVALID,
    }


def test_the_first_edit_of_a_legacy_table_writes_it_whole_with_ids():
    assert find_graph_violations(_graph(KEYED), base=_graph(LEGACY)) == []


def test_duplicate_ids_and_unsorted_rows_are_refused():
    duplicate = [dict(KEYED[0]), {**KEYED[1], "_id": "r1"}]
    unsorted = [KEYED[1], KEYED[0]]

    assert _codes(find_graph_violations(_graph(duplicate), base=EMPTY)) == [
        (GraphViolationCode.TABLE_ROW_ID_DUPLICATE, (*TABLE_PATH, 1, "_id"))
    ]
    assert _codes(find_graph_violations(_graph(unsorted), base=EMPTY)) == [
        (GraphViolationCode.TABLE_ROWS_UNSORTED, TABLE_PATH)
    ]


def test_rows_with_equal_positions_sort_by_id():
    tied = [{"_id": "b", "_pos": "a0"}, {"_id": "a", "_pos": "a0"}]

    assert _codes(find_graph_violations(_graph(tied), base=EMPTY)) == [
        (GraphViolationCode.TABLE_ROWS_UNSORTED, TABLE_PATH)
    ]


def test_only_table_fields_are_checked():
    graph = _graph(LEGACY)
    field = graph["nodes"][0]["data"]["node"]["template"]["headers"]
    field["type"] = "dict"
    del field["_input_type"]

    assert find_graph_violations(graph, base=EMPTY) == []


def test_tool_actions_are_a_keyed_list_not_a_table():
    # A component in tool mode holds its tool actions under a table-typed field;
    # they are keyed by tag, so they never need row ids.
    graph = _graph(copy.deepcopy(KEYED))
    graph["nodes"][0]["data"]["node"]["template"]["tools_metadata"] = {
        "type": "table",
        "_input_type": "ToolsInput",
        "value": [{"name": "fetch", "tags": ["fetch"]}],
    }

    assert find_graph_violations(graph, base=EMPTY) == []


def test_validate_raises_with_the_table_violations():
    with pytest.raises(FlowDataValidationError) as exc_info:
        validate_flow_data(_graph(LEGACY), base=EMPTY)

    assert exc_info.value.violations[0].code == GraphViolationCode.TABLE_ROW_ID_MISSING


def test_repair_assigns_ids_and_evenly_spaced_positions_in_row_order():
    result = repair_flow_data(_graph(LEGACY), base=EMPTY)
    rows = result.flow_data["nodes"][0]["data"]["node"]["template"]["headers"]["value"]

    assert [row["key"] for row in rows] == ["Accept", "Auth"]
    assert [row["_pos"] for row in rows] == ["a0", "a1"]
    assert all(isinstance(row["_id"], str) and len(row["_id"]) == 5 for row in rows)
    assert rows[0]["_id"] != rows[1]["_id"]
    assert [fix.code for fix in result.fixes] == [
        GraphViolationCode.TABLE_ROW_ID_MISSING,
        GraphViolationCode.TABLE_ROW_ID_MISSING,
        GraphViolationCode.TABLE_ROW_POS_INVALID,
        GraphViolationCode.TABLE_ROW_POS_INVALID,
    ]
    assert find_graph_violations(result.flow_data, base=EMPTY) == []


def test_repair_leaves_an_unchanged_legacy_table_alone():
    graph = _graph(LEGACY)

    assert repair_flow_data(graph, base=graph).fixes == []
    assert repair_flow_data(graph).fixes == []


def test_repair_fills_a_missing_position_between_its_neighbours():
    rows = [KEYED[0], {"_id": "r9", "key": "New"}, KEYED[1]]
    result = repair_flow_data(_graph(rows), base=EMPTY)
    repaired = result.flow_data["nodes"][0]["data"]["node"]["template"]["headers"]["value"]

    assert [row["_id"] for row in repaired] == ["r1", "r9", "r2"]
    assert [row["_pos"] for row in repaired] == ["a0", "a0V", "a1"]
    assert [(fix.code, fix.path) for fix in result.fixes] == [
        (GraphViolationCode.TABLE_ROW_POS_INVALID, (*TABLE_PATH, 1, "_pos"))
    ]


def test_repair_regenerates_duplicate_ids_and_sorts():
    rows = [{**KEYED[1]}, {**KEYED[0], "_id": "r2"}, "not a row"]
    result = repair_flow_data(_graph(rows), base=EMPTY)
    repaired = result.flow_data["nodes"][0]["data"]["node"]["template"]["headers"]["value"]

    assert [row["key"] for row in repaired] == ["Accept", "Auth"]
    assert repaired[1]["_id"] == "r2"
    assert repaired[0]["_id"] != "r2"
    assert [fix.code for fix in result.fixes] == [
        GraphViolationCode.TABLE_ROW_NOT_OBJECT,
        GraphViolationCode.TABLE_ROW_ID_DUPLICATE,
        GraphViolationCode.TABLE_ROWS_UNSORTED,
    ]


def test_repair_is_deterministic():
    assert repair_flow_data(_graph(LEGACY), base=EMPTY) == repair_flow_data(_graph(LEGACY), base=EMPTY)


def test_strip_row_keys():
    assert strip_row_keys(KEYED) == LEGACY
    assert strip_row_keys(None) is None
    assert strip_row_keys(["x"]) == ["x"]


# --- Assigning ids to the rows of a node being added ------------------------------------


def _rows(graph) -> list:
    return graph["nodes"][0]["data"]["node"]["template"]["headers"]["value"]


def test_assigning_ids_makes_a_new_node_pass_strict_validation_and_keeps_row_order():
    graph = _graph(copy.deepcopy(LEGACY))
    with pytest.raises(FlowDataValidationError):
        validate_flow_data(graph, base=EMPTY)

    assign_table_row_ids(graph["nodes"][0])

    validate_flow_data(graph, base=EMPTY)
    rows = _rows(graph)
    assert strip_row_keys(rows) == LEGACY
    assert all(re.fullmatch(r"[0-9A-Za-z]{10}", row["_id"]) for row in rows)
    assert rows[0]["_pos"] < rows[1]["_pos"]


def test_assigning_ids_keeps_existing_ids_and_positions_and_fills_the_gaps():
    rows = [
        {"_id": "r1", "_pos": "a0", "key": "first"},
        {"key": "second"},
        {"_id": "r1", "_pos": "a1", "key": "duplicate id"},
    ]
    graph = _graph(rows)

    assign_table_row_ids(graph["nodes"][0])

    result = _rows(graph)
    assert [row["key"] for row in result] == ["first", "second", "duplicate id"]
    assert result[0] == {"_id": "r1", "_pos": "a0", "key": "first"}
    assert result[2]["_pos"] == "a1"
    assert "a0" < result[1]["_pos"] < "a1"
    assert len({row["_id"] for row in result}) == 3
    validate_flow_data(graph, base=EMPTY)


def test_assigning_ids_leaves_valid_tables_and_other_fields_alone():
    graph = _graph(copy.deepcopy(KEYED))
    graph["nodes"][0]["data"]["node"]["template"]["tools_metadata"] = {
        "type": "table",
        "value": [{"name": "tool", "tags": ["tool"]}],
    }
    before = copy.deepcopy(graph)

    assign_table_row_ids(graph["nodes"][0])

    assert graph == before


def test_stripping_a_flow_removes_row_keys_from_every_table():
    graph = _graph(copy.deepcopy(KEYED))

    assert strip_flow_table_row_keys(graph) is graph
    assert _rows(graph) == LEGACY
    assert graph["nodes"][0]["data"]["node"]["template"]["url"]["value"] == "http://x"


def test_assigning_changed_tables_keeps_the_ids_of_rows_the_table_still_holds():
    stored = _graph(copy.deepcopy(KEYED))
    target = _graph([*copy.deepcopy(LEGACY), {"key": "New", "value": "x"}])

    assign_changed_table_row_ids(stored, target)

    rows = _rows(target)
    assert [row["_id"] for row in rows[:2]] == ["r1", "r2"]
    assert [row["_pos"] for row in rows[:2]] == ["a0", "a1"]
    assert rows[2]["key"] == "New"
    assert rows[2]["_pos"] > "a1"
    validate_flow_data(target, base=stored)


def test_assigning_changed_tables_leaves_unchanged_legacy_tables_alone():
    stored = _graph(copy.deepcopy(LEGACY))
    target = copy.deepcopy(stored)
    target["nodes"][0]["data"]["node"]["template"]["url"]["value"] = "http://y"

    assign_changed_table_row_ids(stored, target)

    assert _rows(target) == LEGACY
    validate_flow_data(target, base=stored)


def test_assigning_changed_tables_gives_new_nodes_ids():
    target = _graph(copy.deepcopy(LEGACY))

    assign_changed_table_row_ids(EMPTY, target)

    validate_flow_data(target, base=EMPTY)
    assert strip_row_keys(_rows(target)) == LEGACY
