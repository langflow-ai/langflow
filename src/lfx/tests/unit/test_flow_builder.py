"""Tests for lfx.graph.flow_builder — pure flow-building utilities.

All tests use synthetic registries (plain dicts) — no lfx component loading,
no I/O, no network.
"""

import pytest
from lfx.graph.flow_builder import (
    add_component,
    add_connection,
    configure_component,
    empty_flow,
    flow_info,
    get_component,
    layout_flow,
    list_components,
    list_connections,
    needs_server_update,
    parse_flow_spec,
    remove_component,
    remove_connection,
)
from lfx.graph.flow_builder.connect import _custom_stringify, _scaped_json_stringify

# ---------------------------------------------------------------------------
# Synthetic registry — minimal templates for testing
# ---------------------------------------------------------------------------


def _make_template(display_name, outputs=None, template_fields=None):
    tmpl = {
        "display_name": display_name,
        "base_classes": ["Message"],
        "outputs": outputs or [{"name": "message", "types": ["Message"]}],
        "template": template_fields
        or {
            "input_value": {
                "display_name": "Input Text",
                "type": "str",
                "value": "",
                "input_types": ["Message"],
            },
        },
    }
    return tmpl  # noqa: RET504


REGISTRY = {
    "ChatInput": _make_template("Chat Input"),
    "ToolOutput": _make_template(
        "Tool Output",
        outputs=[{"name": "tool", "types": ["Tool"]}],
        template_fields={
            "tools": {
                "display_name": "Tools",
                "type": "other",
                "value": "",
                "input_types": ["Tool"],
            },
        },
    ),
    "ChatOutput": _make_template(
        "Chat Output",
        outputs=[{"name": "message", "types": ["Message"]}],
        template_fields={
            "input_value": {
                "display_name": "Text",
                "type": "str",
                "value": "",
                "input_types": ["Message"],
            },
        },
    ),
    "OpenAIModel": _make_template(
        "OpenAI",
        outputs=[
            {"name": "text_output", "types": ["Message"]},
            {"name": "model_output", "types": ["LanguageModel"]},
        ],
        template_fields={
            "model_name": {
                "display_name": "Model Name",
                "type": "str",
                "value": "gpt-4o-mini",
                "real_time_refresh": True,
            },
            "temperature": {
                "display_name": "Temperature",
                "type": "float",
                "value": 0.1,
            },
            "input_value": {
                "display_name": "Input",
                "type": "str",
                "value": "",
                "input_types": ["Message"],
            },
        },
    ),
}


def _fresh_flow(name="Test Flow"):
    return empty_flow(name=name)


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------


class TestFlow:
    def test_empty_flow_structure(self):
        flow = empty_flow(name="My Flow", description="desc")
        assert flow["name"] == "My Flow"
        assert flow["description"] == "desc"
        assert flow["data"]["nodes"] == []
        assert flow["data"]["edges"] == []
        assert flow["data"]["viewport"] == {"x": 0, "y": 0, "zoom": 1}

    def test_flow_info_empty(self):
        flow = empty_flow(name="Empty")
        info = flow_info(flow)
        assert info["name"] == "Empty"
        assert info["node_count"] == 0
        assert info["edge_count"] == 0
        assert info["components"] == []

    def test_flow_info_with_components(self):
        flow = _fresh_flow()
        add_component(flow, "ChatInput", REGISTRY)
        add_component(flow, "ChatOutput", REGISTRY)
        info = flow_info(flow)
        assert info["node_count"] == 2
        assert len(info["components"]) == 2
        assert len(info["inputs"]) == 1
        assert len(info["outputs"]) == 1


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------


class TestComponent:
    def test_add_component(self):
        flow = _fresh_flow()
        result = add_component(flow, "ChatInput", REGISTRY)
        assert result["id"].startswith("ChatInput-")
        assert result["display_name"] == "Chat Input"
        assert len(flow["data"]["nodes"]) == 1

    def test_add_component_with_explicit_id(self):
        flow = _fresh_flow()
        result = add_component(flow, "ChatInput", REGISTRY, component_id="ChatInput-fixed")
        assert result["id"] == "ChatInput-fixed"

    def test_add_unknown_component_raises(self):
        flow = _fresh_flow()
        with pytest.raises(ValueError, match="Unknown component"):
            add_component(flow, "TotallyFake", REGISTRY)

    def test_remove_component(self):
        flow = _fresh_flow()
        r = add_component(flow, "ChatInput", REGISTRY)
        assert len(flow["data"]["nodes"]) == 1
        remove_component(flow, r["id"])
        assert len(flow["data"]["nodes"]) == 0

    def test_remove_nonexistent_raises(self):
        flow = _fresh_flow()
        with pytest.raises(ValueError, match="Component not found"):
            remove_component(flow, "NonExistent-12345")

    def test_remove_component_also_removes_edges(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        assert len(flow["data"]["edges"]) == 1
        remove_component(flow, r1["id"])
        assert len(flow["data"]["edges"]) == 0

    def test_configure_component(self):
        flow = _fresh_flow()
        r = add_component(flow, "ChatInput", REGISTRY)
        configure_component(flow, r["id"], {"input_value": "Hello"})
        node = flow["data"]["nodes"][0]
        assert node["data"]["node"]["template"]["input_value"]["value"] == "Hello"

    def test_configure_nonexistent_raises(self):
        flow = _fresh_flow()
        with pytest.raises(ValueError, match="Component not found"):
            configure_component(flow, "NonExistent-12345", {"key": "val"})

    def test_configure_unknown_field_raises(self):
        flow = _fresh_flow()
        r = add_component(flow, "ChatInput", REGISTRY)
        with pytest.raises(ValueError, match="Unknown parameter"):
            configure_component(flow, r["id"], {"nonexistent_field": "val"})

    def test_get_component(self):
        flow = _fresh_flow()
        r = add_component(flow, "ChatInput", REGISTRY)
        info = get_component(flow, r["id"])
        assert info["id"] == r["id"]
        assert info["type"] == "ChatInput"
        assert info["display_name"] == "Chat Input"
        assert "input_value" in info["params"]

    def test_get_nonexistent_raises(self):
        flow = _fresh_flow()
        with pytest.raises(ValueError, match="Component not found"):
            get_component(flow, "NonExistent-12345")

    def test_list_components(self):
        flow = _fresh_flow()
        add_component(flow, "ChatInput", REGISTRY)
        add_component(flow, "ChatOutput", REGISTRY)
        comps = list_components(flow)
        assert len(comps) == 2
        types = {c["type"] for c in comps}
        assert types == {"ChatInput", "ChatOutput"}

    def test_unique_ids(self):
        flow = _fresh_flow()
        ids = set()
        for _ in range(10):
            r = add_component(flow, "ChatInput", REGISTRY)
            assert r["id"] not in ids
            ids.add(r["id"])

    def test_node_structure(self):
        flow = _fresh_flow()
        add_component(flow, "ChatInput", REGISTRY)
        node = flow["data"]["nodes"][0]
        assert node["type"] == "genericNode"
        assert node["position"] == {"x": 0, "y": 0}
        assert node["selected"] is False
        assert node["data"]["showNode"] is True
        assert "template" in node["data"]["node"]
        assert "outputs" in node["data"]["node"]


# ---------------------------------------------------------------------------
# NeedsServerUpdate
# ---------------------------------------------------------------------------


class TestNeedsServerUpdate:
    def test_real_time_refresh_triggers(self):
        template = {"agent_llm": {"real_time_refresh": True, "type": "str"}}
        assert needs_server_update(template, "agent_llm") is True

    def test_no_refresh_does_not_trigger(self):
        template = {"input_value": {"type": "str", "value": ""}}
        assert needs_server_update(template, "input_value") is False

    def test_tool_mode_always_triggers(self):
        assert needs_server_update({}, "tool_mode") is True

    def test_missing_field_does_not_trigger(self):
        assert needs_server_update({}, "nonexistent") is False

    def test_non_dict_field_does_not_trigger(self):
        template = {"some_field": "just a string"}
        assert needs_server_update(template, "some_field") is False


# ---------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------


class TestConnect:
    def test_add_connection(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        edge = add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        assert len(flow["data"]["edges"]) == 1
        assert edge["source"] == r1["id"]
        assert edge["target"] == r2["id"]

    def test_edge_has_reactflow_id(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        edge = add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        assert edge["id"].startswith("reactflow__edge-")

    def test_edge_handle_strings_use_oe(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        edge = add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        assert isinstance(edge["sourceHandle"], str)
        assert isinstance(edge["targetHandle"], str)
        assert "\u0153" in edge["sourceHandle"]
        assert "\u0153" in edge["targetHandle"]

    def test_edge_data_has_handle_dicts(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        edge = add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        assert isinstance(edge["data"]["sourceHandle"], dict)
        assert isinstance(edge["data"]["targetHandle"], dict)
        assert edge["data"]["sourceHandle"]["name"] == "message"
        assert edge["data"]["targetHandle"]["fieldName"] == "input_value"

    def test_edge_resolves_output_types(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        edge = add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        assert edge["data"]["sourceHandle"]["output_types"] == ["Message"]

    def test_edge_resolves_input_types(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        edge = add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        assert edge["data"]["targetHandle"]["inputTypes"] == ["Message"]

    def test_edge_animated_and_selected(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        edge = add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        assert edge["animated"] is False
        assert edge["selected"] is False

    def test_remove_connection(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        removed = remove_connection(flow, r1["id"], r2["id"])
        assert removed == 1
        assert len(flow["data"]["edges"]) == 0

    def test_remove_connection_with_filter(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        removed = remove_connection(flow, r1["id"], r2["id"], source_output="message")
        assert removed == 1

    def test_remove_connection_no_match(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        removed = remove_connection(flow, r1["id"], r2["id"], source_output="nonexistent")
        assert removed == 0
        assert len(flow["data"]["edges"]) == 1

    def test_list_connections(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        conns = list_connections(flow)
        assert len(conns) == 1
        assert conns[0]["source_id"] == r1["id"]
        assert conns[0]["target_id"] == r2["id"]
        assert conns[0]["source_output"] == "message"
        assert conns[0]["target_input"] == "input_value"


# ---------------------------------------------------------------------------
# CustomStringify
# ---------------------------------------------------------------------------


class TestCustomStringify:
    def test_sorted_keys(self):
        result = _custom_stringify({"z": 1, "a": 2})
        assert result == '{"a":2,"z":1}'

    def test_nested_list(self):
        result = _custom_stringify({"list": ["a", "b"]})
        assert result == '{"list":["a","b"]}'

    def test_scaped_replaces_quotes(self):
        result = _scaped_json_stringify({"key": "val"})
        assert '"' not in result
        assert "\u0153" in result

    def test_bool(self):
        assert _custom_stringify(True) == "true"  # noqa: FBT003
        assert _custom_stringify(False) == "false"  # noqa: FBT003

    def test_null(self):
        assert _custom_stringify(None) == "null"

    def test_number(self):
        assert _custom_stringify(42) == "42"
        assert _custom_stringify(3.14) == "3.14"


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


class TestLayout:
    def test_layout_empty_flow(self):
        flow = _fresh_flow()
        layout_flow(flow)  # should not error

    def test_layout_single_node(self):
        flow = _fresh_flow()
        add_component(flow, "ChatInput", REGISTRY)
        layout_flow(flow)
        pos = flow["data"]["nodes"][0]["position"]
        assert "x" in pos
        assert "y" in pos

    def test_layout_chain_assigns_layers(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "OpenAIModel", REGISTRY)
        r3 = add_component(flow, "ChatOutput", REGISTRY)
        add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        add_connection(flow, r2["id"], "text_output", r3["id"], "input_value")
        layout_flow(flow)

        by_id = {n["data"]["id"]: n for n in flow["data"]["nodes"]}
        x1 = by_id[r1["id"]]["position"]["x"]
        x2 = by_id[r2["id"]]["position"]["x"]
        x3 = by_id[r3["id"]]["position"]["x"]
        assert x1 < x2 < x3

    def test_layout_branch_same_x(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY, component_id="ChatOutput-aaa")
        r3 = add_component(flow, "ChatOutput", REGISTRY, component_id="ChatOutput-bbb")
        add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        add_connection(flow, r1["id"], "message", r3["id"], "input_value")
        layout_flow(flow)

        by_id = {n["data"]["id"]: n for n in flow["data"]["nodes"]}
        assert by_id[r2["id"]]["position"]["x"] == by_id[r3["id"]]["position"]["x"]

    def test_layout_disconnected_distinct(self):
        flow = _fresh_flow()
        add_component(flow, "ChatInput", REGISTRY)
        add_component(flow, "ChatOutput", REGISTRY)
        layout_flow(flow)

        positions = [(n["position"]["x"], n["position"]["y"]) for n in flow["data"]["nodes"]]
        assert positions[0] != positions[1]

    def test_layout_uses_spacing_constants(self):
        from lfx.graph.flow_builder.layout import LAYER_SPACING_X

        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        layout_flow(flow)

        by_id = {n["data"]["id"]: n for n in flow["data"]["nodes"]}
        x_diff = by_id[r2["id"]]["position"]["x"] - by_id[r1["id"]]["position"]["x"]
        assert x_diff == LAYER_SPACING_X

    def test_layout_diamond_graph(self):
        """A -> B, A -> C, B -> D, C -> D. D should be at layer 2."""
        from lfx.graph.flow_builder.layout import LAYER_SPACING_X

        flow = _fresh_flow()
        a = add_component(flow, "ChatInput", REGISTRY, component_id="A-00001")
        b = add_component(flow, "ChatOutput", REGISTRY, component_id="B-00001")
        c = add_component(flow, "ChatOutput", REGISTRY, component_id="C-00001")
        d = add_component(flow, "ChatOutput", REGISTRY, component_id="D-00001")
        add_connection(flow, a["id"], "message", b["id"], "input_value")
        add_connection(flow, a["id"], "message", c["id"], "input_value")
        add_connection(flow, b["id"], "message", d["id"], "input_value")
        add_connection(flow, c["id"], "message", d["id"], "input_value")
        layout_flow(flow)

        by_id = {n["data"]["id"]: n for n in flow["data"]["nodes"]}
        # A at layer 0, B and C at layer 1, D at layer 2
        assert by_id["A-00001"]["position"]["x"] == 0
        assert by_id["B-00001"]["position"]["x"] == LAYER_SPACING_X
        assert by_id["C-00001"]["position"]["x"] == LAYER_SPACING_X
        assert by_id["D-00001"]["position"]["x"] == 2 * LAYER_SPACING_X

    def test_layout_long_chain(self):
        """5-node linear chain: each node should be one layer further right."""
        from lfx.graph.flow_builder.layout import LAYER_SPACING_X

        flow = _fresh_flow()
        ids = []
        for i in range(5):
            r = add_component(flow, "ChatInput", REGISTRY, component_id=f"N-{i:05d}")
            ids.append(r["id"])
        for i in range(4):
            add_connection(flow, ids[i], "message", ids[i + 1], "input_value")
        layout_flow(flow)

        by_id = {n["data"]["id"]: n for n in flow["data"]["nodes"]}
        for i, nid in enumerate(ids):
            assert by_id[nid]["position"]["x"] == i * LAYER_SPACING_X

    def test_layout_y_spacing_multiple_at_same_layer(self):
        """3 nodes at the same layer should be spaced by NODE_SPACING_Y."""
        from lfx.graph.flow_builder.layout import NODE_SPACING_Y

        flow = _fresh_flow()
        src = add_component(flow, "ChatInput", REGISTRY, component_id="Src-00001")
        t1 = add_component(flow, "ChatOutput", REGISTRY, component_id="T1-00001")
        t2 = add_component(flow, "ChatOutput", REGISTRY, component_id="T2-00001")
        t3 = add_component(flow, "ChatOutput", REGISTRY, component_id="T3-00001")
        add_connection(flow, src["id"], "message", t1["id"], "input_value")
        add_connection(flow, src["id"], "message", t2["id"], "input_value")
        add_connection(flow, src["id"], "message", t3["id"], "input_value")
        layout_flow(flow)

        by_id = {n["data"]["id"]: n for n in flow["data"]["nodes"]}
        ys = sorted([by_id[t["id"]]["position"]["y"] for t in [t1, t2, t3]])
        # Check spacing between consecutive nodes
        assert ys[1] - ys[0] == NODE_SPACING_Y
        assert ys[2] - ys[1] == NODE_SPACING_Y

    def test_layout_idempotent(self):
        """Running layout twice produces the same positions."""
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        add_connection(flow, r1["id"], "message", r2["id"], "input_value")

        layout_flow(flow)
        positions_1 = [(n["data"]["id"], n["position"].copy()) for n in flow["data"]["nodes"]]

        layout_flow(flow)
        positions_2 = [(n["data"]["id"], n["position"].copy()) for n in flow["data"]["nodes"]]

        assert positions_1 == positions_2

    def test_layout_single_node_centered_y(self):
        """A single node in a layer should be at y=0."""
        flow = _fresh_flow()
        add_component(flow, "ChatInput", REGISTRY)
        layout_flow(flow)
        assert flow["data"]["nodes"][0]["position"]["y"] == 0.0

    def test_layout_two_disconnected_subgraphs(self):
        """Two independent chains should both get correct layering."""
        from lfx.graph.flow_builder.layout import LAYER_SPACING_X

        flow = _fresh_flow()
        # Chain 1: A -> B
        a = add_component(flow, "ChatInput", REGISTRY, component_id="A-00001")
        b = add_component(flow, "ChatOutput", REGISTRY, component_id="B-00001")
        add_connection(flow, a["id"], "message", b["id"], "input_value")
        # Chain 2: C -> D
        c = add_component(flow, "ChatInput", REGISTRY, component_id="C-00001")
        d = add_component(flow, "ChatOutput", REGISTRY, component_id="D-00001")
        add_connection(flow, c["id"], "message", d["id"], "input_value")
        layout_flow(flow)

        by_id = {n["data"]["id"]: n for n in flow["data"]["nodes"]}
        # Both chains: source at layer 0, target at layer 1
        assert by_id["A-00001"]["position"]["x"] == 0
        assert by_id["B-00001"]["position"]["x"] == LAYER_SPACING_X
        assert by_id["C-00001"]["position"]["x"] == 0
        assert by_id["D-00001"]["position"]["x"] == LAYER_SPACING_X

    def test_assign_layers_directly(self):
        """Test _assign_layers with a known graph."""
        from lfx.graph.flow_builder.layout import _assign_layers

        node_ids = ["A", "B", "C", "D"]
        successors = {"A": ["B", "C"], "B": ["D"], "C": ["D"]}
        predecessors = {"B": ["A"], "C": ["A"], "D": ["B", "C"]}
        layers = _assign_layers(node_ids, successors, predecessors)
        assert layers["A"] == 0
        assert layers["B"] == 1
        assert layers["C"] == 1
        assert layers["D"] == 2


# ---------------------------------------------------------------------------
# Component — additional tests
# ---------------------------------------------------------------------------


class TestComponentExtended:
    def test_configure_overwrites_existing_value(self):
        flow = _fresh_flow()
        r = add_component(flow, "OpenAIModel", REGISTRY)
        # Template starts with value "gpt-4o-mini"
        info = get_component(flow, r["id"])
        assert info["params"]["model_name"] == "gpt-4o-mini"
        # Overwrite
        configure_component(flow, r["id"], {"model_name": "gpt-4o"})
        info2 = get_component(flow, r["id"])
        assert info2["params"]["model_name"] == "gpt-4o"

    def test_add_component_deep_copies_template(self):
        """Modifying a node should not affect the registry or other nodes."""
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatInput", REGISTRY)
        configure_component(flow, r1["id"], {"input_value": "modified"})
        info2 = get_component(flow, r2["id"])
        assert info2["params"]["input_value"] == ""  # unmodified

    def test_list_components_empty_flow(self):
        flow = _fresh_flow()
        assert list_components(flow) == []

    def test_get_component_outputs(self):
        flow = _fresh_flow()
        r = add_component(flow, "OpenAIModel", REGISTRY)
        info = get_component(flow, r["id"])
        output_names = [o["name"] for o in info["outputs"]]
        assert "text_output" in output_names
        assert "model_output" in output_names


# ---------------------------------------------------------------------------
# Connect — additional tests
# ---------------------------------------------------------------------------


class TestConnectErrorCases:
    def test_connect_nonexistent_source_raises(self):
        flow = _fresh_flow()
        add_component(flow, "ChatOutput", REGISTRY, component_id="Target-00001")
        with pytest.raises(ValueError, match="Component not found in flow"):
            add_connection(flow, "NoSuch-00001", "message", "Target-00001", "input_value")

    def test_connect_nonexistent_target_raises(self):
        flow = _fresh_flow()
        add_component(flow, "ChatInput", REGISTRY, component_id="Source-00001")
        with pytest.raises(ValueError, match="Component not found in flow"):
            add_connection(flow, "Source-00001", "message", "NoSuch-00001", "input_value")

    def test_connect_nonexistent_output_raises(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        with pytest.raises(ValueError, match="Output 'bad_output' not found"):
            add_connection(flow, r1["id"], "bad_output", r2["id"], "input_value")

    def test_connect_nonexistent_input_raises(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        with pytest.raises(ValueError, match="Input 'bad_input' not found"):
            add_connection(flow, r1["id"], "message", r2["id"], "bad_input")

    def test_connect_incompatible_types_raises(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ToolOutput", REGISTRY)
        with pytest.raises(ValueError, match="Type mismatch"):
            add_connection(flow, r1["id"], "message", r2["id"], "tools")
        assert len(flow["data"]["edges"]) == 0

    def test_explicit_types_bypass_validation(self):
        """When explicit types are provided, type-compatibility is not enforced."""
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        # Incompatible explicit types -- succeeds because validation is skipped
        edge = add_connection(
            flow,
            r1["id"],
            "message",
            r2["id"],
            "input_value",
            source_types=["Incompatible"],
            target_types=["Mismatch"],
        )
        assert edge["data"]["sourceHandle"]["output_types"] == ["Incompatible"]
        assert edge["data"]["targetHandle"]["inputTypes"] == ["Mismatch"]


class TestConnectExtended:
    def test_explicit_types_override(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        edge = add_connection(
            flow,
            r1["id"],
            "message",
            r2["id"],
            "input_value",
            source_types=["CustomType"],
            target_types=["OtherType"],
        )
        assert edge["data"]["sourceHandle"]["output_types"] == ["CustomType"]
        assert edge["data"]["targetHandle"]["inputTypes"] == ["OtherType"]

    def test_multiple_connections_between_same_pair(self):
        """Two different output->input connections between the same components."""
        flow = _fresh_flow()
        r1 = add_component(flow, "OpenAIModel", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        add_connection(flow, r1["id"], "text_output", r2["id"], "input_value")
        # This would be unusual but should work structurally
        add_connection(
            flow,
            r1["id"],
            "model_output",
            r2["id"],
            "input_value",
            source_types=["LanguageModel"],
        )
        assert len(flow["data"]["edges"]) == 2
        conns = list_connections(flow)
        outputs = {c["source_output"] for c in conns}
        assert outputs == {"text_output", "model_output"}

    def test_remove_connection_by_target_input(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        removed = remove_connection(flow, r1["id"], r2["id"], target_input="input_value")
        assert removed == 1

    def test_list_connections_empty(self):
        flow = _fresh_flow()
        assert list_connections(flow) == []

    def test_source_type_extracted_from_id(self):
        """The source handle dataType should be the component type prefix."""
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY, component_id="ChatInput-abc12")
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        edge = add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        assert edge["data"]["sourceHandle"]["dataType"] == "ChatInput"


# ---------------------------------------------------------------------------
# Flow — additional tests
# ---------------------------------------------------------------------------


class TestFlowExtended:
    def test_flow_info_with_edges(self):
        flow = _fresh_flow()
        r1 = add_component(flow, "ChatInput", REGISTRY)
        r2 = add_component(flow, "ChatOutput", REGISTRY)
        add_connection(flow, r1["id"], "message", r2["id"], "input_value")
        info = flow_info(flow)
        assert info["edge_count"] == 1

    def test_flow_info_description(self):
        flow = empty_flow(name="Named", description="A description")
        info = flow_info(flow)
        assert info["description"] == "A description"

    def test_flow_info_no_inputs_outputs_for_model(self):
        """OpenAIModel is not a ChatInput or ChatOutput."""
        flow = _fresh_flow()
        add_component(flow, "OpenAIModel", REGISTRY)
        info = flow_info(flow)
        assert info["inputs"] == []
        assert info["outputs"] == []
        assert len(info["components"]) == 1


# ---------------------------------------------------------------------------
# CustomStringify — additional tests
# ---------------------------------------------------------------------------


class TestCustomStringifyExtended:
    def test_empty_dict(self):
        assert _custom_stringify({}) == "{}"

    def test_empty_list(self):
        assert _custom_stringify([]) == "[]"

    def test_nested_dict(self):
        result = _custom_stringify({"a": {"b": 1}})
        assert result == '{"a":{"b":1}}'

    def test_string_value(self):
        assert _custom_stringify("hello") == '"hello"'

    def test_scaped_round_trips_handle_format(self):
        """A source handle dict should produce a string that matches Langflow's format."""
        handle = {
            "dataType": "ChatInput",
            "id": "ChatInput-abc12",
            "name": "message",
            "output_types": ["Message"],
        }
        result = _scaped_json_stringify(handle)
        # Should have no double quotes
        assert '"' not in result
        # Should contain the field names with oe
        assert "dataType" in result.replace("\u0153", '"')
        assert "output_types" in result.replace("\u0153", '"')


# ---------------------------------------------------------------------------
# parse_flow_spec — text parser tests
# ---------------------------------------------------------------------------


class TestParseFlowSpec:
    def test_basic_spec(self):
        spec = """\
name: Test Flow
description: A test

nodes:
  A: ChatInput
  B: ChatOutput

edges:
  A.message -> B.input_value
"""
        result = parse_flow_spec(spec)
        assert result["name"] == "Test Flow"
        assert result["description"] == "A test"
        assert len(result["nodes"]) == 2
        assert result["nodes"][0] == {"id": "A", "type": "ChatInput"}
        assert result["nodes"][1] == {"id": "B", "type": "ChatOutput"}
        assert len(result["edges"]) == 1
        assert result["edges"][0] == {
            "source_id": "A",
            "source_output": "message",
            "target_id": "B",
            "target_input": "input_value",
        }

    def test_no_description(self):
        spec = """\
name: Minimal

nodes:
  A: ChatInput
"""
        result = parse_flow_spec(spec)
        assert result["name"] == "Minimal"
        assert result["description"] == ""

    def test_no_edges(self):
        spec = """\
name: No Edges

nodes:
  A: ChatInput
  B: ChatOutput
"""
        result = parse_flow_spec(spec)
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 0

    def test_config_simple_values(self):
        spec = """\
name: Config Test

nodes:
  A: ChatInput

config:
  A.input_value: Hello world
  A.sender_name: Bot
"""
        result = parse_flow_spec(spec)
        assert result["config"] == {"A": {"input_value": "Hello world", "sender_name": "Bot"}}

    def test_config_multiline(self):
        spec = """\
name: Multiline

nodes:
  A: ChatInput

config:
  A.system_prompt: |
    You are a helpful assistant.
    Be concise.
"""
        result = parse_flow_spec(spec)
        assert "You are a helpful assistant." in result["config"]["A"]["system_prompt"]
        assert "Be concise." in result["config"]["A"]["system_prompt"]

    def test_config_multiple_nodes(self):
        spec = """\
name: Multi Config

nodes:
  A: ChatInput
  B: OpenAIModel

config:
  A.input_value: test
  B.model_name: gpt-4o
  B.temperature: 0.5
"""
        result = parse_flow_spec(spec)
        assert result["config"]["A"] == {"input_value": "test"}
        assert result["config"]["B"] == {"model_name": "gpt-4o", "temperature": 0.5}

    def test_multiple_edges(self):
        spec = """\
name: Chain

nodes:
  A: ChatInput
  B: OpenAIModel
  C: ChatOutput

edges:
  A.message -> B.input_value
  B.text_output -> C.input_value
"""
        result = parse_flow_spec(spec)
        assert len(result["edges"]) == 2
        assert result["edges"][0]["source_id"] == "A"
        assert result["edges"][0]["target_id"] == "B"
        assert result["edges"][1]["source_id"] == "B"
        assert result["edges"][1]["target_id"] == "C"

    def test_tool_mode_edge(self):
        spec = """\
name: Agent

nodes:
  A: URLComponent
  B: Agent

edges:
  A.component_as_tool -> B.tools
"""
        result = parse_flow_spec(spec)
        assert result["edges"][0]["source_output"] == "component_as_tool"
        assert result["edges"][0]["target_input"] == "tools"

    def test_empty_nodes_raises(self):
        spec = """\
name: Empty
"""
        with pytest.raises(ValueError, match="No nodes found"):
            parse_flow_spec(spec)

    def test_blank_lines_between_sections(self):
        spec = """\
name: Spaced



nodes:

  A: ChatInput

  B: ChatOutput


edges:

  A.message -> B.input_value

"""
        result = parse_flow_spec(spec)
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

    def test_leading_trailing_whitespace(self):
        spec = """
    name: Indented

    nodes:
      A: ChatInput

    edges:
      A.message -> A.input_value
"""
        result = parse_flow_spec(spec)
        assert result["name"] == "Indented"

    def test_many_nodes(self):
        lines = ["name: Big", "", "nodes:"]
        lines.extend(f"  N{i}: ChatInput" for i in range(10))
        spec = "\n".join(lines)
        result = parse_flow_spec(spec)
        assert len(result["nodes"]) == 10

    def test_config_preserves_multiline_indentation(self):
        spec = """\
name: Indent Test

nodes:
  A: ChatInput

config:
  A.template: |
    Line 1
      Indented line 2
    Line 3
"""
        result = parse_flow_spec(spec)
        tmpl = result["config"]["A"]["template"]
        assert "  Indented line 2" in tmpl

    def test_edge_with_underscores_in_names(self):
        spec = """\
name: Underscores

nodes:
  A: OpenAIModel
  B: Agent

edges:
  A.model_output -> B.model
"""
        result = parse_flow_spec(spec)
        assert result["edges"][0]["source_output"] == "model_output"

    def test_roundtrip_node_ids_preserved(self):
        spec = """\
name: IDs

nodes:
  X: ChatInput
  Y: ChatOutput
  Z: OpenAIModel
"""
        result = parse_flow_spec(spec)
        ids = [n["id"] for n in result["nodes"]]
        assert ids == ["X", "Y", "Z"]

    def test_config_multiline_with_dot_and_colon(self):
        """Continuation lines with dots and colons must not be mistaken for keys."""
        spec = """\
name: DotColon Test

nodes:
  A: ChatInput

config:
  A.system_prompt: |
    You are an assistant. Follow these rules: be polite.
    Also see http://example.com: it has info.
"""
        result = parse_flow_spec(spec)
        prompt = result["config"]["A"]["system_prompt"]
        assert "You are an assistant" in prompt
        assert "Also see http://example.com" in prompt

    def test_config_coerces_int(self):
        spec = """\
name: Coerce

nodes:
  A: ChatInput

config:
  A.max_tokens: 100
"""
        result = parse_flow_spec(spec)
        assert result["config"]["A"]["max_tokens"] == 100
        assert isinstance(result["config"]["A"]["max_tokens"], int)

    def test_config_coerces_float(self):
        spec = """\
name: Coerce

nodes:
  A: ChatInput

config:
  A.temperature: 0.7
"""
        result = parse_flow_spec(spec)
        assert result["config"]["A"]["temperature"] == 0.7
        assert isinstance(result["config"]["A"]["temperature"], float)

    def test_config_coerces_bool(self):
        spec = """\
name: Coerce

nodes:
  A: ChatInput

config:
  A.stream: true
  A.verbose: False
"""
        result = parse_flow_spec(spec)
        assert result["config"]["A"]["stream"] is True
        assert result["config"]["A"]["verbose"] is False

    def test_config_multiline_stays_string(self):
        """Multi-line values (with |) should not be coerced."""
        spec = """\
name: NoCoerce

nodes:
  A: ChatInput

config:
  A.template: |
    42
"""
        result = parse_flow_spec(spec)
        assert result["config"]["A"]["template"] == "42"
        assert isinstance(result["config"]["A"]["template"], str)

    def test_config_coerces_null(self):
        spec = """\
name: Null

nodes:
  A: ChatInput

config:
  A.value: null
"""
        result = parse_flow_spec(spec)
        assert result["config"]["A"]["value"] is None

    def test_edge_unknown_source_in_spec(self):
        """Parser doesn't validate refs, but the structure should be correct."""
        spec = """\
name: Bad Edge

nodes:
  A: ChatInput

edges:
  Z.message -> A.input_value
"""
        result = parse_flow_spec(spec)
        assert result["edges"][0]["source_id"] == "Z"

    def test_config_key_with_long_field_name(self):
        spec = """\
name: Long

nodes:
  A: ChatInput

config:
  A.very_long_field_name_with_underscores: hello
"""
        result = parse_flow_spec(spec)
        assert result["config"]["A"]["very_long_field_name_with_underscores"] == "hello"

    def test_multiline_then_single_line(self):
        """A multi-line value followed by a single-line value."""
        spec = """\
name: Mixed

nodes:
  A: ChatInput

config:
  A.template: |
    Line 1
    Line 2
  A.name: simple
"""
        result = parse_flow_spec(spec)
        assert "Line 1" in result["config"]["A"]["template"]
        assert "Line 2" in result["config"]["A"]["template"]
        assert result["config"]["A"]["name"] == "simple"

    def test_config_multiline_with_key_like_pattern(self):
        """Continuation line that looks like a config key (word.word: value)."""
        spec = """\
name: KeyLike

nodes:
  A: ChatInput

config:
  A.prompt: |
    hello.world: this should stay in the prompt
    config.timeout: 30 seconds
"""
        result = parse_flow_spec(spec)
        prompt = result["config"]["A"]["prompt"]
        assert "hello.world: this should stay" in prompt
        assert "config.timeout: 30" in prompt
        assert len(result["config"]) == 1  # only A, no hello or config node

    def test_sections_in_any_order(self):
        """Config before edges should work."""
        spec = """\
name: Reordered

nodes:
  A: ChatInput
  B: ChatOutput

config:
  A.input_value: test

edges:
  A.message -> B.input_value
"""
        result = parse_flow_spec(spec)
        assert result["config"]["A"]["input_value"] == "test"
        assert len(result["edges"]) == 1
