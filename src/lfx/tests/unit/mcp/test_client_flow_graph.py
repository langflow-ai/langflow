"""Tests for LangflowClient.list_flow_components / list_flow_edges."""

from unittest.mock import AsyncMock, patch

import pytest
from lfx.mcp.client import LangflowClient


@pytest.fixture
def client():
    return LangflowClient(server_url="http://localhost:7860", api_key="test-key")  # pragma: allowlist secret


class TestListFlowComponents:
    async def test_calls_components_endpoint(self, client):
        payload = [{"id": "ChatInput-1", "type": "ChatInput", "inputs": [], "outputs": []}]
        with patch.object(client, "get", new_callable=AsyncMock, return_value=payload) as mock_get:
            result = await client.list_flow_components("flow-123")

            mock_get.assert_called_once_with("/flows/flow-123/components")
            assert result == payload

    async def test_propagates_runtime_error(self, client):
        with (
            patch.object(client, "get", new_callable=AsyncMock, side_effect=RuntimeError("404")),
            pytest.raises(RuntimeError, match="404"),
        ):
            await client.list_flow_components("missing")


class TestListFlowEdges:
    async def test_calls_edges_endpoint(self, client):
        payload = [
            {
                "id": "edge-1",
                "source": "ChatInput-1",
                "target": "Prompt-1",
                "source_output": "message",
                "target_input": "input_value",
                "source_types": ["Message"],
                "target_types": ["Message"],
            }
        ]
        with patch.object(client, "get", new_callable=AsyncMock, return_value=payload) as mock_get:
            result = await client.list_flow_edges("flow-123")

            mock_get.assert_called_once_with("/flows/flow-123/edges")
            assert result == payload

    async def test_propagates_runtime_error(self, client):
        with (
            patch.object(client, "get", new_callable=AsyncMock, side_effect=RuntimeError("404")),
            pytest.raises(RuntimeError, match="404"),
        ):
            await client.list_flow_edges("missing")


class TestAddFlowComponent:
    async def test_minimal_payload(self, client):
        payload = {"id": "ChatInput-x1y2z", "type": "ChatInput", "inputs": [], "outputs": []}
        with patch.object(client, "post", new_callable=AsyncMock, return_value=payload) as mock_post:
            result = await client.add_flow_component("flow-123", "ChatInput")

            mock_post.assert_called_once_with(
                "/flows/flow-123/components",
                json_data={"type": "ChatInput"},
            )
            assert result == payload

    async def test_with_id_and_position(self, client):
        with patch.object(client, "post", new_callable=AsyncMock, return_value={}) as mock_post:
            await client.add_flow_component(
                "flow-123",
                "OpenAIModel",
                component_id="OpenAIModel-fixed",
                position={"x": 100.0, "y": 200.0},
            )

            mock_post.assert_called_once_with(
                "/flows/flow-123/components",
                json_data={
                    "type": "OpenAIModel",
                    "component_id": "OpenAIModel-fixed",
                    "position": {"x": 100.0, "y": 200.0},
                },
            )


class TestAddFlowEdge:
    async def test_sends_all_handle_fields(self, client):
        payload = {
            "id": "reactflow__edge-...",
            "source": "ChatInput-1",
            "target": "Prompt-1",
            "source_output": "message",
            "target_input": "input_value",
            "source_types": ["Message"],
            "target_types": ["Message"],
        }
        with patch.object(client, "post", new_callable=AsyncMock, return_value=payload) as mock_post:
            result = await client.add_flow_edge(
                "flow-123",
                source="ChatInput-1",
                source_output="message",
                target="Prompt-1",
                target_input="input_value",
            )

            mock_post.assert_called_once_with(
                "/flows/flow-123/edges",
                json_data={
                    "source": "ChatInput-1",
                    "source_output": "message",
                    "target": "Prompt-1",
                    "target_input": "input_value",
                },
            )
            assert result == payload

    async def test_propagates_400_on_type_mismatch(self, client):
        with (
            patch.object(client, "post", new_callable=AsyncMock, side_effect=RuntimeError("400")),
            pytest.raises(RuntimeError, match="400"),
        ):
            await client.add_flow_edge(
                "flow-123",
                source="X",
                source_output="out",
                target="Y",
                target_input="in",
            )
