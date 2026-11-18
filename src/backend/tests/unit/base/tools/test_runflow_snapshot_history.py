"""RunFlow child graphs have their own diagnostic history policy."""

from lfx.graph import Graph


def test_runflow_independent_child_keeps_full_default():
    from lfx.base.tools.run_flow import RunFlowBaseComponent

    parent = Graph(snapshot_history_limit=0)
    # The actual RunFlow cached-child builder has no parent policy parameter.
    child = RunFlowBaseComponent._build_graph_from_dict(
        object(),
        cache_entry={"graph_dump": {"data": {"nodes": [], "edges": []}}},
    )
    assert parent.snapshot_history_limit == 0
    assert child.snapshot_history_limit is None
    assert Graph.from_payload({"nodes": [], "edges": []}, snapshot_history_limit=0).snapshot_history_limit == 0


def test_dill_graph_roundtrip_preserves_policy_without_history():
    import dill

    graph = Graph(snapshot_history_limit=0)
    restored = dill.loads(dill.dumps(graph, recurse=True))  # noqa: S301
    assert restored.__dict__["_snapshot_history_limit"] == 0
    assert restored._snapshots == []
    restored._record_snapshot("cached_vertex")
    assert restored._call_order == ["cached_vertex"]
    assert restored._snapshots == []
