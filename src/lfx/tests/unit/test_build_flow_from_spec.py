"""Tests for lfx.graph.flow_builder.builder and flow_to_spec_summary.

Uses the real component_index.json registry.
"""

from lfx.graph.flow_builder.builder import build_flow_from_spec
from lfx.graph.flow_builder.flow import flow_to_spec_summary


class TestBuildFlowFromSpec:
    def test_simple_chat_flow(self):
        spec = """\
name: Simple Chat
description: A basic chatbot

nodes:
  A: ChatInput
  B: ChatOutput

edges:
  A.message -> B.input_value
"""
        result = build_flow_from_spec(spec)
        assert "flow" in result, f"Expected flow, got: {result}"
        assert result["name"] == "Simple Chat"
        assert result["node_count"] == 2
        assert result["edge_count"] == 1
        assert "A" in result["node_id_map"]
        assert "B" in result["node_id_map"]

    def test_three_node_flow(self):
        spec = """\
name: Chat with Model

nodes:
  A: ChatInput
  B: OpenAIModel
  C: ChatOutput

edges:
  A.message -> B.input_value
  B.text_output -> C.input_value
"""
        result = build_flow_from_spec(spec)
        assert "flow" in result, f"Expected flow, got: {result}"
        assert result["node_count"] == 3
        assert result["edge_count"] == 2

    def test_with_config(self):
        spec = """\
name: Configured Flow

nodes:
  A: ChatInput
  B: ChatOutput

edges:
  A.message -> B.input_value

config:
  A.input_value: Hello world
"""
        result = build_flow_from_spec(spec)
        assert "flow" in result, f"Expected flow, got: {result}"
        # Verify the config was applied
        nodes = result["flow"]["data"]["nodes"]
        chat_input = next(n for n in nodes if n["data"]["type"] == "ChatInput")
        template = chat_input["data"]["node"]["template"]
        assert template["input_value"]["value"] == "Hello world"

    def test_unknown_component_type(self):
        spec = """\
name: Bad Flow

nodes:
  A: TotallyFakeComponent
"""
        result = build_flow_from_spec(spec)
        assert "error" in result
        assert "Unknown component" in result["error"]

    def test_unknown_node_in_edge(self):
        spec = """\
name: Bad Edge

nodes:
  A: ChatInput

edges:
  A.message -> Z.input_value
"""
        result = build_flow_from_spec(spec)
        assert "error" in result
        assert "unknown" in result["error"].lower()

    def test_unknown_node_in_config(self):
        spec = """\
name: Bad Config

nodes:
  A: ChatInput

config:
  Z.field: value
"""
        result = build_flow_from_spec(spec)
        assert "error" in result
        assert "unknown" in result["error"].lower()

    def test_invalid_spec_syntax(self):
        result = build_flow_from_spec("just some random text")
        assert "error" in result

    def test_empty_spec(self):
        result = build_flow_from_spec("")
        assert "error" in result

    def test_flow_has_valid_structure(self):
        spec = """\
name: Structure Test

nodes:
  A: ChatInput
  B: ChatOutput

edges:
  A.message -> B.input_value
"""
        result = build_flow_from_spec(spec)
        assert "flow" in result
        flow = result["flow"]
        assert "data" in flow
        assert "nodes" in flow["data"]
        assert "edges" in flow["data"]
        assert "viewport" in flow["data"]
        # Each node should have proper Langflow structure
        for node in flow["data"]["nodes"]:
            assert "data" in node
            assert "id" in node["data"]
            assert "type" in node["data"]
            assert "node" in node["data"]
            assert "template" in node["data"]["node"]

    def test_nodes_only_no_edges(self):
        spec = """\
name: Disconnected

nodes:
  A: ChatInput
  B: ChatOutput
"""
        result = build_flow_from_spec(spec)
        assert "flow" in result, f"Expected flow, got: {result}"
        assert result["node_count"] == 2
        assert result["edge_count"] == 0


class TestFlowToSpecSummary:
    def test_summary_of_built_flow(self):
        spec = """\
name: Chat Flow

nodes:
  A: ChatInput
  B: OpenAIModel
  C: ChatOutput

edges:
  A.message -> B.input_value
  B.text_output -> C.input_value
"""
        result = build_flow_from_spec(spec)
        summary = flow_to_spec_summary(result["flow"])
        assert "Chat Flow" in summary
        assert "ChatInput" in summary
        assert "OpenAIModel" in summary
        assert "ChatOutput" in summary
        assert "connections:" in summary

    def test_empty_flow(self):
        summary = flow_to_spec_summary({"data": {"nodes": [], "edges": []}})
        assert summary == "(empty canvas)"

    def test_no_data(self):
        summary = flow_to_spec_summary({})
        assert summary == "(empty canvas)"

    def test_nodes_without_edges(self):
        result = build_flow_from_spec("name: Solo\nnodes:\n  A: ChatInput")
        summary = flow_to_spec_summary(result["flow"])
        assert "ChatInput" in summary
        assert "connections:" not in summary
