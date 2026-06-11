"""Unit tests for the upgrade applier."""

import copy

from lfx.upgrade.applier import apply_safe_upgrades
from lfx.upgrade.checker import check_flow_compatibility

REGISTRY_CODE = "class MyComp:\n    pass  # v2"
NODE_CODE = "class MyComp:\n    pass  # v1"


def _registry(code=REGISTRY_CODE):
    return {
        "Cat": {
            "MyComp": {
                "template": {"code": {"value": code}},
                "outputs": [{"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}],
                "metadata": {},
            }
        }
    }


def _node(code=NODE_CODE, type_="MyComp"):
    return {
        "id": "n1",
        "data": {
            "id": "n1",
            "type": type_,
            "node": {
                "display_name": "My Component",
                "edited": False,
                "template": {"code": {"value": code}},
                "outputs": [{"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}],
            },
        },
    }


def _flow(*nodes):
    return {"nodes": list(nodes), "edges": []}


def test_apply_updates_safe_node_code():
    flow = _flow(_node(code=NODE_CODE))
    registry = _registry(code=REGISTRY_CODE)
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_safe"

    updated = apply_safe_upgrades(flow, registry, report)
    code = updated["nodes"][0]["data"]["node"]["template"]["code"]["value"]
    assert code == REGISTRY_CODE


def test_apply_does_not_mutate_original():
    flow = _flow(_node(code=NODE_CODE))
    original_code = flow["nodes"][0]["data"]["node"]["template"]["code"]["value"]
    registry = _registry(code=REGISTRY_CODE)
    report = check_flow_compatibility(flow, registry)

    apply_safe_upgrades(flow, registry, report)
    assert flow["nodes"][0]["data"]["node"]["template"]["code"]["value"] == original_code


def test_apply_skips_breaking_nodes():
    new_outputs = [{"name": "renamed_out", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}]
    flow = _flow(_node(code=NODE_CODE))
    registry = {
        "Cat": {
            "MyComp": {
                "template": {"code": {"value": REGISTRY_CODE}},
                "outputs": new_outputs,
                "metadata": {},
            }
        }
    }
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "outdated_breaking"

    updated = apply_safe_upgrades(flow, registry, report)
    code = updated["nodes"][0]["data"]["node"]["template"]["code"]["value"]
    assert code == NODE_CODE


def test_apply_skips_blocked_nodes():
    flow = _flow(_node(type_="Ghost"))
    registry = {}
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "blocked"

    updated = apply_safe_upgrades(flow, registry, report)
    assert updated["nodes"][0]["data"]["node"]["template"]["code"]["value"] == NODE_CODE


def test_apply_skips_ok_nodes():
    flow = _flow(_node(code=REGISTRY_CODE))
    registry = _registry(code=REGISTRY_CODE)
    report = check_flow_compatibility(flow, registry)
    assert report.nodes[0].status == "ok"

    updated = apply_safe_upgrades(flow, registry, report)
    assert updated["nodes"][0]["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE


def test_apply_returns_count_of_updated_nodes():
    node_a = _node(code=NODE_CODE)
    node_b = copy.deepcopy(node_a)
    node_b["id"] = "n2"
    node_b["data"]["id"] = "n2"
    node_b["data"]["type"] = "Ghost"
    flow = _flow(node_a, node_b)
    registry = _registry(code=REGISTRY_CODE)
    report = check_flow_compatibility(flow, registry)

    _, count = apply_safe_upgrades(flow, registry, report, return_count=True)
    assert count == 1


def test_apply_updates_nested_flow_safe_node_code():
    """Safe upgrades inside a grouped component's nested flow must be written, not skipped.

    Counterpart to test_nested_flow_nodes_are_classified in test_checker.py: the checker
    classifies nested nodes, so the applier must also write them, otherwise the report
    advertises a safe upgrade that never actually lands on disk.
    """
    nested = _node(code=NODE_CODE)
    nested["id"] = "nested-1"
    nested["data"]["id"] = "nested-1"
    outer = {
        "id": "group-1",
        "data": {
            "id": "group-1",
            "type": "SomeGrouping",
            "node": {
                "display_name": "Group",
                "template": {},
                "outputs": [],
                "flow": {"data": {"nodes": [nested], "edges": []}},
            },
        },
    }
    flow = _flow(outer)
    registry = _registry(code=REGISTRY_CODE)
    report = check_flow_compatibility(flow, registry)
    assert any(n.node_id == "nested-1" and n.status == "outdated_safe" for n in report.nodes)

    updated, count = apply_safe_upgrades(flow, registry, report, return_count=True)
    assert count == 1
    written = updated["nodes"][0]["data"]["node"]["flow"]["data"]["nodes"][0]
    assert written["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE
