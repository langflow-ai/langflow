"""Shared apply cases every flow operation engine must agree on.

The fixture file is the contract, not this test: any other applier of the same
operations (for example the editor's history playback) runs the same cases, so
the Python engine and that applier cannot drift apart unnoticed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from lfx.services.flow_operations import (
    FlowOperationError,
    apply_flow_operations,
    dump_flow_operation,
    load_node_schema,
    parse_flow_operations,
)

CASES = json.loads((Path(__file__).parent / "fixtures" / "apply_cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_apply_case(case):
    base = copy.deepcopy(case["base"])

    if "error" in case:
        with pytest.raises(FlowOperationError) as exc_info:
            apply_flow_operations(base, parse_flow_operations(copy.deepcopy(case["operations"])))
        assert type(exc_info.value).__name__ == case["error"]
        assert exc_info.value.code == case["code"]
        assert base == case["base"]
        return

    result = apply_flow_operations(base, parse_flow_operations(copy.deepcopy(case["operations"])))

    assert _ignoring_row_order(result.flow_data) == _ignoring_row_order(case["expected"])
    # Cases whose normalized operations equal what they submit leave forward_operations out.
    expected_forward = case.get("forward_operations", case["operations"])
    assert _ignoring_id_order([dump_flow_operation(op) for op in result.forward_ops]) == _ignoring_id_order(
        expected_forward
    )
    assert base == case["base"]


def _ignoring_id_order(operations: list[dict]) -> list[dict]:
    """Compare the ids a delete names as a set: node and edge order is not state."""
    return [
        {**operation, "ids": sorted(operation["ids"])}
        if operation["type"] in {"delete_nodes", "delete_edges"}
        else operation
        for operation in operations
    ]


def _ignoring_row_order(flow_data: dict) -> dict:
    """Compare table rows as a collection keyed by ``__id__``: a table's order is its rows' positions, not the array."""
    flow_data = copy.deepcopy(flow_data)
    schema = load_node_schema()
    for node in flow_data.get("nodes", []):
        template = node.get("data", {}).get("node", {}).get("template", {})
        for name, field in template.items():
            path = ("data", "node", "template", name, "value")
            rows = field.get("value") if isinstance(field, dict) else None
            if isinstance(rows, list) and schema.keyed_list_at(node, path) is schema.table:
                field["value"] = sorted(rows, key=lambda row: row["__id__"])
    return flow_data
