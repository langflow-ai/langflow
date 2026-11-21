"""Regression test: filter_json must not strip layout keys out of the caller's flow.

``compute_dict_hash`` (used by ``SessionService.build_key``) hashes flows through
``filter_json`` so cosmetic edits do not change a session key. The node loop used
to delete ``position`` / ``positionAbsolute`` / ``selected`` / ``dragging`` from
the node dicts of the caller's payload, so a caller that kept using that payload
had every node at the origin.
"""

from __future__ import annotations

import copy

from langflow.services.cache.utils import filter_json

FLOW = {
    "viewport": {"x": 12.5, "y": -8.0, "zoom": 0.75},
    "chatHistory": [{"message": "hello"}],
    "nodes": [
        {
            "id": "ChatInput-abc",
            "position": {"x": 300.0, "y": 180.0},
            "positionAbsolute": {"x": 300.0, "y": 180.0},
            "selected": True,
            "dragging": False,
            "data": {"id": "ChatInput-abc"},
        }
    ],
    "edges": [],
}


def test_filter_json_does_not_mutate_the_caller_payload():
    flow = copy.deepcopy(FLOW)

    filtered = filter_json(flow)

    # The filtered copy is what gets hashed: layout-only keys are gone.
    assert "viewport" not in filtered
    assert "chatHistory" not in filtered
    assert filtered["nodes"][0] == {"id": "ChatInput-abc", "data": {"id": "ChatInput-abc"}}

    # The caller's flow still carries its layout, so hashing it did not move nodes.
    assert flow == FLOW
