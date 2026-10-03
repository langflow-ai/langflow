"""Shared merge cases: what concurrent transactions do when the server applies them in order.

The server sequences each flow's transactions and applies every one to the
latest graph, with no transformation. These cases pin the outcome of the
conflicts that matter: edits to different cells merge, the last write to a
path wins, edits to deleted items fail, and expectations catch stale writes.
The editor's applier runs the same file.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from lfx.services.flow_operations import FlowOperationError, apply_flow_operations, parse_flow_operations

DOCUMENT = json.loads((Path(__file__).parent / "fixtures" / "merge_cases.json").read_text())
CASES = DOCUMENT["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_merge_case(case):
    graph = copy.deepcopy(DOCUMENT["base"])
    outcomes = {}
    for name in case["order"]:
        before = copy.deepcopy(graph)
        try:
            operations = parse_flow_operations(copy.deepcopy(case["transactions"][name]))
            graph = apply_flow_operations(graph, operations).flow_data
        except FlowOperationError as exc:
            outcomes[name] = {"error": type(exc).__name__, "code": exc.code}
            assert graph == before
        else:
            outcomes[name] = "applied"

    assert outcomes == case["outcomes"]
    assert graph == case["expected"]
