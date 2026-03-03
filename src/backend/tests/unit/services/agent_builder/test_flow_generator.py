"""Tests for the dynamic agent flow generator."""

import json

import pytest
from langflow.services.agent_builder.flow_generator import (
    _build_edge,
    _generate_node_id,
    _pick_tool_output,
    generate_agent_flow,
)


class TestGenerateNodeId:
    """Tests for _generate_node_id."""

    def test_should_contain_type_prefix(self):
        node_id = _generate_node_id("Agent")
        assert node_id.startswith("Agent-")

    def test_should_have_five_char_suffix(self):
        node_id = _generate_node_id("ChatInput")
        suffix = node_id.split("-", 1)[1]
        assert len(suffix) == 5

    def test_should_generate_unique_ids(self):
        ids = {_generate_node_id("Agent") for _ in range(100)}
        # With 62^5 possibilities, 100 should all be unique
        assert len(ids) == 100

    def test_should_handle_component_name_with_hyphens(self):
        node_id = _generate_node_id("My-Component")
        assert node_id.startswith("My-Component-")


class TestBuildEdge:
    """Tests for _build_edge."""

    def test_should_set_source_and_target(self):
        edge = _build_edge(
            "src-1",
            "ChatInput",
            "message",
            ["Message"],
            "tgt-1",
            "input_value",
            ["Message"],
            "str",
        )
        assert edge["source"] == "src-1"
        assert edge["target"] == "tgt-1"

    def test_should_create_valid_json_handles(self):
        edge = _build_edge(
            "src-1",
            "ChatInput",
            "message",
            ["Message"],
            "tgt-1",
            "input_value",
            ["Message"],
            "str",
        )
        source_handle = json.loads(edge["sourceHandle"])
        assert source_handle["dataType"] == "ChatInput"
        assert source_handle["name"] == "message"

        target_handle = json.loads(edge["targetHandle"])
        assert target_handle["fieldName"] == "input_value"
        assert target_handle["type"] == "str"

    def test_should_embed_handles_in_data(self):
        edge = _build_edge(
            "src-1",
            "Agent",
            "response",
            ["Message"],
            "tgt-1",
            "input_value",
            ["Data"],
            "other",
        )
        assert edge["data"]["sourceHandle"]["name"] == "response"
        assert edge["data"]["targetHandle"]["fieldName"] == "input_value"

    def test_should_create_deterministic_edge_id(self):
        edge = _build_edge(
            "src-1",
            "A",
            "out",
            ["X"],
            "tgt-1",
            "in",
            ["Y"],
            "str",
        )
        assert edge["id"].startswith("reactflow__edge-")
        assert "src-1" in edge["id"]
        assert "tgt-1" in edge["id"]


class TestGenerateAgentFlow:
    """Tests for generate_agent_flow — the main public function."""

    def test_should_produce_valid_flow_structure(self):
        flow = generate_agent_flow("You are helpful.", [])
        assert "data" in flow
        assert "nodes" in flow["data"]
        assert "edges" in flow["data"]
        assert flow["is_component"] is False

    def test_should_create_three_core_nodes_without_tools(self):
        flow = generate_agent_flow("Hello", [])
        nodes = flow["data"]["nodes"]
        types = {n["data"]["type"] for n in nodes}
        assert types == {"ChatInput", "Agent", "ChatOutput"}

    def test_should_create_two_edges_without_tools(self):
        flow = generate_agent_flow("Hello", [])
        edges = flow["data"]["edges"]
        assert len(edges) == 2

    def test_should_inject_system_prompt(self):
        prompt = "You are a math tutor."
        flow = generate_agent_flow(prompt, [])
        agent_node = _find_node_by_type(flow, "Agent")
        template = agent_node["data"]["node"]["template"]
        assert template["system_prompt"]["value"] == prompt

    def test_should_add_tool_nodes_and_edges(self):
        flow = generate_agent_flow("Hi", ["CalculatorComponent", "URLComponent"])
        nodes = flow["data"]["nodes"]
        edges = flow["data"]["edges"]

        node_types = [n["data"]["type"] for n in nodes]
        assert "CalculatorComponent" in node_types
        assert "URLComponent" in node_types
        # 3 core + 2 tools
        assert len(nodes) == 5
        # 2 core edges + 2 tool edges
        assert len(edges) == 4

    def test_tool_edges_should_target_agent_tools_field(self):
        flow = generate_agent_flow("Hi", ["CalculatorComponent"])
        edges = flow["data"]["edges"]

        tool_edges = [e for e in edges if e["data"]["targetHandle"]["fieldName"] == "tools"]
        assert len(tool_edges) == 1

        tool_edge = tool_edges[0]
        assert tool_edge["data"]["sourceHandle"]["name"] == "component_as_tool"
        assert tool_edge["data"]["targetHandle"]["inputTypes"] == ["Tool"]

    def test_should_handle_empty_tool_list(self):
        flow = generate_agent_flow("Hello", [])
        assert len(flow["data"]["nodes"]) == 3
        assert len(flow["data"]["edges"]) == 2

    def test_chat_input_should_be_minimized(self):
        flow = generate_agent_flow("Hi", [])
        chat_input = _find_node_by_type(flow, "ChatInput")
        assert chat_input["data"]["showNode"] is False

    def test_chat_output_should_be_minimized(self):
        flow = generate_agent_flow("Hi", [])
        chat_output = _find_node_by_type(flow, "ChatOutput")
        assert chat_output["data"]["showNode"] is False

    def test_agent_should_not_be_minimized(self):
        flow = generate_agent_flow("Hi", [])
        agent = _find_node_by_type(flow, "Agent")
        assert agent["data"]["showNode"] is True

    def test_all_nodes_should_be_generic_node_type(self):
        flow = generate_agent_flow("Hi", ["CalculatorComponent"])
        for node in flow["data"]["nodes"]:
            assert node["type"] == "genericNode"

    # Adversarial tests

    def test_should_handle_empty_system_prompt(self):
        flow = generate_agent_flow("", [])
        agent = _find_node_by_type(flow, "Agent")
        assert agent["data"]["node"]["template"]["system_prompt"]["value"] == ""

    def test_should_handle_very_long_system_prompt(self):
        long_prompt = "x" * 10000
        flow = generate_agent_flow(long_prompt, [])
        agent = _find_node_by_type(flow, "Agent")
        assert agent["data"]["node"]["template"]["system_prompt"]["value"] == long_prompt

    def test_should_handle_special_characters_in_prompt(self):
        prompt = 'He said "hello" & <world> \n\ttab'
        flow = generate_agent_flow(prompt, [])
        agent = _find_node_by_type(flow, "Agent")
        assert agent["data"]["node"]["template"]["system_prompt"]["value"] == prompt

    def test_should_deduplicate_tool_names(self):
        """Duplicate tools are deduplicated to avoid 'Tool names must be unique' API errors."""
        flow = generate_agent_flow("Hi", ["Calc", "Calc"])
        nodes = flow["data"]["nodes"]
        calc_nodes = [n for n in nodes if n["data"]["type"] == "Calc"]
        assert len(calc_nodes) == 1
        # 3 core nodes + 1 deduplicated tool
        assert len(nodes) == 4

    def test_generated_json_should_be_serializable(self):
        flow = generate_agent_flow("Hi", ["CalculatorComponent"])
        serialized = json.dumps(flow)
        deserialized = json.loads(serialized)
        assert deserialized == flow


class TestToolOutputSelection:
    """Tests for _pick_tool_output and tool edge routing.

    Bug: 'Tool names must be unique' from Anthropic API.
    Root cause: LCToolComponent subclasses (CalculatorTool, TavilyAISearch)
    both inherit api_run_model output. to_toolkit() creates tools named
    'run_model' for each, causing duplicates. Fix: use api_build_tool
    output for LCToolComponent types, which returns properly-named tools.
    """

    def test_pick_tool_output_returns_api_build_tool_for_lc_tool_components(self):
        outputs = [
            {"name": "api_run_model", "method": "run_model", "types": ["Data"]},
            {"name": "api_build_tool", "method": "build_tool", "types": ["Tool"]},
        ]
        assert _pick_tool_output(outputs) == "api_build_tool"

    def test_pick_tool_output_returns_component_as_tool_for_regular_components(self):
        outputs = [
            {"name": "result", "method": "evaluate_expression", "types": ["Data"]},
        ]
        assert _pick_tool_output(outputs) == "component_as_tool"

    def test_pick_tool_output_returns_component_as_tool_when_no_outputs(self):
        assert _pick_tool_output(None) == "component_as_tool"
        assert _pick_tool_output([]) == "component_as_tool"

    def test_lc_tool_edges_use_api_build_tool(self):
        """LCToolComponent edges must use api_build_tool to avoid name collisions."""
        lc_outputs = {
            "CalculatorTool": [
                {"name": "api_run_model", "method": "run_model", "types": ["Data"]},
                {"name": "api_build_tool", "method": "build_tool", "types": ["Tool"]},
            ],
            "TavilyAISearch": [
                {"name": "api_run_model", "method": "run_model", "types": ["Data"]},
                {"name": "api_build_tool", "method": "build_tool", "types": ["Tool"]},
            ],
        }
        flow = generate_agent_flow(
            "Hi", ["CalculatorTool", "TavilyAISearch"], tool_outputs=lc_outputs,
        )
        tool_edges = [
            e for e in flow["data"]["edges"]
            if e["data"]["targetHandle"]["fieldName"] == "tools"
        ]
        assert len(tool_edges) == 2
        for edge in tool_edges:
            assert edge["data"]["sourceHandle"]["name"] == "api_build_tool"

    def test_regular_component_edges_use_component_as_tool(self):
        """Regular components should still use component_as_tool."""
        reg_outputs = {
            "CalculatorComponent": [
                {"name": "result", "method": "evaluate_expression", "types": ["Data"]},
            ],
        }
        flow = generate_agent_flow("Hi", ["CalculatorComponent"], tool_outputs=reg_outputs)
        tool_edges = [
            e for e in flow["data"]["edges"]
            if e["data"]["targetHandle"]["fieldName"] == "tools"
        ]
        assert len(tool_edges) == 1
        assert tool_edges[0]["data"]["sourceHandle"]["name"] == "component_as_tool"


class TestCodeFieldPresence:
    """Tests that every node template includes a 'code' field.

    Bug: KeyError: 'code' at instantiate_class() in loading.py (line 43).
    Root cause: generate_agent_flow() produces templates without the 'code'
    field that instantiate_class() requires via custom_params.pop("code").
    """

    def test_should_include_code_field_in_all_core_node_templates(self):
        """All 3 core nodes (ChatInput, Agent, ChatOutput) must have a code field."""
        flow = generate_agent_flow("You are helpful.", [])
        for node in flow["data"]["nodes"]:
            template = node["data"]["node"]["template"]
            node_type = node["data"]["type"]
            assert "code" in template, f"Node '{node_type}' template is missing 'code' field"

    def test_should_include_code_field_with_type_code(self):
        """The code field must have type='code' for param processing."""
        flow = generate_agent_flow("Hello", [])
        for node in flow["data"]["nodes"]:
            template = node["data"]["node"]["template"]
            node_type = node["data"]["type"]
            assert template["code"]["type"] == "code", (
                f"Node '{node_type}' code field has wrong type: {template['code'].get('type')}"
            )

    def test_should_include_code_field_with_nonempty_value(self):
        """The code value must contain actual Python source code."""
        flow = generate_agent_flow("Hello", [])
        for node in flow["data"]["nodes"]:
            template = node["data"]["node"]["template"]
            node_type = node["data"]["type"]
            code_value = template["code"]["value"]
            assert isinstance(code_value, str), (
                f"Node '{node_type}' code field value is not a string"
            )
            assert len(code_value) > 0, (
                f"Node '{node_type}' code field has empty value"
            )

    def test_should_include_code_field_with_valid_python(self):
        """The code value must be parseable Python source."""
        import ast

        flow = generate_agent_flow("Hello", [])
        for node in flow["data"]["nodes"]:
            template = node["data"]["node"]["template"]
            node_type = node["data"]["type"]
            code_value = template["code"]["value"]
            try:
                ast.parse(code_value)
            except SyntaxError as e:
                pytest.fail(f"Node '{node_type}' code field contains invalid Python: {e}")

    def test_should_include_code_field_in_tool_node_templates(self):
        """Tool nodes must also have a code field."""
        flow = generate_agent_flow("Hi", ["CalculatorComponent"])
        tool_nodes = [
            n for n in flow["data"]["nodes"] if n["data"]["type"] == "CalculatorComponent"
        ]
        assert len(tool_nodes) == 1
        template = tool_nodes[0]["data"]["node"]["template"]
        assert "code" in template, "Tool node template is missing 'code' field"
        assert template["code"]["type"] == "code"
        assert isinstance(template["code"]["value"], str)
        assert len(template["code"]["value"]) > 0


class TestShowFieldAttribute:
    """Tests that template fields include 'show': True.

    Bug: ValueError 'A model selection is required' at unified_models.py.
    Root cause: param_handler.py's should_skip_field() skips any field
    without 'show': True (except 'code'), so the model field was silently
    dropped during vertex parameter processing.
    """

    def test_agent_template_model_field_has_show_true(self):
        """The model field must have show=True so param_handler processes it."""
        flow = generate_agent_flow("Hello", [])
        agent = _find_node_by_type(flow, "Agent")
        model_field = agent["data"]["node"]["template"]["model"]
        assert model_field.get("show") is True, "Agent model field missing 'show': True"

    def test_agent_template_has_context_id_with_empty_string_default(self):
        """context_id must exist with value='' to prevent MessageTextInput None validation error."""
        flow = generate_agent_flow("Hello", [])
        agent = _find_node_by_type(flow, "Agent")
        template = agent["data"]["node"]["template"]
        assert "context_id" in template, "Agent template missing 'context_id' field"
        assert template["context_id"]["value"] == "", "context_id must default to empty string, not None"

    def test_all_agent_template_fields_have_show_attribute(self):
        """Every field in the Agent template must have an explicit show attribute.

        Most fields need show=True so param_handler processes them.
        IBM-specific conditional fields (base_url_ibm_watsonx, project_id)
        intentionally use show=False as they are only shown when IBM is selected.
        """
        # Fields that intentionally have show=False (conditional IBM watsonx fields)
        show_false_allowed = {"base_url_ibm_watsonx", "project_id"}
        flow = generate_agent_flow("Hello", [])
        agent = _find_node_by_type(flow, "Agent")
        template = agent["data"]["node"]["template"]
        for field_name, field_def in template.items():
            if field_name.startswith("_") or not isinstance(field_def, dict):
                continue
            if field_name in show_false_allowed:
                assert "show" in field_def, (
                    f"Agent template field '{field_name}' missing 'show' attribute"
                )
            else:
                assert field_def.get("show") is True, (
                    f"Agent template field '{field_name}' missing 'show': True"
                )

    def test_all_chat_input_template_fields_have_show_true(self):
        """Every field in the ChatInput template must have show=True."""
        flow = generate_agent_flow("Hello", [])
        node = _find_node_by_type(flow, "ChatInput")
        template = node["data"]["node"]["template"]
        for field_name, field_def in template.items():
            if field_name.startswith("_") or not isinstance(field_def, dict):
                continue
            assert field_def.get("show") is True, (
                f"ChatInput template field '{field_name}' missing 'show': True"
            )

    def test_all_chat_output_template_fields_have_show_true(self):
        """Every field in the ChatOutput template must have show=True."""
        flow = generate_agent_flow("Hello", [])
        node = _find_node_by_type(flow, "ChatOutput")
        template = node["data"]["node"]["template"]
        for field_name, field_def in template.items():
            if field_name.startswith("_") or not isinstance(field_def, dict):
                continue
            assert field_def.get("show") is True, (
                f"ChatOutput template field '{field_name}' missing 'show': True"
            )


def _find_node_by_type(flow: dict, node_type: str) -> dict:
    """Helper to find a node by its type in the flow."""
    for node in flow["data"]["nodes"]:
        if node["data"]["type"] == node_type:
            return node
    pytest.fail(f"Node of type {node_type} not found")
