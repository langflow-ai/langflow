"""Tests that MCP tools emit flow events after mutations.

Each mutating tool should call post_event with the correct flow_id and
event type after a successful PATCH. These tests verify the event is
emitted -- the exact summary string is not asserted since it's a
human-readable detail that may change.
"""

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


def _node(component_id: str, *, frozen: bool = False) -> dict:
    """Build a minimal flow node for tests that need one."""
    return {
        "id": "node-1",
        "data": {
            "id": component_id,
            "node": {
                "frozen": frozen,
                "template": {"input_value": {"value": "", "type": "str"}},
            },
        },
    }


# ---------------------------------------------------------------------------
# Parameterized test: every mutating tool emits an event with correct type
# ---------------------------------------------------------------------------


async def _call_add_component(flow_id, _flow):
    from lfx.mcp.server import add_component

    with (
        patch("lfx.mcp.server.fb_add_component", return_value={"id": "X-1", "display_name": "X"}),
        patch("lfx.mcp.server.layout_flow"),
    ):
        await add_component(flow_id, "ChatInput")


async def _call_remove_component(flow_id, _flow):
    from lfx.mcp.server import remove_component

    with patch("lfx.mcp.server.fb_remove_component"), patch("lfx.mcp.server.layout_flow"):
        await remove_component(flow_id, "X-1")


async def _call_configure_component(flow_id, flow):
    from lfx.mcp.server import configure_component

    flow["data"]["nodes"] = [_node("X-1")]
    with patch("lfx.mcp.server.fb_configure"), patch("lfx.mcp.server.needs_server_update", return_value=False):
        await configure_component(flow_id, "X-1", {"input_value": "hello"})


async def _call_connect_components(flow_id, _flow):
    from lfx.mcp.server import connect_components

    with patch("lfx.mcp.server.fb_add_connection"), patch("lfx.mcp.server.layout_flow"):
        await connect_components(flow_id, "A-1", "message", "B-1", "input_value")


async def _call_disconnect_components(flow_id, _flow):
    from lfx.mcp.server import disconnect_components

    with patch("lfx.mcp.server.fb_remove_connection", return_value=1), patch("lfx.mcp.server.layout_flow"):
        await disconnect_components(flow_id, "A-1", "B-1")


async def _call_freeze_component(flow_id, flow):
    from lfx.mcp.server import freeze_component

    flow["data"]["nodes"] = [_node("X-1", frozen=False)]
    await freeze_component(flow_id, "X-1")


async def _call_unfreeze_component(flow_id, flow):
    from lfx.mcp.server import unfreeze_component

    flow["data"]["nodes"] = [_node("X-1", frozen=True)]
    await unfreeze_component(flow_id, "X-1")


async def _call_layout_flow_tool(flow_id, _flow):
    from lfx.mcp.server import layout_flow_tool

    with patch("lfx.mcp.server.layout_flow"):
        await layout_flow_tool(flow_id)


async def _call_update_flow_from_spec(flow_id, flow):
    from lfx.mcp.server import update_flow_from_spec

    parsed = {"name": "T", "description": "", "nodes": [{"id": "A", "type": "ChatInput"}], "edges": [], "config": {}}
    with (
        patch("lfx.mcp.server.parse_flow_spec", return_value=parsed),
        patch("lfx.mcp.server.validate_spec_references"),
        patch("lfx.mcp.server.empty_flow", return_value=flow),
        patch("lfx.mcp.server.fb_add_component", return_value={"id": "X-1"}),
        patch("lfx.mcp.server.layout_flow"),
        patch("lfx.mcp.server.fb_spec_summary", return_value="A: ChatInput"),
    ):
        await update_flow_from_spec(flow_id, "nodes:\n  A: ChatInput")


TOOL_CASES = [
    ("add_component", _call_add_component, "component_added"),
    ("remove_component", _call_remove_component, "component_removed"),
    ("configure_component", _call_configure_component, "component_configured"),
    ("connect_components", _call_connect_components, "connection_added"),
    ("disconnect_components", _call_disconnect_components, "connection_removed"),
    ("freeze_component", _call_freeze_component, "component_configured"),
    ("unfreeze_component", _call_unfreeze_component, "component_configured"),
    ("layout_flow_tool", _call_layout_flow_tool, "flow_updated"),
    ("update_flow_from_spec", _call_update_flow_from_spec, "flow_updated"),
]


@pytest.mark.parametrize(("tool_name", "call_fn", "expected_event_type"), TOOL_CASES, ids=[c[0] for c in TOOL_CASES])
async def test_tool_emits_event(tool_name, call_fn, expected_event_type, mock_client, mock_registry, mock_flow):
    """Every mutating tool should emit an event with the correct flow_id and type."""
    flow_id = "flow-123"

    with _patch_server(mock_client, mock_registry, mock_flow):
        await call_fn(flow_id, mock_flow)

    mock_client.post_event.assert_called_once()
    call_args = mock_client.post_event.call_args
    assert call_args[0][0] == flow_id, f"{tool_name} should emit event for the correct flow_id"
    assert call_args[0][1] == expected_event_type, f"{tool_name} should emit '{expected_event_type}'"
    assert isinstance(call_args[0][2], str), f"{tool_name} summary should be a string"


# ---------------------------------------------------------------------------
# Distinct behavior: create_flow_from_spec emits flow_settled (not just a
# mutation event) because it signals the end of a batch operation.
# ---------------------------------------------------------------------------


class TestCreateFlowFromSpecEmitsSettled:
    async def test_emits_flow_settled_after_batch(self, mock_client, mock_registry):
        from lfx.mcp.server import create_flow_from_spec

        parsed = {
            "name": "T",
            "description": "",
            "nodes": [{"id": "A", "type": "ChatInput"}],
            "edges": [],
            "config": {},
        }
        created = {"id": "flow-new", "name": "T", "description": ""}

        with (
            patch("lfx.mcp.server._get_client", return_value=mock_client),
            patch("lfx.mcp.server._get_registry", new_callable=AsyncMock, return_value=mock_registry),
            patch("lfx.mcp.server.parse_flow_spec", return_value=parsed),
            patch("lfx.mcp.server.validate_spec_references"),
            patch("lfx.mcp.server.create_flow", new_callable=AsyncMock, return_value=created),
            patch("lfx.mcp.server.add_component", new_callable=AsyncMock, return_value={"id": "X-1"}),
            patch("lfx.mcp.server.build_flow", new_callable=AsyncMock),
            patch("lfx.mcp.server.get_flow_info", new_callable=AsyncMock, return_value={"id": "flow-new"}),
        ):
            await create_flow_from_spec("nodes:\n  A: ChatInput")

        # The last post_event call should be flow_settled on the new flow
        last_call = mock_client.post_event.call_args
        assert last_call[0][0] == "flow-new"
        assert last_call[0][1] == "flow_settled"


# ---------------------------------------------------------------------------
# notify_done: distinct behavior (explicit settle signal, returns result)
# ---------------------------------------------------------------------------


class TestNotifyDone:
    async def test_emits_flow_settled_and_returns_status(self, mock_client):
        from lfx.mcp.server import notify_done

        with patch("lfx.mcp.server._get_client", return_value=mock_client):
            result = await notify_done("flow-123", "Built a RAG pipeline")

        mock_client.post_event.assert_called_once()
        assert mock_client.post_event.call_args[0][1] == "flow_settled"
        assert result == {"status": "ok", "flow_id": "flow-123"}

    async def test_summary_defaults_to_empty(self, mock_client):
        from lfx.mcp.server import notify_done

        with patch("lfx.mcp.server._get_client", return_value=mock_client):
            await notify_done("flow-123")

        assert mock_client.post_event.call_args[0][2] == ""
