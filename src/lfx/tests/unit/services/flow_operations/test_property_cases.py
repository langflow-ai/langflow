"""The cross-language property fixture replays to the hashes it was generated with.

``property_cases.py`` generated random valid transactions over a small graph
with this engine. Any change that makes a transaction replay differently
changes what stored history means, so it must be deliberate: regenerate the
fixture and update the editor's applier with it.
"""

from __future__ import annotations

import copy
import json

import pytest
from lfx.services.flow_operations import apply_flow_operations, graph_hash, parse_flow_operations

from tests.unit.services.flow_operations.property_cases import FIXTURE, generate

DOCUMENT = json.loads(FIXTURE.read_text(encoding="utf-8"))
SEQUENCES = DOCUMENT["sequences"]


def test_fixture_is_what_the_generator_produces():
    assert generate() == DOCUMENT


@pytest.mark.parametrize("sequence", SEQUENCES, ids=[sequence["name"] for sequence in SEQUENCES])
def test_sequence_replays_to_the_recorded_hash(sequence):
    graph = copy.deepcopy(DOCUMENT["base"])
    for transaction in sequence["transactions"]:
        graph = apply_flow_operations(graph, parse_flow_operations(copy.deepcopy(transaction))).flow_data

    assert graph_hash(graph) == sequence["graph_hash"]
