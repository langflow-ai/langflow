"""Shared diff cases: the exact operations a whole-flow save records.

The fixture pins the diff's output, not just that it replays: every writer
that derives operations (the server today, the editor later) must produce the
same units, keyed-list writes and edge updates so history stays uniform.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from lfx.services.flow_operations import (
    apply_flow_operations,
    derive_flow_operations,
    diff_flow_data,
    dump_flow_operation,
    graphs_equal,
    parse_flow_operations,
)

CASES = json.loads((Path(__file__).parent / "fixtures" / "diff_cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_diff_case(case):
    base = copy.deepcopy(case["base"])
    target = copy.deepcopy(case["target"])

    operations = diff_flow_data(base, target)

    assert [dump_flow_operation(operation) for operation in operations] == case["operations"]
    assert graphs_equal(derive_flow_operations(base, target).flow_data, target)
    assert base == case["base"]
    assert target == case["target"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_diff_case_replays_from_its_recorded_form(case):
    graph = copy.deepcopy(case["base"])
    for operation in parse_flow_operations(copy.deepcopy(case["operations"])):
        graph = apply_flow_operations(graph, [operation]).flow_data

    assert graphs_equal(graph, case["target"])
