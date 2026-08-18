"""Unit tests for the upgrade compatibility checker."""

from lfx.upgrade.checker import (
    TOOL_OUTPUT_NAME,
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


def test_outdated_safe_when_flow_has_transient_template_metadata():
    node = _node(
        code=REGISTRY_CODE_V1,
        template_extra={
            "_frontend_node_flow_id": {"value": "flow-1"},
            "_frontend_node_folder_id": {"value": "folder-1"},
            "is_refresh": True,
            "tools_metadata": {"value": []},
        },
    )
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


def test_outdated_safe_when_registry_dropped_template_field():
    """A field only the flow has (the registry dropped it) holds a value nothing reads."""
    old_template_extra = {"prompt": {"value": "hello"}}
    node = _node(code=REGISTRY_CODE_V1, template_extra=old_template_extra)
    registry = _registry(code=REGISTRY_CODE_V2)
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_safe"


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


def _group(node_id: str, type_: str, child: dict) -> dict:
    """Wrap *child* inside a grouped-component node's nested flow."""
    return {
        "id": node_id,
        "data": {
            "type": type_,
            "node": {
                "display_name": type_,
                "template": {},  # no code, so the group wrapper itself is skipped
                "outputs": [],
                "flow": {"data": {"nodes": [child], "edges": []}},
            },
        },
    }


# --- _outputs_are_compatible must not flag cosmetic / widening changes -----------------


def _output(types, display_name="Output", method="run"):
    return {"name": "out", "display_name": display_name, "types": types, "method": method, "allows_loop": False}


def test_outdated_safe_when_output_display_name_changed():
    """A cosmetic display_name change (e.g. a registry typo fix) is not breaking."""
    node = _node(code=REGISTRY_CODE_V1, outputs=[_output(["Message"], display_name="Outpout")])
    registry = _registry(code=REGISTRY_CODE_V2, outputs=[_output(["Message"], display_name="Output")])
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_safe"


def test_outdated_safe_when_output_types_widened():
    """The registry adding a type to an output (widening) is safe, not breaking."""
    node = _node(code=REGISTRY_CODE_V1, outputs=[_output(["Message"])])
    registry = _registry(code=REGISTRY_CODE_V2, outputs=[_output(["Message", "Data"])])
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_safe"


def test_outdated_breaking_when_output_types_narrowed():
    """The registry dropping a type the saved flow emitted (narrowing) breaks downstream edges."""
    node = _node(code=REGISTRY_CODE_V1, outputs=[_output(["Message", "Data"])])
    registry = _registry(code=REGISTRY_CODE_V2, outputs=[_output(["Message"])])
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_breaking"


# --- _input_types_contained must allow widening ----------------------------------------


def test_outdated_safe_when_input_types_widened():
    """The registry accepting an additional input type (widening) is safe, not breaking."""
    node = _node(code=REGISTRY_CODE_V1, template_extra={"inp": {"input_types": ["Message"]}})
    registry = _registry(code=REGISTRY_CODE_V2, template_extra={"inp": {"input_types": ["Message", "Data"]}})
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_safe"


# --- template key differences are directional, not an equality check -------------------


def test_outdated_safe_when_registry_added_optional_field():
    """The registry growing an optional field — the docs-recommended evolution — is safe.

    apply_safe_upgrades introduces the field with its registry default, so the re-stamped
    code never runs without a field it expects.
    """
    node = _node(code=REGISTRY_CODE_V1)
    registry = _registry(code=REGISTRY_CODE_V2, template_extra={"new_flag": {"value": False, "required": False}})
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_safe"


def test_outdated_safe_when_registry_added_required_field_with_default():
    """A new required field whose registry default is usable leaves the node runnable."""
    node = _node(code=REGISTRY_CODE_V1)
    registry = _registry(code=REGISTRY_CODE_V2, template_extra={"retries": {"value": 3, "required": True}})
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_safe"


def test_outdated_safe_when_registry_added_required_field_with_falsy_default():
    """0, False, and [] are usable defaults; only None and "" mean there is nothing to fill.

    Pins the guard to ``value in (None, "")`` — a truthiness rewrite would wrongly start
    marking these as breaking.
    """
    for falsy_default in (0, False, []):
        node = _node(code=REGISTRY_CODE_V1)
        registry = _registry(
            code=REGISTRY_CODE_V2, template_extra={"max_retries": {"value": falsy_default, "required": True}}
        )
        report = check_flow_compatibility(_flow(node), registry)
        assert report.nodes[0].status == "outdated_safe"


def test_outdated_breaking_when_registry_added_required_field_without_default():
    """A new required field with nothing to fill it turns a flow that ran into one that fails."""
    for empty_default in ("", None):
        node = _node(code=REGISTRY_CODE_V1)
        registry = _registry(
            code=REGISTRY_CODE_V2, template_extra={"api_key": {"value": empty_default, "required": True}}
        )
        report = check_flow_compatibility(_flow(node), registry)
        assert report.nodes[0].status == "outdated_breaking"


def test_outdated_safe_when_registry_added_handle_input_field():
    """A new field with input_types has no saved edges feeding it, so nothing narrows."""
    node = _node(code=REGISTRY_CODE_V1)
    registry = _registry(code=REGISTRY_CODE_V2, template_extra={"tools": {"input_types": ["Tool"], "value": ""}})
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_safe"


def test_outdated_safe_when_optional_field_renamed():
    """A rename is a drop plus an add; with an optional replacement neither direction breaks.

    The saved value of the old field is not carried over — the new field starts at its
    registry default, the same state the frontend's update endpoint produces when it
    rebuilds the template.
    """
    node = _node(code=REGISTRY_CODE_V1, template_extra={"legacy_input": {"value": "user set"}})
    registry = _registry(code=REGISTRY_CODE_V2, template_extra={"current_input": {"value": ""}})
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_safe"


# --- full recursion into nested grouped components -------------------------------------


def test_deeply_nested_flow_nodes_are_classified():
    """A safe-upgradeable node two levels deep (group inside a group) must be classified."""
    inner = _node(code=REGISTRY_CODE_V1)
    middle = _group("group-2", "InnerGroup", inner)
    outer = _group("group-1", "OuterGroup", middle)
    report = check_flow_compatibility({"nodes": [outer], "edges": []}, _registry())
    assert len(report.nodes) == 1
    assert report.nodes[0].status == "outdated_safe"


# --- pre-built registry lookup can be reused -------------------------------------------


def test_check_accepts_prebuilt_registry():
    all_types = _registry()
    lookup = build_registry_lookup(all_types)
    report = check_flow_compatibility(_flow(_node(code=REGISTRY_CODE_V1)), all_types, registry=lookup)
    assert report.nodes[0].status == "outdated_safe"


# --- tool-mode nodes carry a synthesized output set ------------------------------------


def _tool_outputs():
    """The outputs a node carries once it is switched to tool mode."""
    return [
        {
            "name": TOOL_OUTPUT_NAME,
            "display_name": "Toolset",
            "types": ["Tool"],
            "method": "to_toolkit",
            "allows_loop": False,
        }
    ]


def test_outdated_safe_when_tool_mode_node_outputs_are_the_toolset():
    """Tool mode replaces a node's outputs, so they never match the registry's declared ones."""
    node = _node(
        code=REGISTRY_CODE_V1,
        outputs=_tool_outputs(),
        template_extra={"query": {"tool_mode": True}, "tools_metadata": {}},
    )
    registry = _registry(code=REGISTRY_CODE_V2, template_extra={"query": {"tool_mode": True}})
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_safe"


def test_outdated_breaking_when_tool_mode_component_declares_no_tool_input():
    """Without a tool_mode input the component is not known to still produce the toolset output.

    ``Component._handle_tool_mode`` also creates that output for components that set the
    ``add_tool_output`` class attribute; the flag reaches the component index now, but neither
    this checker nor its frontend mirror reads it yet, so it stays undetected on both sides
    until they change together. Treating "no inputs at all" as tool-capable would be wrong in the
    dangerous direction: ``MockDataGenerator`` has no inputs and produces no toolset output at
    runtime, so a node of it would be called safe and re-stamped while its saved
    ``component_as_tool`` output still failed to resolve.
    """
    node = _node(code=REGISTRY_CODE_V1, outputs=_tool_outputs(), template_extra={"tools_metadata": {}})
    registry = _registry(code=REGISTRY_CODE_V2)
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_breaking"


def test_outdated_breaking_when_tool_mode_node_lost_tool_support():
    """The component no longer declares a tool-mode input, so the saved node cannot be rebuilt."""
    node = _node(
        code=REGISTRY_CODE_V1,
        outputs=_tool_outputs(),
        template_extra={"query": {"tool_mode": True}, "tools_metadata": {}},
    )
    registry = _registry(code=REGISTRY_CODE_V2, template_extra={"query": {"tool_mode": False}})
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_breaking"


def test_outdated_breaking_when_tool_output_appears_more_than_once():
    """Tool mode synthesizes exactly one output, so a duplicated name is a malformed node.

    Such a node must keep going through the authored-output comparison instead of being
    treated as a tool-mode node and skipping it.
    """
    node = _node(
        code=REGISTRY_CODE_V1,
        outputs=_tool_outputs() + _tool_outputs(),
        template_extra={"query": {"tool_mode": True}, "tools_metadata": {}},
    )
    registry = _registry(code=REGISTRY_CODE_V2, template_extra={"query": {"tool_mode": True}})
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_breaking"


def test_outdated_breaking_when_tool_mode_node_input_types_narrowed():
    """The remaining compatibility checks still apply to a tool-mode node."""
    node = _node(
        code=REGISTRY_CODE_V1,
        outputs=_tool_outputs(),
        template_extra={"query": {"tool_mode": True, "input_types": ["Message"]}, "tools_metadata": {}},
    )
    registry = _registry(code=REGISTRY_CODE_V2, template_extra={"query": {"tool_mode": True, "input_types": ["Data"]}})
    report = check_flow_compatibility(_flow(node), registry)
    assert report.nodes[0].status == "outdated_breaking"
