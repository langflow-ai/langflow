"""Tests for langflow.processing.expand_flow module."""

import pytest
from langflow.processing.expand_flow import (
    CompactEdge,
    CompactFlowData,
    CompactNode,
    _build_source_handle_data,
    _build_target_handle_data,
    _expand_node,
    _get_flat_components,
    expand_compact_flow,
)
from pydantic import ValidationError


class TestCompactNode:
    def test_basic(self):
        node = CompactNode(id="1", type="ChatInput")
        assert node.id == "1"
        assert node.type == "ChatInput"
        assert node.values == {}
        assert node.edited is False
        assert node.node is None

    def test_with_values(self):
        node = CompactNode(id="1", type="OpenAI", values={"model": "gpt-4"})
        assert node.values == {"model": "gpt-4"}

    def test_edited_with_node(self):
        node_data = {"template": {"code": {"value": "x=1"}}}
        node = CompactNode(id="1", type="Custom", edited=True, node=node_data)
        assert node.edited is True
        assert node.node == node_data


class TestCompactEdge:
    def test_basic(self):
        edge = CompactEdge(source="1", source_output="message", target="2", target_input="input_value")
        assert edge.source == "1"
        assert edge.source_output == "message"
        assert edge.target == "2"
        assert edge.target_input == "input_value"


class TestCompactFlowData:
    def test_basic(self):
        data = CompactFlowData(
            nodes=[CompactNode(id="1", type="ChatInput")],
            edges=[CompactEdge(source="1", source_output="msg", target="2", target_input="inp")],
        )
        assert len(data.nodes) == 1
        assert len(data.edges) == 1

    def test_empty(self):
        data = CompactFlowData(nodes=[], edges=[])
        assert len(data.nodes) == 0
        assert len(data.edges) == 0


class TestGetFlatComponents:
    def test_flattens_nested_dict(self):
        all_types = {
            "inputs": {
                "ChatInput": {"template": {}},
                "TextInput": {"template": {}},
            },
            "models": {
                "OpenAIModel": {"template": {}},
            },
        }
        flat = _get_flat_components(all_types)
        assert "ChatInput" in flat
        assert "TextInput" in flat
        assert "OpenAIModel" in flat
        assert len(flat) == 3

    def test_empty(self):
        assert _get_flat_components({}) == {}

    def test_non_dict_values_skipped(self):
        all_types = {
            "inputs": {"ChatInput": {"template": {}}},
            "metadata": "not a dict",
        }
        flat = _get_flat_components(all_types)
        assert "ChatInput" in flat
        assert len(flat) == 1


class TestExpandNode:
    def test_basic_expansion(self):
        flat = {
            "ChatInput": {
                "template": {
                    "input_value": {"value": "", "type": "str"},
                },
                "outputs": [],
            },
        }
        node = CompactNode(id="n1", type="ChatInput", values={"input_value": "hello"})
        result = _expand_node(node, flat)
        assert result["id"] == "n1"
        assert result["type"] == "genericNode"
        assert result["data"]["type"] == "ChatInput"
        assert result["data"]["id"] == "n1"
        # Value should be merged into template
        template = result["data"]["node"]["template"]
        assert template["input_value"]["value"] == "hello"

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="not found in component index"):
            _expand_node(CompactNode(id="1", type="NonexistentType"), {})

    def test_edited_node_uses_node_data(self):
        node_data = {"template": {"x": {"value": 42}}, "outputs": []}
        node = CompactNode(id="n1", type="Custom", edited=True, node=node_data)
        result = _expand_node(node, {})
        assert result["data"]["node"] == node_data

    def test_edited_without_node_data_raises(self):
        node = CompactNode(id="n1", type="Custom", edited=True)
        with pytest.raises(ValueError, match="marked as edited but has no node data"):
            _expand_node(node, {})

    def test_new_field_added_to_template(self):
        flat = {
            "MyComp": {"template": {"existing": {"value": "old"}}},
        }
        node = CompactNode(id="n1", type="MyComp", values={"new_field": "new_value"})
        result = _expand_node(node, flat)
        template = result["data"]["node"]["template"]
        assert template["new_field"] == {"value": "new_value"}

    def test_template_key_copied(self):
        """Verify that expanding a node copies the template dict (shallow).

        So the flat_components lookup table can be reused for another node of the same type.
        """
        flat = {
            "MyComp": {"template": {"field": {"value": "original"}}},
        }
        node = CompactNode(id="n1", type="MyComp", values={"field": "changed"})
        result = _expand_node(node, flat)
        # The result's template should be a different dict object than the original
        assert result["data"]["node"]["template"] is not flat["MyComp"]["template"]


class TestBuildHandleData:
    def test_source_handle(self):
        result = _build_source_handle_data("node1", "ChatInput", "message", ["Message"])
        assert result == {
            "dataType": "ChatInput",
            "id": "node1",
            "name": "message",
            "output_types": ["Message"],
        }

    def test_target_handle(self):
        result = _build_target_handle_data("node2", "input_value", ["Message", "Text"], "str")
        assert result == {
            "fieldName": "input_value",
            "id": "node2",
            "inputTypes": ["Message", "Text"],
            "type": "str",
        }


class TestExpandCompactFlow:
    def test_nodes_only(self):
        all_types = {
            "inputs": {
                "ChatInput": {
                    "template": {"input_value": {"value": ""}},
                    "outputs": [],
                },
            },
        }
        compact = {
            "nodes": [{"id": "1", "type": "ChatInput"}],
            "edges": [],
        }
        result = expand_compact_flow(compact, all_types)
        assert len(result["nodes"]) == 1
        assert len(result["edges"]) == 0
        assert result["nodes"][0]["id"] == "1"

    def test_multiple_nodes(self):
        all_types = {
            "inputs": {
                "ChatInput": {"template": {}, "outputs": []},
                "TextInput": {"template": {}, "outputs": []},
            },
        }
        compact = {
            "nodes": [
                {"id": "1", "type": "ChatInput"},
                {"id": "2", "type": "TextInput"},
            ],
            "edges": [],
        }
        result = expand_compact_flow(compact, all_types)
        assert len(result["nodes"]) == 2

    def test_invalid_compact_data_raises(self):
        with pytest.raises(ValidationError):
            expand_compact_flow({"nodes": "invalid"}, {})
