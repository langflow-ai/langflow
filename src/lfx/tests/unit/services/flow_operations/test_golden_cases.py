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
from lfx.services.flow_operations import FlowOperationError, apply_flow_operations, parse_flow_operations

CASES = json.loads((Path(__file__).parent / "fixtures" / "apply_cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_apply_case(case):
    base = copy.deepcopy(case["base"])

    if "error" in case:
        with pytest.raises(FlowOperationError) as exc_info:
            apply_flow_operations(base, parse_flow_operations(copy.deepcopy(case["operations"])))
        assert type(exc_info.value).__name__ == case["error"]
        assert base == case["base"]
        return

    result = apply_flow_operations(base, parse_flow_operations(copy.deepcopy(case["operations"])))

    assert result.flow_data == case["expected"]
    assert [op.model_dump(mode="json") for op in result.forward_ops] == case["forward_operations"]
    assert base == case["base"]
