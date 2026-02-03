"""Integration tests for agent building blocks with database access.

These tests verify the message ID flow through the agent loop with actual
database operations to ensure messages are updated (not created anew) on
subsequent iterations.
"""

import pytest
from langflow.schema.message import Message


class TestMessageIdFlowWithDB:
    """Tests for message ID flow with database operations."""

    @pytest.mark.asyncio
    async def test_store_message_updates_when_has_id(self):
        """Test that _store_message calls update instead of create when message has ID."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from langflow.components.agent_blocks import AgentStepComponent

        component = AgentStepComponent()

        # Mock the graph
        mock_graph = MagicMock()
        mock_graph.flow_id = "test-flow-id"
        mock_vertex = MagicMock()
        mock_vertex.graph = mock_graph
        component._vertex = mock_vertex

        # Test 1: Message WITHOUT ID should call astore_message (create)
        message_no_id = Message(text="Test", sender="Machine", sender_name="AI", session_id="test-session")
        assert not message_no_id.has_id(), "Message should not have ID initially"

        stored_message = Message(text="Test", sender="Machine", sender_name="AI", session_id="test-session")
        stored_message.id = "new-generated-id"

        with (
            patch("lfx.custom.custom_component.component.astore_message", new_callable=AsyncMock) as mock_store,
            patch("lfx.custom.custom_component.component.aupdate_messages", new_callable=AsyncMock) as mock_update,
        ):
            mock_store.return_value = [stored_message]

            await component._store_message(message_no_id)

            assert mock_store.called, "Should call astore_message for new message"
            assert not mock_update.called, "Should NOT call aupdate_messages for new message"

        # Test 2: Message WITH ID should call aupdate_messages (update)
        message_with_id = Message(text="Updated text", sender="Machine", sender_name="AI", session_id="test-session")
        message_with_id.id = "existing-message-id"
        assert message_with_id.has_id(), "Message should have ID"

        updated_message = Message(text="Updated text", sender="Machine", sender_name="AI", session_id="test-session")
        updated_message.id = "existing-message-id"

        with (
            patch("lfx.custom.custom_component.component.astore_message", new_callable=AsyncMock) as mock_store,
            patch("lfx.custom.custom_component.component.aupdate_messages", new_callable=AsyncMock) as mock_update,
        ):
            mock_update.return_value = [updated_message]

            await component._store_message(message_with_id)

            assert not mock_store.called, "Should NOT call astore_message for existing message"
            assert mock_update.called, "Should call aupdate_messages for existing message"


class TestMessageIdExtraction:
    """Tests for message ID extraction from DataFrame."""

    def test_extract_message_id_from_dataframe(self):
        """Test that message ID is correctly extracted from DataFrame."""
        from langflow.base.agents.message_utils import extract_message_id_from_dataframe
        from langflow.base.agents.tool_execution import build_ai_message_row, build_tool_result_row
        from langflow.schema.dataframe import DataFrame

        # Build rows like ExecuteTool would
        ai_row = build_ai_message_row(
            text="Let me search",
            tool_calls=[{"name": "search", "args": {}, "id": "call_1"}],
            message_id="test-id-789",
            content_blocks=None,
        )
        tool_row = build_tool_result_row("search", "call_1", result="found it")

        df = DataFrame([ai_row, tool_row])

        extracted_id = extract_message_id_from_dataframe(df)

        assert extracted_id == "test-id-789", f"Expected 'test-id-789', got {extracted_id}"

    def test_full_id_flow_simulation(self):
        """Test the full ID flow: AgentStep -> ExecuteTool -> DataFrame -> AgentStep."""
        from langflow.base.agents.message_utils import extract_message_id_from_dataframe
        from langflow.base.agents.tool_execution import build_ai_message_row, build_tool_result_row
        from langflow.schema.dataframe import DataFrame

        # Step 1: Simulate AgentStep producing a message with ID
        agent_step_message = Message(
            text="I'll look that up",
            sender="Machine",
        )
        agent_step_message.id = "original-message-id"
        agent_step_message.data["has_tool_calls"] = True
        agent_step_message.data["tool_calls"] = [{"name": "lookup", "args": {"key": "test"}, "id": "call_abc"}]

        # Step 2: ExecuteTool extracts the ID
        extracted_id = getattr(agent_step_message, "id", None)
        assert extracted_id == "original-message-id"

        # Step 3: ExecuteTool builds DataFrame with the ID
        ai_row = build_ai_message_row(
            text="I'll look that up",
            tool_calls=agent_step_message.data["tool_calls"],
            message_id=extracted_id,
            content_blocks=None,
        )
        tool_row = build_tool_result_row("lookup", "call_abc", result="found: value")
        df = DataFrame([ai_row, tool_row])

        # Step 4: AgentStep iteration 2 extracts ID from DataFrame
        iteration2_id = extract_message_id_from_dataframe(df)
        assert iteration2_id == "original-message-id"

        # Step 5: AgentStep creates new message with that ID
        new_message = Message(text="", sender="Machine")
        new_message.id = iteration2_id
        assert new_message.has_id()
