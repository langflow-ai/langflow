"""Tests that MCP tools emit flow events after mutations."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.post_event = AsyncMock()
    client.get = AsyncMock()
    client.patch = AsyncMock()
    client.post = AsyncMock()
    return client


@pytest.fixture
def mock_registry():
    return {
        "ChatInput": {
            "display_name": "Chat Input",
            "template": {},
            "output_types": ["Message"],
            "outputs": [{"name": "message", "types": ["Message"]}],
        },
    }


@pytest.fixture
def mock_flow():
    return {
        "id": "flow-123",
        "name": "Test Flow",
        "data": {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
    }


def _patch_server(mock_client, mock_registry, mock_flow):
    """Return a context manager that patches all server helpers."""
    from contextlib import contextmanager
    from unittest.mock import patch as _patch

    @contextmanager
    def ctx():
        with (
            _patch("lfx.mcp.server._get_client", return_value=mock_client),
            _patch("lfx.mcp.server._get_registry", new_callable=AsyncMock, return_value=mock_registry),
            _patch("lfx.mcp.server._get_flow", new_callable=AsyncMock, return_value=mock_flow),
            _patch("lfx.mcp.server._patch_flow", new_callable=AsyncMock, return_value=mock_flow),
        ):
            yield

    return ctx()


class TestAddComponentEmitsEvent:
    async def test_emits_component_added_event(self, mock_client, mock_registry, mock_flow):
        from lfx.mcp.server import add_component

        add_result = {"id": "ChatInput-abc", "display_name": "Chat Input"}
        with (
            _patch_server(mock_client, mock_registry, mock_flow),
            patch("lfx.mcp.server.fb_add_component", return_value=add_result),
            patch("lfx.mcp.server.layout_flow"),
        ):
            await add_component("flow-123", "ChatInput")

        mock_client.post_event.assert_called_once_with("flow-123", "component_added", "Added ChatInput")


class TestRemoveComponentEmitsEvent:
    async def test_emits_component_removed_event(self, mock_client, mock_registry, mock_flow):
        from lfx.mcp.server import remove_component

        with (
            _patch_server(mock_client, mock_registry, mock_flow),
            patch("lfx.mcp.server.fb_remove_component"),
            patch("lfx.mcp.server.layout_flow"),
        ):
            await remove_component("flow-123", "ChatInput-abc")

        mock_client.post_event.assert_called_once_with("flow-123", "component_removed", "Removed ChatInput-abc")


class TestConfigureComponentEmitsEvent:
    async def test_emits_component_configured_event(self, mock_client, mock_registry, mock_flow):
        from lfx.mcp.server import configure_component

        mock_flow["data"]["nodes"] = [
            {
                "id": "node-1",
                "data": {
                    "id": "ChatInput-abc",
                    "node": {
                        "template": {
                            "input_value": {"value": "", "type": "str"},
                        },
                    },
                },
            },
        ]

        with (
            _patch_server(mock_client, mock_registry, mock_flow),
            patch("lfx.mcp.server.fb_configure"),
            patch("lfx.mcp.server.needs_server_update", return_value=False),
        ):
            await configure_component("flow-123", "ChatInput-abc", {"input_value": "hello"})

        mock_client.post_event.assert_called_once_with("flow-123", "component_configured", "Configured ChatInput-abc")


class TestConnectComponentsEmitsEvent:
    async def test_emits_connection_added_event(self, mock_client, mock_registry, mock_flow):
        from lfx.mcp.server import connect_components

        with (
            _patch_server(mock_client, mock_registry, mock_flow),
            patch("lfx.mcp.server.fb_add_connection"),
            patch("lfx.mcp.server.layout_flow"),
        ):
            await connect_components("flow-123", "A-1", "message", "B-1", "input_value")

        mock_client.post_event.assert_called_once_with("flow-123", "connection_added", "Connected A-1 to B-1")


class TestDisconnectComponentsEmitsEvent:
    async def test_emits_connection_removed_event(self, mock_client, mock_registry, mock_flow):
        from lfx.mcp.server import disconnect_components

        with (
            _patch_server(mock_client, mock_registry, mock_flow),
            patch("lfx.mcp.server.fb_remove_connection", return_value=1),
            patch("lfx.mcp.server.layout_flow"),
        ):
            await disconnect_components("flow-123", "A-1", "B-1")

        mock_client.post_event.assert_called_once_with("flow-123", "connection_removed", "Disconnected A-1 from B-1")


class TestNotifyDone:
    async def test_emits_flow_settled_event(self, mock_client):
        from lfx.mcp.server import notify_done

        with patch("lfx.mcp.server._get_client", return_value=mock_client):
            result = await notify_done("flow-123", "Built a RAG pipeline")

        mock_client.post_event.assert_called_once_with("flow-123", "flow_settled", "Built a RAG pipeline")
        assert result == {"status": "ok", "flow_id": "flow-123"}

    async def test_emits_empty_summary_when_none(self, mock_client):
        from lfx.mcp.server import notify_done

        with patch("lfx.mcp.server._get_client", return_value=mock_client):
            await notify_done("flow-123")

        mock_client.post_event.assert_called_once_with("flow-123", "flow_settled", "")
