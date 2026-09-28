"""Shadow derivation observes accepted saves and can never fail one."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.flow_history.shadow import observe_graph_write


def _node(node_id: str, value: str = "hi") -> dict:
    return {"id": node_id, "data": {"node": {"template": {"text": {"value": value}}}}}


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ({"nodes": [_node("a")], "edges": []}, {"nodes": [_node("a", "hello")], "edges": []}),
        # A target that breaks the rules is reported, not raised.
        ({"nodes": [_node("a")], "edges": []}, {"nodes": [_node("a"), _node("a")], "edges": []}),
        # A stored graph that predates the rules is reported, not raised.
        ({"nodes": [{"id": "a"}], "edges": []}, {"nodes": [_node("a")], "edges": []}),
        (None, {"nodes": [], "edges": []}),
        ({"nodes": [], "edges": []}, "not a graph"),
    ],
    ids=["valid", "invalid target", "invalid base", "no previous graph", "non-object target"],
)
def test_observing_a_write_never_raises(before, after):
    observe_graph_write(uuid4(), before, after)
