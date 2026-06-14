"""Tests for ChatOutput upstream token usage accumulation in message_response()."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.input_output.chat_output import ChatOutput
from lfx.schema.message import Message
from lfx.schema.properties import Usage


def _make_graph_stub():
    """Return a minimal graph stub with required attributes."""
    return SimpleNamespace(session_id="test-session", flow_id=None, user_id=None)


def _make_vertex(*, accumulate_return=None):
    """Create a vertex mock with a proper graph attribute."""
    vertex = MagicMock()
    vertex.graph = _make_graph_stub()
    vertex._accumulate_upstream_token_usage.return_value = accumulate_return
    return vertex


def _make_chat_output(*, should_store_message=False, vertex=None):
    """Create a minimal ChatOutput instance with mocked dependencies.

    Uses __new__ to bypass __init__; sets required attributes manually.
    The `graph` property on CustomComponent reads self._vertex.graph,
    so vertex must carry a proper graph stub.
    """
    component = ChatOutput.__new__(ChatOutput)
    component.input_value = "hello"
    component.should_store_message = should_store_message
    component.sender = "Machine"
    component.sender_name = "AI"
    component.session_id = ""
    component.context_id = ""
    component.data_template = "{text}"
    component.clean_data = True
    component._vertex = vertex
    component._user_id = None
    component.message = MagicMock()
    component.status = None
    return component


class TestChatOutputTokenUsageAccumulation:
    """Tests for upstream token usage accumulation in message_response()."""

    @pytest.mark.asyncio
    async def test_sets_usage_on_message_when_vertex_returns_usage(self):
        # Arrange
        usage = Usage(input_tokens=100, output_tokens=50, total_tokens=150)
        vertex = _make_vertex(accumulate_return=usage)
        component = _make_chat_output(vertex=vertex)

        with (
            patch.object(component, "convert_to_string", return_value="hello"),
            patch.object(component, "get_properties_from_source_component", return_value=(None, None, None, None)),
            patch.object(component, "is_connected_to_chat_input", return_value=False),
            patch.object(component, "_build_source", return_value=MagicMock()),
        ):
            # Act
            result = await component.message_response()

        # Assert
        assert result.properties.usage == usage
        vertex._accumulate_upstream_token_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_set_usage_when_vertex_is_none(self):
        # Arrange — no vertex means graph property raises AttributeError, so
        # hasattr(self, "graph") returns False, and accumulation is skipped
        component = _make_chat_output(vertex=None)

        with (
            patch.object(component, "convert_to_string", return_value="hello"),
            patch.object(component, "get_properties_from_source_component", return_value=(None, None, None, None)),
            patch.object(component, "is_connected_to_chat_input", return_value=False),
            patch.object(component, "_build_source", return_value=MagicMock()),
        ):
            # Act
            result = await component.message_response()

        # Assert
        assert result.properties.usage is None

    @pytest.mark.asyncio
    async def test_does_not_set_usage_when_accumulation_returns_none(self):
        # Arrange
        vertex = _make_vertex(accumulate_return=None)
        component = _make_chat_output(vertex=vertex)

        with (
            patch.object(component, "convert_to_string", return_value="hello"),
            patch.object(component, "get_properties_from_source_component", return_value=(None, None, None, None)),
            patch.object(component, "is_connected_to_chat_input", return_value=False),
            patch.object(component, "_build_source", return_value=MagicMock()),
        ):
            # Act
            result = await component.message_response()

        # Assert
        assert result.properties.usage is None

    @pytest.mark.asyncio
    async def test_updates_stored_message_when_usage_and_stored(self):
        # Arrange
        usage = Usage(input_tokens=10, output_tokens=20, total_tokens=30)
        vertex = _make_vertex(accumulate_return=usage)

        component = _make_chat_output(should_store_message=True, vertex=vertex)
        component.session_id = "test-session"

        stored_message = Message(text="hello", id="stored-id")
        updated_message = Message(text="hello", id="stored-id")
        updated_message.properties.usage = usage

        with (
            patch.object(component, "convert_to_string", return_value="hello"),
            patch.object(component, "get_properties_from_source_component", return_value=(None, None, None, None)),
            patch.object(component, "is_connected_to_chat_input", return_value=False),
            patch.object(component, "_build_source", return_value=MagicMock()),
            patch.object(component, "send_message", new_callable=AsyncMock, return_value=stored_message),
            patch.object(
                component, "_update_stored_message", new_callable=AsyncMock, return_value=updated_message
            ) as mock_update,
            patch.object(component, "_send_message_event", new_callable=AsyncMock) as mock_send_event,
        ):
            # Act
            result = await component.message_response()

            # Assert (inside patch context while mocks are still active)
            assert result.properties.usage == usage
            mock_update.assert_called_once()
            mock_send_event.assert_called_once()
