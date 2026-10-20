"""The fixed property sequences replay to their hashes.

``property_cases.json`` holds fixed, reviewed transactions over a small graph,
with the hash of the graph each sequence replays to. Every engine runs the
same file. A change that makes a transaction replay differently changes what
stored history means, so it is a reviewed edit of the fixture that names its
rule.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from lfx.services.flow_operations import apply_flow_operations, graph_hash, parse_flow_operations

FIXTURE = Path(__file__).resolve().parents[5] / "lfx-native" / "fixtures" / "property_cases.json"
DOCUMENT = json.loads(FIXTURE.read_text(encoding="utf-8"))
SEQUENCES = DOCUMENT["sequences"]


@pytest.mark.parametrize("sequence", SEQUENCES, ids=[sequence["name"] for sequence in SEQUENCES])
def test_sequence_replays_to_its_hash(sequence):
    assert sequence.get("rule"), "every sequence names the rule it checks"
    graph = copy.deepcopy(DOCUMENT["base"])
    for transaction in sequence["transactions"]:
        graph = apply_flow_operations(graph, parse_flow_operations(copy.deepcopy(transaction))).flow_data

    assert graph_hash(graph) == sequence["graph_hash"]
