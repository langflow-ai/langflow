"""Unit tests for the upgrade compatibility checker."""

from lfx.upgrade.checker import (
    build_registry_lookup,
    check_flow_compatibility,
)

REGISTRY_CODE_V2 = "class MyComp:\n    pass  # v2"
REGISTRY_CODE_V1 = "class MyComp:\n    pass  # v1"


def _registry(code: str = REGISTRY_CODE_V2, outputs=None, template_extra=None):
    outputs = outputs or [
        {"name": "out", "display_name": "Output", "types": ["Message"], "method": "run", "allows_loop": False}
    ]
    template = {"code": {"value": code}}
    if template_extra:
        template.update(template_extra)
    return {
        "TestCategory": {
            "MyComp": {
                "template": template,
                "outputs": outputs,
                "metadata": {},
            }
        }
    }


def _node(type_: str = "MyComp", code: str = REGISTRY_CODE_V2, outputs=None, template_extra=None):
    outputs = outputs or [
        {"name": "out", "display_name": "Output", "types": ["Message"], "method": "run", "allows_loop": False}
    ]
    template = {"code": {"value": code}}
    if template_extra:
        template.update(template_extra)
    return {
        "id": "node-1",
        "data": {
            "type": type_,
            "node": {
                "display_name": "My Component",
                "edited": False,
                "template": template,
                "outputs": outputs,
            },
        },
    }


def _flow(*nodes):
    return {"nodes": list(nodes), "edges": []}


def test_build_registry_lookup_flattens_categories():
    all_types = _registry()
    lookup = build_registry_lookup(all_types)
    assert "MyComp" in lookup
    assert "code" in lookup["MyComp"]["template"]


def test_build_registry_lookup_skips_non_dict_entries():
    lookup = build_registry_lookup({"Cat": "not a dict"})
    assert lookup == {}


def test_ok_when_code_matches():
    report = check_flow_compatibility(_flow(_node()), _registry())
    assert len(report.nodes) == 1
    assert report.nodes[0].status == "ok"


def test_ok_for_custom_component_ignored():
    node = _node(type_="CustomComponent", code="old code")
    report = check_flow_compatibility(_flow(node), {})
    assert report.nodes[0].status == "ok"


def test_blocked_when_type_not_in_registry():
    node = _node(type_="UnknownComp")
    report = check_flow_compatibility(_flow(node), {})
    assert report.nodes[0].status == "blocked"


def test_outdated_safe_when_code_changed_but_structure_compatible():
    node = _node(code=REGISTRY_CODE_V1)
    report = check_flow_compatibility(_flow(node), _registry(code=REGISTRY_CODE_V2))
    assert report.nodes[0].status == "outdated_safe"


def test_outdated_breaking_when_output_removed():
    old_outputs = [
        {"name": "out", "display_name": "Output", "types": ["Message"], "method": "run", "allows_loop": False},
        {"name": "debug", "display_name": "Debug", "types": ["str"], "method": "debug", "allows_loop": False},
    ]
    new_outputs = [
        {"name": "out", "display_name": "Output", "types": ["Message"], "method": "run", "allows_loop": False},
    ]
    node = _node(code=REGISTRY_CODE_V1, outputs=old_outputs)
    registry = _registry(code=REGISTRY_CODE_V2, outputs=new_outputs)
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_breaking"


def test_outdated_breaking_when_template_key_removed():
    old_template_extra = {"prompt": {"value": "hello"}}
    node = _node(code=REGISTRY_CODE_V1, template_extra=old_template_extra)
    registry = _registry(code=REGISTRY_CODE_V2)
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_breaking"


def test_outdated_breaking_when_input_types_narrowed():
    node = _node(code=REGISTRY_CODE_V1, template_extra={"inp": {"input_types": ["Message", "Data"]}})
    registry = _registry(code=REGISTRY_CODE_V2, template_extra={"inp": {"input_types": ["Message"]}})
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_breaking"


def test_report_is_clean():
    report = check_flow_compatibility(_flow(_node()), _registry())
    assert report.is_clean
    assert not report.has_blocked
    assert not report.has_breaking
    assert not report.has_safe_updates


def test_report_has_blocked():
    report = check_flow_compatibility(_flow(_node(type_="Ghost")), {})
    assert report.has_blocked
    assert not report.is_clean


def test_report_has_safe_updates():
    node = _node(code=REGISTRY_CODE_V1)
    report = check_flow_compatibility(_flow(node), _registry())
    assert report.has_safe_updates
    assert not report.has_blocked
    assert not report.has_breaking


def test_empty_flow_is_clean():
    report = check_flow_compatibility({"nodes": [], "edges": []}, {})
    assert report.is_clean


def test_nodes_without_code_are_skipped():
    node = {"id": "n1", "data": {"type": "NoteNode", "node": {"template": {}, "outputs": []}}}
    report = check_flow_compatibility({"nodes": [node], "edges": []}, {})
    assert len(report.nodes) == 0


def test_report_properties_with_mixed_statuses():
    ok_node = _node(type_="MyComp", code=REGISTRY_CODE_V2)
    safe_node = _node(type_="MyComp", code=REGISTRY_CODE_V1)
    safe_node["id"] = "node-2"
    safe_node["data"]["id"] = "node-2"
    flow = {"nodes": [ok_node, safe_node], "edges": []}
    report = check_flow_compatibility(flow, _registry())
    assert report.has_safe_updates
    assert not report.has_blocked
    assert not report.has_breaking
    assert not report.is_clean


def test_nested_flow_nodes_are_classified():
    """Nodes inside a grouped component's nested flow must be checked."""
    outer_node = {
        "id": "group-1",
        "data": {
            "type": "SomeGrouping",
            "node": {
                "display_name": "Group",
                "template": {},  # no code — outer is skipped
                "outputs": [],
                "flow": {
                    "data": {
                        "nodes": [_node(code=REGISTRY_CODE_V1)],
                        "edges": [],
                    }
                },
            },
        },
    }
    report = check_flow_compatibility({"nodes": [outer_node], "edges": []}, _registry())
    assert len(report.nodes) == 1
    assert report.nodes[0].status == "outdated_safe"
