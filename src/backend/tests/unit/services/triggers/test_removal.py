"""Unit tests for the pure removal helpers (no DB, no I/O)."""

from __future__ import annotations

from copy import deepcopy

from langflow.services.triggers.removal import (
    remove_all_cron_trigger_nodes,
    remove_cron_trigger_node,
)


def _cron_node(component_id: str) -> dict:
    return {
        "id": component_id,
        "type": "genericNode",
        "data": {"type": "CronTrigger", "node": {"template": {}}},
    }


def _chat_node(component_id: str = "ChatInput-c") -> dict:
    return {
        "id": component_id,
        "type": "genericNode",
        "data": {"type": "ChatInput", "node": {"template": {}}},
    }


def _flow(nodes: list[dict], edges: list[dict] | None = None) -> dict:
    return {"nodes": nodes, "edges": edges or []}


# --------------------------------------------------------------------------- #
#  remove_cron_trigger_node (single)
# --------------------------------------------------------------------------- #


def test_remove_single_returns_false_for_none_flow_data():
    result, removed = remove_cron_trigger_node(None, "CronTrigger-x")
    assert removed is False
    assert result == {"nodes": [], "edges": []}


def test_remove_single_returns_false_when_component_not_present():
    flow = _flow([_chat_node()])
    result, removed = remove_cron_trigger_node(flow, "CronTrigger-x")
    assert removed is False
    assert result["nodes"] == flow["nodes"]


def test_remove_single_does_not_match_a_non_cron_node_with_same_id():
    """Safety: id collisions never reach non-CronTrigger nodes.

    Even if another node accidentally has an id colliding with the target,
    only nodes whose ``data.type`` is ``CronTrigger`` should be touched.
    """
    colliding = {"id": "CronTrigger-x", "type": "genericNode", "data": {"type": "ChatInput"}}
    flow = _flow([colliding])
    result, removed = remove_cron_trigger_node(flow, "CronTrigger-x")
    assert removed is False
    assert result["nodes"] == [colliding]


def test_remove_single_drops_only_the_targeted_node():
    flow = _flow([_chat_node(), _cron_node("CronTrigger-x"), _cron_node("CronTrigger-y")])
    result, removed = remove_cron_trigger_node(flow, "CronTrigger-x")
    assert removed is True
    ids = [n["id"] for n in result["nodes"]]
    assert ids == ["ChatInput-c", "CronTrigger-y"]


def test_remove_single_prunes_edges_referencing_the_removed_node():
    flow = _flow(
        [_cron_node("CronTrigger-x"), _chat_node()],
        edges=[
            {"source": "CronTrigger-x", "target": "ChatInput-c"},
            {"source": "ChatInput-c", "target": "OtherNode"},
        ],
    )
    result, removed = remove_cron_trigger_node(flow, "CronTrigger-x")
    assert removed is True
    assert result["edges"] == [{"source": "ChatInput-c", "target": "OtherNode"}]


def test_remove_single_does_not_mutate_the_input():
    flow = _flow([_cron_node("CronTrigger-x")])
    snapshot = deepcopy(flow)
    remove_cron_trigger_node(flow, "CronTrigger-x")
    assert flow == snapshot


# --------------------------------------------------------------------------- #
#  remove_all_cron_trigger_nodes (bulk)
# --------------------------------------------------------------------------- #


def test_remove_all_returns_empty_list_when_no_triggers_present():
    flow = _flow([_chat_node()])
    result, removed_ids = remove_all_cron_trigger_nodes(flow)
    assert removed_ids == []
    assert result["nodes"] == flow["nodes"]


def test_remove_all_strips_every_cron_node():
    flow = _flow(
        [_chat_node(), _cron_node("CronTrigger-1"), _cron_node("CronTrigger-2")],
        edges=[
            {"source": "CronTrigger-1", "target": "ChatInput-c"},
            {"source": "CronTrigger-2", "target": "ChatInput-c"},
            {"source": "ChatInput-c", "target": "Other"},
        ],
    )
    result, removed_ids = remove_all_cron_trigger_nodes(flow)
    assert removed_ids == ["CronTrigger-1", "CronTrigger-2"]
    assert [n["id"] for n in result["nodes"]] == ["ChatInput-c"]
    assert result["edges"] == [{"source": "ChatInput-c", "target": "Other"}]


def test_remove_all_handles_missing_edges_gracefully():
    flow = {"nodes": [_cron_node("CronTrigger-x")]}
    result, removed_ids = remove_all_cron_trigger_nodes(flow)
    assert removed_ids == ["CronTrigger-x"]
    assert result["nodes"] == []
    assert result["edges"] == []


def test_remove_all_returns_input_when_node_list_is_malformed():
    flow = {"nodes": "not-a-list"}
    result, removed_ids = remove_all_cron_trigger_nodes(flow)
    assert removed_ids == []
    assert result == {"nodes": "not-a-list"}
