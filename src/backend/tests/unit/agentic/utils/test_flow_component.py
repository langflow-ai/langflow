"""Tests for flow component operations utilities.

Tests get_component_details, get_component_field_value,
update_component_field_value, and list_component_fields.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from langflow.agentic.utils.flow_component import (
    get_component_details,
    get_component_field_value,
    list_component_fields,
    update_component_field_value,
)

MODULE = "langflow.agentic.utils.flow_component"

FLOW_ID = str(uuid4())
USER_ID = str(uuid4())


def _mock_logger():
    """Create a mock async logger."""
    mock = MagicMock()
    mock.aerror = AsyncMock()
    mock.ainfo = AsyncMock()
    return mock


def _make_flow(*, has_data=True, name="TestFlow", user_id=None):
    """Create a mock flow object."""
    flow = MagicMock()
    flow.id = UUID(FLOW_ID)
    flow.name = name
    flow.user_id = UUID(user_id or USER_ID)
    flow.data = (
        {
            "nodes": [
                {
                    "id": "comp-1",
                    "data": {
                        "node": {
                            "type": "ChatInput",
                            "display_name": "Chat Input",
                            "description": "A chat input component",
                            "template": {
                                "input_value": {
                                    "value": "hello",
                                    "field_type": "str",
                                    "display_name": "Input Value",
                                    "required": True,
                                    "advanced": False,
                                    "show": True,
                                },
                                "sender_name": {
                                    "value": "User",
                                    "field_type": "str",
                                    "display_name": "Sender Name",
                                    "required": False,
                                    "advanced": True,
                                    "show": True,
                                },
                            },
                            "outputs": [{"name": "message"}],
                        },
                    },
                }
            ],
        }
        if has_data
        else None
    )
    return flow


def _make_vertex():
    """Create a mock vertex (graph node)."""
    vertex = MagicMock()
    vertex.id = "comp-1"
    vertex.edges = []
    vertex.to_data.return_value = _make_flow().data["nodes"][0]
    return vertex


def _make_graph(vertex=None):
    """Create a mock graph with a vertex."""
    graph = MagicMock()
    v = vertex or _make_vertex()
    graph.get_vertex.return_value = v
    graph.vertices = [v]
    graph.edges = []
    return graph


class TestGetComponentDetails:
    """Tests for get_component_details."""

    @pytest.mark.asyncio
    async def test_should_return_component_data(self):
        """Should return component details including type, display_name, template."""
        flow = _make_flow()
        graph = _make_graph()

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.Graph.from_payload", return_value=graph),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_component_details("test-flow", "comp-1")

        assert result["component_id"] == "comp-1"
        assert result["component_type"] == "ChatInput"
        assert result["display_name"] == "Chat Input"
        assert result["flow_id"] == FLOW_ID

    @pytest.mark.asyncio
    async def test_should_return_error_when_flow_not_found(self):
        """Should return error dict when flow is None."""
        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_component_details("missing-flow", "comp-1")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_should_return_error_when_flow_has_no_data(self):
        """Should return error when flow.data is None."""
        flow = _make_flow(has_data=False)

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_component_details("test-flow", "comp-1")

        assert "error" in result
        assert "no data" in result["error"]

    @pytest.mark.asyncio
    async def test_should_return_error_when_component_not_found(self):
        """Should return error when vertex doesn't exist in graph."""
        flow = _make_flow()
        graph = MagicMock()
        graph.get_vertex.side_effect = ValueError("not found")

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.Graph.from_payload", return_value=graph),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_component_details("test-flow", "missing-comp")

        assert "error" in result
        assert "not found" in result["error"]


class TestGetComponentFieldValue:
    """Tests for get_component_field_value."""

    @pytest.mark.asyncio
    async def test_should_return_field_config(self):
        """Should return field value and metadata."""
        flow = _make_flow()
        graph = _make_graph()

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.Graph.from_payload", return_value=graph),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_component_field_value("test-flow", "comp-1", "input_value")

        assert result["field_name"] == "input_value"
        assert result["value"] == "hello"
        assert result["field_type"] == "str"

    @pytest.mark.asyncio
    async def test_should_return_error_for_missing_field(self):
        """Should return error with available_fields when field doesn't exist."""
        flow = _make_flow()
        graph = _make_graph()

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.Graph.from_payload", return_value=graph),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_component_field_value("test-flow", "comp-1", "nonexistent_field")

        assert "error" in result
        assert "available_fields" in result


class TestUpdateComponentFieldValue:
    """Tests for update_component_field_value."""

    @pytest.mark.asyncio
    async def test_should_persist_new_value(self):
        """Should update field in DB and return success=True."""
        flow = _make_flow()
        db_flow = MagicMock()
        db_flow.user_id = UUID(USER_ID)
        db_flow.data = flow.data.copy()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=db_flow)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        @asynccontextmanager
        async def mock_scope():
            yield mock_session

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.session_scope", mock_scope),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await update_component_field_value(
                "test-flow",
                "comp-1",
                "input_value",
                "new_value",
                USER_ID,
            )

        assert result["success"] is True
        assert result["old_value"] == "hello"
        assert result["new_value"] == "new_value"

    @pytest.mark.asyncio
    async def test_should_return_error_for_missing_component(self):
        """Should return success=False when component not found."""
        flow = _make_flow()

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await update_component_field_value(
                "test-flow",
                "nonexistent-comp",
                "field",
                "val",
                USER_ID,
            )

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_should_check_user_permission(self):
        """Should return error when user_id doesn't match flow owner."""
        flow = _make_flow()
        db_flow = MagicMock()
        db_flow.user_id = UUID(USER_ID)  # original owner

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=db_flow)

        @asynccontextmanager
        async def mock_scope():
            yield mock_session

        different_user = str(uuid4())

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.session_scope", mock_scope),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await update_component_field_value(
                "test-flow",
                "comp-1",
                "input_value",
                "hack",
                different_user,
            )

        assert result["success"] is False
        assert "permission" in result["error"].lower()


class TestListComponentFields:
    """Tests for list_component_fields."""

    @pytest.mark.asyncio
    async def test_should_return_all_fields(self):
        """Should return fields_info with value, type, required, etc."""
        flow = _make_flow()
        graph = _make_graph()

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.Graph.from_payload", return_value=graph),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await list_component_fields("test-flow", "comp-1")

        assert "fields" in result
        assert result["field_count"] == 2
        assert "input_value" in result["fields"]
        assert "sender_name" in result["fields"]
        assert result["fields"]["input_value"]["value"] == "hello"
        assert result["fields"]["sender_name"]["advanced"] is True

    @pytest.mark.asyncio
    async def test_should_return_error_when_flow_not_found(self):
        """Should return error dict for nonexistent flow."""
        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await list_component_fields("missing-flow", "comp-1")

        assert "error" in result
