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


class TestLoadLocalRegistryEncoding:
    """Regression: registry JSON must be read as UTF-8 regardless of the OS locale.

    Bug: on Windows the default text encoding is cp1252, which rejects the UTF-8
    bytes embedded in ``component_index.json`` (first occurrence: byte 0x8f at
    offset 590097). Every Flow Builder tool that touches the registry crashed
    with ``UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f``.
    """

    def test_should_load_registry_when_system_default_encoding_is_cp1252(self, monkeypatch):
        from pathlib import Path

        from lfx.graph.flow_builder import builder as builder_module

        monkeypatch.setattr(builder_module, "_registry_cache", None)

        original_open = Path.open

        def windows_like_open(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
            if "b" not in mode and encoding is None:
                encoding = "cp1252"
            return original_open(self, mode, buffering, encoding, errors, newline)

        monkeypatch.setattr(Path, "open", windows_like_open)

        registry = builder_module.load_local_registry()

        assert isinstance(registry, dict)
        assert registry, "registry must contain at least one component after a successful UTF-8 load"


class TestBuildFlowFromSpecModelFieldNormalization:
    r"""Regression: PR-12575 round 7 — bug 2 reopened on the build path.

    The flow-builder agent emits a YAML multi-line block in config when
    asked to "Build a brand-new agent flow":

        config:
          Ag.model: |
            - provider: OpenAI
              name: gpt-5.4

    The parser keeps multi-line values as raw strings, and the builder
    helper at ``flow_builder/component.py::configure_component`` writes
    them straight into ``template['model'].value``. Without
    normalization at this layer, ``verify_built_flow`` fails three times
    with ``ValueError: missing a provider`` and the UI ModelInput
    renders the raw YAML truncated. The fix lives in the shared
    helper so this path AND the ConfigureComponent tool path go through
    the same normalizer.
    """

    def test_should_normalize_model_field_when_spec_emits_yaml_block(self):
        spec = (
            "name: Agent Test\n"
            "\n"
            "nodes:\n"
            "  Ag: Agent\n"
            "\n"
            "config:\n"
            "  Ag.model: |\n"
            "    - provider: OpenAI\n"
            "      name: gpt-5.4\n"
        )
        result = build_flow_from_spec(spec)
        assert "flow" in result, f"build failed: {result}"
        nodes = result["flow"]["data"]["nodes"]
        agent = next(n for n in nodes if n["data"]["type"] == "Agent")
        value = agent["data"]["node"]["template"]["model"]["value"]
        assert isinstance(value, list), (
            f"model value must be a canonical list[dict] after build, got {type(value).__name__}: {value!r}"
        )
        assert len(value) == 1, f"expected 1-element list, got {value!r}"
        assert value[0].get("provider") == "OpenAI", (
            f"provider must be parsed from the YAML block, got provider={value[0].get('provider')!r} "
            f"(catalog 'Unknown' fallback firing → user sees the 'missing a provider' ValueError)"
        )
        assert value[0].get("name") == "gpt-5.4", f"name must be the bare model name, got {value[0].get('name')!r}"

    def test_should_normalize_model_field_when_spec_emits_json_inline(self):
        spec = (
            "name: Agent Test\n"
            "\n"
            "nodes:\n"
            "  Ag: Agent\n"
            "\n"
            "config:\n"
            '  Ag.model: [{"provider": "OpenAI", "name": "gpt-5.4"}]\n'
        )
        result = build_flow_from_spec(spec)
        assert "flow" in result, f"build failed: {result}"
        nodes = result["flow"]["data"]["nodes"]
        agent = next(n for n in nodes if n["data"]["type"] == "Agent")
        value = agent["data"]["node"]["template"]["model"]["value"]
        assert isinstance(value, list)
        assert len(value) == 1
        assert value[0].get("provider") == "OpenAI"
        assert value[0].get("name") == "gpt-5.4"


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
