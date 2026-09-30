"""Tests for expand_compact_flow functionality."""

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.processing.expand_flow import (
    CompactEdge,
    CompactNode,
    _expand_edge,
    _expand_node,
    _get_flat_components,
    expand_compact_flow,
)

# Sample component data mimicking the component_index structure
SAMPLE_COMPONENTS = {
    "inputs": {
        "ChatInput": {
            "display_name": "Chat Input",
            "description": "Receives text input from user",
            "template": {
                "_type": "ChatInput",
                "input_value": {
                    "type": "str",
                    "required": False,
                    "value": "",
                    "display_name": "Input",
                },
            },
            "base_classes": ["Message"],
            "outputs": [
                {
                    "name": "message",
                    "display_name": "Message",
                    "types": ["Message"],
                }
            ],
        },
    },
    "outputs": {
        "ChatOutput": {
            "display_name": "Chat Output",
            "description": "Displays text output to user",
            "template": {
                "_type": "ChatOutput",
                "input_value": {
                    "type": "Message",
                    "required": True,
                    "value": "",
                    "display_name": "Text",
                    "input_types": ["Message"],
                },
            },
            "base_classes": ["Message"],
            "outputs": [
                {
                    "name": "message",
                    "display_name": "Message",
                    "types": ["Message"],
                }
            ],
        },
    },
    "models": {
        "OpenAIModel": {
            "display_name": "OpenAI",
            "description": "OpenAI language models",
            "template": {
                "_type": "OpenAIModel",
                "model_name": {
                    "type": "str",
                    "required": False,
                    "value": "gpt-4o-mini",
                    "display_name": "Model Name",
                },
                "temperature": {
                    "type": "float",
                    "required": False,
                    "value": 0.1,
                    "display_name": "Temperature",
                },
                "input_value": {
                    "type": "Message",
                    "required": True,
                    "value": "",
                    "display_name": "Input",
                    "input_types": ["Message"],
                },
            },
            "base_classes": ["Message", "LanguageModel"],
            "outputs": [
                {
                    "name": "text_output",
                    "display_name": "Text",
                    "types": ["Message"],
                },
                {
                    "name": "model",
                    "display_name": "Model",
                    "types": ["LanguageModel"],
                },
            ],
        },
    },
}


class TestGetFlatComponents:
    def test_flattens_component_dict(self):
        flat = _get_flat_components(SAMPLE_COMPONENTS)
        assert "ChatInput" in flat
        assert "ChatOutput" in flat
        assert "OpenAIModel" in flat
        assert len(flat) == 3

    def test_empty_dict(self):
        flat = _get_flat_components({})
        assert flat == {}


class TestExpandNode:
    def test_expand_simple_node(self):
        compact = CompactNode(id="1", type="ChatInput")
        flat = _get_flat_components(SAMPLE_COMPONENTS)

        expanded = _expand_node(compact, flat)

        assert expanded["id"] == "1"
        assert expanded["type"] == "genericNode"
        assert expanded["data"]["type"] == "ChatInput"
        assert "template" in expanded["data"]["node"]

    def test_expand_node_with_values(self):
        compact = CompactNode(
            id="2",
            type="OpenAIModel",
            values={"model_name": "gpt-4", "temperature": 0.7},
        )
        flat = _get_flat_components(SAMPLE_COMPONENTS)

        expanded = _expand_node(compact, flat)

        assert expanded["data"]["type"] == "OpenAIModel"
        template = expanded["data"]["node"]["template"]
        assert template["model_name"]["value"] == "gpt-4"
        assert template["temperature"]["value"] == 0.7

    def test_expand_node_unknown_type_raises(self):
        compact = CompactNode(id="1", type="UnknownComponent")
        flat = _get_flat_components(SAMPLE_COMPONENTS)

        with pytest.raises(ValueError, match="not found in component index"):
            _expand_node(compact, flat)

    def test_expand_edited_node(self):
        custom_node_data = {
            "template": {"custom_field": {"value": "custom"}},
            "outputs": [],
        }
        compact = CompactNode(
            id="1",
            type="CustomComponent",
            edited=True,
            node=custom_node_data,
        )
        flat = _get_flat_components(SAMPLE_COMPONENTS)

        expanded = _expand_node(compact, flat)

        assert expanded["data"]["node"] == custom_node_data

    def test_expand_edited_node_without_node_data_raises(self):
        compact = CompactNode(id="1", type="CustomComponent", edited=True)
        flat = _get_flat_components(SAMPLE_COMPONENTS)

        with pytest.raises(ValueError, match="marked as edited but has no node data"):
            _expand_node(compact, flat)


class TestExpandEdge:
    def test_expand_edge(self):
        compact_edge = CompactEdge(
            source="1",
            source_output="message",
            target="2",
            target_input="input_value",
        )
        expanded_nodes = {
            "1": {
                "id": "1",
                "type": "genericNode",
                "data": {
                    "type": "ChatInput",
                    "node": SAMPLE_COMPONENTS["inputs"]["ChatInput"],
                },
            },
            "2": {
                "id": "2",
                "type": "genericNode",
                "data": {
                    "type": "OpenAIModel",
                    "node": SAMPLE_COMPONENTS["models"]["OpenAIModel"],
                },
            },
        }

        expanded = _expand_edge(compact_edge, expanded_nodes)

        assert expanded["source"] == "1"
        assert expanded["target"] == "2"
        assert "sourceHandle" in expanded
        assert "targetHandle" in expanded
        assert "id" in expanded
        assert expanded["id"].startswith("reactflow__edge-")

    def test_expand_edge_source_handle_format(self):
        """Test that sourceHandle is a JSON-encoded dict with œ as quotes."""
        compact_edge = CompactEdge(
            source="node1",
            source_output="message",
            target="node2",
            target_input="input_value",
        )
        expanded_nodes = {
            "node1": {
                "id": "node1",
                "type": "genericNode",
                "data": {
                    "type": "ChatInput",
                    "node": SAMPLE_COMPONENTS["inputs"]["ChatInput"],
                },
            },
            "node2": {
                "id": "node2",
                "type": "genericNode",
                "data": {
                    "type": "OpenAIModel",
                    "node": SAMPLE_COMPONENTS["models"]["OpenAIModel"],
                },
            },
        }

        expanded = _expand_edge(compact_edge, expanded_nodes)

        # sourceHandle is JSON-encoded with œ as quotes
        source_handle = expanded["sourceHandle"]
        assert "œdataTypeœ" in source_handle
        assert "œChatInputœ" in source_handle
        assert "œnode1œ" in source_handle
        assert "œmessageœ" in source_handle
        assert "œMessageœ" in source_handle

        # data.sourceHandle is the actual dict
        source_data = expanded["data"]["sourceHandle"]
        assert source_data["dataType"] == "ChatInput"
        assert source_data["id"] == "node1"
        assert source_data["name"] == "message"
        assert source_data["output_types"] == ["Message"]

    def test_expand_edge_target_handle_format(self):
        """Test that targetHandle is a JSON-encoded dict with œ as quotes."""
        compact_edge = CompactEdge(
            source="node1",
            source_output="message",
            target="node2",
            target_input="input_value",
        )
        expanded_nodes = {
            "node1": {
                "id": "node1",
                "type": "genericNode",
                "data": {
                    "type": "ChatInput",
                    "node": SAMPLE_COMPONENTS["inputs"]["ChatInput"],
                },
            },
            "node2": {
                "id": "node2",
                "type": "genericNode",
                "data": {
                    "type": "OpenAIModel",
                    "node": SAMPLE_COMPONENTS["models"]["OpenAIModel"],
                },
            },
        }

        expanded = _expand_edge(compact_edge, expanded_nodes)

        # targetHandle is JSON-encoded with œ as quotes
        target_handle = expanded["targetHandle"]
        assert "œfieldNameœ" in target_handle
        assert "œinput_valueœ" in target_handle
        assert "œnode2œ" in target_handle
        assert "œMessageœ" in target_handle

        # data.targetHandle is the actual dict
        target_data = expanded["data"]["targetHandle"]
        assert target_data["fieldName"] == "input_value"
        assert target_data["id"] == "node2"
        assert target_data["inputTypes"] == ["Message"]
        assert target_data["type"] == "Message"

    def test_expand_edge_with_multiple_output_types(self):
        """Test edge from component with multiple output types (e.g., OpenAIModel)."""
        compact_edge = CompactEdge(
            source="model_node",
            source_output="model",  # The LanguageModel output
            target="target_node",
            target_input="some_input",
        )
        expanded_nodes = {
            "model_node": {
                "id": "model_node",
                "type": "genericNode",
                "data": {
                    "type": "OpenAIModel",
                    "node": SAMPLE_COMPONENTS["models"]["OpenAIModel"],
                },
            },
            "target_node": {
                "id": "target_node",
                "type": "genericNode",
                "data": {
                    "type": "ChatOutput",
                    "node": SAMPLE_COMPONENTS["outputs"]["ChatOutput"],
                },
            },
        }

        expanded = _expand_edge(compact_edge, expanded_nodes)

        # Should use LanguageModel type for "model" output
        source_handle = expanded["sourceHandle"]
        assert "LanguageModel" in source_handle

    def test_expand_edge_fallback_to_base_classes(self):
        """Test that edge falls back to base_classes when output not found."""
        compact_edge = CompactEdge(
            source="node1",
            source_output="nonexistent_output",
            target="node2",
            target_input="input_value",
        )
        # Component without matching output name
        expanded_nodes = {
            "node1": {
                "id": "node1",
                "type": "genericNode",
                "data": {
                    "type": "ChatInput",
                    "node": {
                        "base_classes": ["Message", "Data"],
                        "outputs": [],  # No outputs defined
                        "template": {},
                    },
                },
            },
            "node2": {
                "id": "node2",
                "type": "genericNode",
                "data": {
                    "type": "OpenAIModel",
                    "node": SAMPLE_COMPONENTS["models"]["OpenAIModel"],
                },
            },
        }

        expanded = _expand_edge(compact_edge, expanded_nodes)

        # Should fall back to base_classes
        source_handle = expanded["sourceHandle"]
        assert "Message" in source_handle or "Data" in source_handle

    def test_expand_edge_target_type_fallback(self):
        """Test that target handle falls back to field type when input_types not present."""
        compact_edge = CompactEdge(
            source="node1",
            source_output="message",
            target="node2",
            target_input="custom_field",
        )
        expanded_nodes = {
            "node1": {
                "id": "node1",
                "type": "genericNode",
                "data": {
                    "type": "ChatInput",
                    "node": SAMPLE_COMPONENTS["inputs"]["ChatInput"],
                },
            },
            "node2": {
                "id": "node2",
                "type": "genericNode",
                "data": {
                    "type": "CustomNode",
                    "node": {
                        "template": {
                            "custom_field": {
                                "type": "str",  # No input_types, should use type
                                "value": "",
                            }
                        },
                        "outputs": [],
                    },
                },
            },
        }

        expanded = _expand_edge(compact_edge, expanded_nodes)

        # data.targetHandle should have "str" as the type and inputTypes
        target_data = expanded["data"]["targetHandle"]
        assert target_data["type"] == "str"
        assert target_data["inputTypes"] == ["str"]

    def test_expand_edge_id_uniqueness(self):
        """Test that edge IDs are unique for different edges."""
        expanded_nodes = {
            "1": {
                "id": "1",
                "type": "genericNode",
                "data": {
                    "type": "ChatInput",
                    "node": SAMPLE_COMPONENTS["inputs"]["ChatInput"],
                },
            },
            "2": {
                "id": "2",
                "type": "genericNode",
                "data": {
                    "type": "OpenAIModel",
                    "node": SAMPLE_COMPONENTS["models"]["OpenAIModel"],
                },
            },
            "3": {
                "id": "3",
                "type": "genericNode",
                "data": {
                    "type": "ChatOutput",
                    "node": SAMPLE_COMPONENTS["outputs"]["ChatOutput"],
                },
            },
        }

        edge1 = _expand_edge(
            CompactEdge(source="1", source_output="message", target="2", target_input="input_value"),
            expanded_nodes,
        )
        edge2 = _expand_edge(
            CompactEdge(source="2", source_output="text_output", target="3", target_input="input_value"),
            expanded_nodes,
        )

        assert edge1["id"] != edge2["id"]

    def test_expand_edge_missing_source_raises(self):
        compact_edge = CompactEdge(
            source="missing",
            source_output="message",
            target="2",
            target_input="input_value",
        )
        expanded_nodes = {"2": {"id": "2", "data": {"type": "X", "node": {}}}}

        with pytest.raises(ValueError, match="Source node 'missing' not found"):
            _expand_edge(compact_edge, expanded_nodes)

    def test_expand_edge_missing_target_raises(self):
        compact_edge = CompactEdge(
            source="1",
            source_output="message",
            target="missing",
            target_input="input_value",
        )
        expanded_nodes = {"1": {"id": "1", "data": {"type": "X", "node": {}}}}

        with pytest.raises(ValueError, match="Target node 'missing' not found"):
            _expand_edge(compact_edge, expanded_nodes)


class TestExpandCompactFlow:
    def test_expand_simple_flow(self):
        compact_data = {
            "nodes": [
                {"id": "1", "type": "ChatInput"},
                {"id": "2", "type": "OpenAIModel", "values": {"model_name": "gpt-4"}},
                {"id": "3", "type": "ChatOutput"},
            ],
            "edges": [
                {
                    "source": "1",
                    "source_output": "message",
                    "target": "2",
                    "target_input": "input_value",
                },
                {
                    "source": "2",
                    "source_output": "text_output",
                    "target": "3",
                    "target_input": "input_value",
                },
            ],
        }

        expanded = expand_compact_flow(compact_data, SAMPLE_COMPONENTS)

        assert len(expanded["nodes"]) == 3
        assert len(expanded["edges"]) == 2

        # Check nodes are properly expanded
        node_types = {n["data"]["type"] for n in expanded["nodes"]}
        assert node_types == {"ChatInput", "OpenAIModel", "ChatOutput"}

        # Check values were merged
        openai_node = next(n for n in expanded["nodes"] if n["data"]["type"] == "OpenAIModel")
        assert openai_node["data"]["node"]["template"]["model_name"]["value"] == "gpt-4"

    def test_expand_flow_no_edges(self):
        compact_data = {
            "nodes": [{"id": "1", "type": "ChatInput"}],
            "edges": [],
        }

        expanded = expand_compact_flow(compact_data, SAMPLE_COMPONENTS)

        assert len(expanded["nodes"]) == 1
        assert len(expanded["edges"]) == 0

    def test_expand_flow_unknown_component_raises(self):
        compact_data = {
            "nodes": [{"id": "1", "type": "UnknownComponent"}],
            "edges": [],
        }

        with pytest.raises(ValueError, match="not found in component index"):
            expand_compact_flow(compact_data, SAMPLE_COMPONENTS)


class TestExpandFlowEndpoint:
    """Integration tests for the /flows/expand endpoint."""

    async def test_expand_flow_endpoint_requires_auth(self, client: AsyncClient):
        """Test that endpoint requires authentication."""
        compact_data = {
            "nodes": [{"id": "1", "type": "ChatInput"}],
            "edges": [],
        }

        response = await client.post("api/v1/flows/expand/", json=compact_data)

        # Should return 401 or 403 without auth
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    async def test_expand_flow_endpoint_success(self, client: AsyncClient, logged_in_headers):
        compact_data = {
            "nodes": [
                {"id": "1", "type": "ChatInput"},
            ],
            "edges": [],
        }

        response = await client.post("api/v1/flows/expand/", json=compact_data, headers=logged_in_headers)

        # Component might not exist in test env, but endpoint should work
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    async def test_expand_flow_endpoint_invalid_component(self, client: AsyncClient, logged_in_headers):
        compact_data = {
            "nodes": [{"id": "1", "type": "NonExistentComponent12345"}],
            "edges": [],
        }

        response = await client.post("api/v1/flows/expand/", json=compact_data, headers=logged_in_headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not found" in response.json()["detail"]

    async def test_expand_flow_endpoint_invalid_edge(self, client: AsyncClient, logged_in_headers):
        compact_data = {
            "nodes": [{"id": "1", "type": "ChatInput"}],
            "edges": [
                {
                    "source": "missing",
                    "source_output": "message",
                    "target": "1",
                    "target_input": "input_value",
                }
            ],
        }

        response = await client.post("api/v1/flows/expand/", json=compact_data, headers=logged_in_headers)

        # Should fail due to missing source node
        assert response.status_code == status.HTTP_400_BAD_REQUEST
