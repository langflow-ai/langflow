"""Tests for agent building block components."""

import pytest
from lfx.components.agent_blocks import (
    AgentStepComponent,
    ExecuteToolComponent,
    ThinkToolComponent,
)
from lfx.schema.message import Message


class TestAgentStepComponent:
    """Tests for AgentStepComponent."""

    def test_component_instantiation(self):
        """Test that AgentStepComponent can be instantiated."""
        comp = AgentStepComponent()
        assert comp is not None
        assert comp.display_name == "Agent Step"

    def test_has_expected_inputs(self):
        """Test that AgentStepComponent has expected inputs."""
        comp = AgentStepComponent()
        input_names = [i.name for i in comp.inputs]

        # Should have ModelInput for model selection
        assert "model" in input_names
        assert "api_key" in input_names

        # Should have component-specific inputs
        assert "messages" in input_names
        assert "system_message" in input_names
        assert "tools" in input_names
        assert "temperature" in input_names

    def test_has_expected_outputs(self):
        """Test that AgentStepComponent has expected outputs."""
        comp = AgentStepComponent()
        output_names = [o.name for o in comp.outputs]

        # ai_message fires when done (no tool calls)
        assert "ai_message" in output_names
        # tool_calls fires when model wants to call tools
        assert "tool_calls" in output_names

    def test_outputs_are_conditional(self):
        """Test that AgentStep outputs route based on has_tool_calls."""
        comp = AgentStepComponent()

        # Verify both outputs exist
        output_names = [o.name for o in comp.outputs]
        assert "ai_message" in output_names
        assert "tool_calls" in output_names

    def test_convert_messages_to_lc_format(self):
        """Test message conversion to LangChain format."""
        comp = AgentStepComponent()

        messages = [
            Message(text="Hello", sender="User"),
            Message(text="Hi there!", sender="Machine"),
        ]

        lc_messages = comp._convert_to_lc_messages(messages)

        assert len(lc_messages) == 2
        assert lc_messages[0].content == "Hello"
        assert lc_messages[1].content == "Hi there!"


class TestExecuteToolComponent:
    """Tests for ExecuteToolComponent."""

    def test_component_instantiation(self):
        """Test that ExecuteToolComponent can be instantiated."""
        comp = ExecuteToolComponent()
        assert comp is not None
        assert comp.display_name == "Execute Tool"

    def test_has_expected_inputs(self):
        """Test that ExecuteToolComponent has expected inputs."""
        comp = ExecuteToolComponent()
        input_names = [i.name for i in comp.inputs]

        assert "tool_calls_message" in input_names
        assert "tools" in input_names

    def test_has_expected_outputs(self):
        """Test that ExecuteToolComponent has expected outputs."""
        comp = ExecuteToolComponent()
        output_names = [o.name for o in comp.outputs]

        # Output is now "messages" (DataFrame) not "tool_results"
        assert "messages" in output_names


class TestThinkToolComponent:
    """Tests for ThinkToolComponent."""

    def test_component_instantiation(self):
        """Test that ThinkToolComponent can be instantiated."""
        comp = ThinkToolComponent()
        assert comp is not None
        assert comp.display_name == "Think Tool"

    def test_build_tool(self):
        """Test that ThinkToolComponent can build a tool."""
        comp = ThinkToolComponent()
        tool = comp.build_tool()

        assert tool is not None
        assert tool.name == "think"


class TestAgentStepConditionalRouting:
    """Tests for AgentStep's conditional output routing.

    Note: Full graph-based integration tests for conditional routing are in
    src/backend/tests/unit/components/agent_blocks/test_agent_blocks_integration.py
    """

    def test_agent_step_has_two_outputs(self):
        """Test that AgentStep has both ai_message and tool_calls outputs."""
        comp = AgentStepComponent()
        output_names = [o.name for o in comp.outputs]

        assert "ai_message" in output_names
        assert "tool_calls" in output_names

    def test_outputs_are_grouped(self):
        """Test that both outputs have group_outputs=True for conditional routing."""
        comp = AgentStepComponent()

        for output in comp.outputs:
            if output.name in ["ai_message", "tool_calls"]:
                assert output.group_outputs is True, f"{output.name} should have group_outputs=True"


class TestAgentStepMessageConversion:
    """Tests for AgentStep's message conversion from DataFrame."""

    def test_convert_dataframe_with_user_message(self):
        """Test converting DataFrame with user message to LangChain format."""
        from lfx.schema.dataframe import DataFrame

        comp = AgentStepComponent()
        df = DataFrame([{"text": "Hello", "sender": "User"}])

        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 1
        assert lc_messages[0].content == "Hello"
        assert lc_messages[0].__class__.__name__ == "HumanMessage"

    def test_convert_dataframe_with_ai_message(self):
        """Test converting DataFrame with AI message to LangChain format."""
        from lfx.schema.dataframe import DataFrame

        comp = AgentStepComponent()
        df = DataFrame([{"text": "I can help", "sender": "Machine"}])

        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 1
        assert lc_messages[0].content == "I can help"
        assert lc_messages[0].__class__.__name__ == "AIMessage"

    def test_convert_dataframe_with_tool_result(self):
        """Test converting DataFrame with tool result to LangChain format."""
        from lfx.schema.dataframe import DataFrame

        comp = AgentStepComponent()
        df = DataFrame([{"text": "42", "is_tool_result": True, "tool_call_id": "call_123"}])

        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 1
        assert lc_messages[0].content == "42"
        assert lc_messages[0].__class__.__name__ == "ToolMessage"
        assert lc_messages[0].tool_call_id == "call_123"

    def test_convert_dataframe_with_ai_message_and_tool_calls(self):
        """Test converting DataFrame with AI message that has tool_calls."""
        from lfx.schema.dataframe import DataFrame

        comp = AgentStepComponent()
        df = DataFrame(
            [
                {
                    "text": "Let me calculate",
                    "sender": "Machine",
                    "tool_calls": [{"name": "calc", "args": {"x": 5}, "id": "call_1"}],
                }
            ]
        )

        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 1
        assert lc_messages[0].__class__.__name__ == "AIMessage"
        assert lc_messages[0].tool_calls == [{"name": "calc", "args": {"x": 5}, "id": "call_1"}]

    def test_convert_full_conversation_dataframe(self):
        """Test converting a full conversation DataFrame (like from FormatResult)."""
        from lfx.schema.dataframe import DataFrame

        comp = AgentStepComponent()
        df = DataFrame(
            [
                {"text": "What is 2+2?", "sender": "User"},
                {
                    "text": "Let me calculate",
                    "sender": "Machine",
                    "tool_calls": [{"name": "calc", "args": {}, "id": "call_1"}],
                },
                {"text": "4", "is_tool_result": True, "tool_call_id": "call_1"},
            ]
        )

        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 3
        assert lc_messages[0].__class__.__name__ == "HumanMessage"
        assert lc_messages[1].__class__.__name__ == "AIMessage"
        assert lc_messages[2].__class__.__name__ == "ToolMessage"


class TestMessageIdFlow:
    """Tests for message ID flow between AgentStep and ExecuteTool."""

    def test_execute_tool_extracts_message_id(self):
        """Test that ExecuteTool correctly extracts message ID from incoming message."""
        # Create a message with ID (simulating what AgentStep would produce after send_message)
        ai_message = Message(
            text="I'll search for that",
            sender="Machine",
            data={
                "id": "test-message-id-123",
                "has_tool_calls": True,
                "tool_calls": [{"name": "search", "args": {"q": "test"}, "id": "call_1"}],
            },
        )

        # Verify the ID is accessible via getattr (which __getattr__ proxies to data)
        extracted_id = getattr(ai_message, "id", None)

        assert extracted_id == "test-message-id-123", f"Expected 'test-message-id-123', got {extracted_id}"

    def test_build_ai_message_row_includes_id(self):
        """Test that build_ai_message_row includes message ID in output."""
        from lfx.base.agents.tool_execution import build_ai_message_row

        row = build_ai_message_row(
            text="Test response",
            tool_calls=[{"name": "test", "args": {}, "id": "call_1"}],
            message_id="test-id-456",
            content_blocks=None,
        )

        assert row["_agent_message_id"] == "test-id-456"

    def test_extract_message_id_from_dataframe(self):
        """Test that extract_message_id_from_dataframe finds the ID."""
        from lfx.base.agents.message_utils import extract_message_id_from_dataframe
        from lfx.base.agents.tool_execution import build_ai_message_row, build_tool_result_row
        from lfx.schema.dataframe import DataFrame

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

        assert extracted_id == "test-id-789"

    def test_full_id_flow_simulation(self):
        """Test the full ID flow: AgentStep -> ExecuteTool -> DataFrame -> AgentStep."""
        from lfx.base.agents.message_utils import extract_message_id_from_dataframe
        from lfx.base.agents.tool_execution import build_ai_message_row, build_tool_result_row
        from lfx.schema.dataframe import DataFrame

        # Step 1: Simulate AgentStep producing a message with ID (after send_message)
        agent_step_message = Message(
            text="I'll look that up",
            sender="Machine",
            data={
                "id": "original-message-id",
                "has_tool_calls": True,
                "tool_calls": [{"name": "lookup", "args": {"key": "test"}, "id": "call_abc"}],
            },
        )

        # Step 2: Simulate ExecuteTool extracting the ID
        extracted_id = getattr(agent_step_message, "id", None)
        assert extracted_id == "original-message-id", f"ExecuteTool should extract ID, got {extracted_id}"

        # Step 3: Simulate ExecuteTool building DataFrame with the ID
        ai_row = build_ai_message_row(
            text="I'll look that up",
            tool_calls=agent_step_message.data["tool_calls"],
            message_id=extracted_id,
            content_blocks=None,
        )
        tool_row = build_tool_result_row("lookup", "call_abc", result="found: value")
        df = DataFrame([ai_row, tool_row])

        # Step 4: Simulate AgentStep (iteration 2) extracting ID from DataFrame
        iteration2_id = extract_message_id_from_dataframe(df)
        assert iteration2_id == "original-message-id", f"AgentStep should find ID, got {iteration2_id}"

    def test_message_id_from_top_level_kwarg(self):
        """Test that Message created with id as top-level kwarg (like from DB) exposes id correctly.

        This simulates what _store_message does: Message.create(**message_table.model_dump())
        where message_table has id as a top-level field.
        """
        from uuid import uuid4

        # Simulate MessageTable.model_dump() output - id is a top-level field, not inside data
        test_uuid = uuid4()
        db_model_dump = {
            "id": test_uuid,
            "text": "Test message",
            "sender": "Machine",
            "sender_name": "AI",
            "session_id": "test-session",
            "timestamp": "2026-02-03 12:00:00 UTC",
            "flow_id": None,
            "files": [],
            "properties": {"state": "complete"},
            "category": "message",
            "content_blocks": [],
        }

        # Create Message like _store_message does
        message = Message(**db_model_dump)

        # The ID should be accessible via getattr (which uses __getattr__ -> data dict)
        extracted_id = getattr(message, "id", None)
        assert extracted_id == test_uuid, f"Expected {test_uuid}, got {extracted_id}"

    def test_message_id_setattr_and_hasattr(self):
        """Test setting message.id via setattr and checking via hasattr.

        This simulates what AgentStep does:
        1. Creates a Message without ID
        2. Sets message.id = existing_message_id
        3. astore_message checks hasattr(message, 'id') and message.id
        """
        # Create message without ID
        message = Message(text="Test", sender="Machine")

        # This is what AgentStep does when it has an existing_message_id
        test_id = "test-id-12345"
        message.id = test_id

        # This is what astore_message checks
        has_id = hasattr(message, "id") and message.id

        assert message.data.get("id") == test_id, "ID should be in data dict"
        assert message.id == test_id, "message.id should return the ID"
        assert has_id, "astore_message condition should be True"


class TestSubgraphStreamingContext:
    """Tests for streaming context propagation from parent graph to subgraph."""

    def test_is_connected_to_chat_output_checks_parent_graph(self):
        """Test that is_connected_to_chat_output checks parent graph when in subgraph.

        When a component is in a subgraph, it should check the parent graph's
        connections if the subgraph doesn't have a direct ChatOutput connection.
        """
        from unittest.mock import MagicMock, patch

        # Create a mock component with a mock graph (subgraph)
        component = AgentStepComponent()

        # Create mock subgraph that doesn't have ChatOutput
        mock_subgraph = MagicMock()
        mock_subgraph.get_vertex_neighbors = MagicMock(return_value=[])

        # Create mock parent graph that IS connected to ChatOutput
        mock_parent_graph = MagicMock()
        mock_parent_vertex = MagicMock()
        mock_parent_graph.get_vertex = MagicMock(return_value=mock_parent_vertex)
        # Return a mock ChatOutput neighbor
        mock_chat_output = MagicMock()
        mock_chat_output.id = "ChatOutput-123"
        mock_parent_graph.get_vertex_neighbors = MagicMock(return_value=[mock_chat_output])

        # Set up the parent graph reference
        mock_subgraph._parent_graph = mock_parent_graph

        # Mock vertex - set its graph to the subgraph
        # (component.graph property returns self._vertex.graph)
        mock_vertex = MagicMock()
        mock_vertex.id = "AgentStep-456"
        mock_vertex.graph = mock_subgraph

        # Set the vertex on the component
        component._vertex = mock_vertex

        # Mock has_chat_output to return True for parent's neighbors
        # Patch at the source location since it's lazily imported
        with patch("lfx.graph.utils.has_chat_output") as mock_has_chat_output:
            # First call (subgraph) returns False, second call (parent) returns True
            mock_has_chat_output.side_effect = [False, True]

            result = component.is_connected_to_chat_output()

            assert result is True
            # Should have been called twice - once for subgraph, once for parent
            assert mock_has_chat_output.call_count == 2

    def test_is_connected_to_chat_output_no_parent_graph(self):
        """Test that is_connected_to_chat_output returns False when no parent and no connection."""
        from unittest.mock import MagicMock, patch

        component = AgentStepComponent()

        # Create mock graph without parent
        mock_graph = MagicMock()
        mock_graph.get_vertex_neighbors = MagicMock(return_value=[])
        mock_graph._parent_graph = None  # No parent graph

        # Mock vertex - set its graph to the mock graph
        mock_vertex = MagicMock()
        mock_vertex.graph = mock_graph

        # Set the vertex on the component
        component._vertex = mock_vertex

        # Patch at the source location since it's lazily imported
        with patch("lfx.graph.utils.has_chat_output", return_value=False):
            result = component.is_connected_to_chat_output()
            assert result is False


class TestWhileLoopAccumulation:
    """Tests for WhileLoop DataFrame accumulation preserving _agent_message_id."""

    def test_accumulation_preserves_agent_message_id(self):
        """Test that WhileLoop accumulation preserves _agent_message_id through iterations."""
        from lfx.base.agents.message_utils import extract_message_id_from_dataframe
        from lfx.base.agents.tool_execution import build_ai_message_row, build_tool_result_row
        from lfx.schema.dataframe import DataFrame

        # Simulate iteration 1 initial state (user message from ChatInput)
        initial_state = DataFrame([{"text": "What time is it?", "sender": "User"}])

        # Simulate ExecuteTool output from iteration 1 (has _agent_message_id)
        ai_row = build_ai_message_row(
            text="Let me check the time",
            tool_calls=[{"name": "get_time", "args": {}, "id": "call_1"}],
            message_id="first-message-id",
            content_blocks=None,
        )
        tool_row = build_tool_result_row("get_time", "call_1", result="14:30 UTC")
        iteration1_output = DataFrame([ai_row, tool_row])

        # Simulate WhileLoop accumulation (lines 292-293)
        new_rows = iteration1_output.to_dict(orient="records")
        accumulated_state = initial_state.add_rows(new_rows)

        # Check what AgentStep iteration 2 would receive
        extracted_id = extract_message_id_from_dataframe(accumulated_state)

        assert extracted_id == "first-message-id", f"ID should be preserved, got {extracted_id}"

    def test_dataframe_add_rows_preserves_columns(self):
        """Test that DataFrame.add_rows preserves all columns including _agent_message_id."""
        from lfx.schema.dataframe import DataFrame

        # Create initial DataFrame without _agent_message_id
        initial = DataFrame([{"text": "Hello", "sender": "User"}])

        # Add rows with _agent_message_id
        new_rows = [
            {"text": "Response", "sender": "Machine", "_agent_message_id": "test-id"},
            {"text": "Tool result", "sender": "Tool", "_agent_message_id": None},
        ]
        accumulated = initial.add_rows(new_rows)

        assert "_agent_message_id" in accumulated.columns, "Column should exist"
        # First row (user message) should have NaN for _agent_message_id
        # Second row (AI message) should have the ID
        assert accumulated.iloc[1]["_agent_message_id"] == "test-id"


class TestAgentBlocksIntegration:
    """Integration tests for agent building blocks working together.

    Note: Full graph integration tests are in
    src/backend/tests/unit/components/agent_blocks/test_agent_blocks_integration.py
    """

    def test_all_blocks_can_be_instantiated(self):
        """Test that all blocks can be instantiated together."""
        agent_step = AgentStepComponent()
        execute_tool = ExecuteToolComponent()
        think_tool = ThinkToolComponent()

        assert all(
            [
                agent_step,
                execute_tool,
                think_tool,
            ]
        )

    def test_message_flow_data_structure(self):
        """Test that message data structure is compatible across blocks."""
        # Create a message like AgentStep would produce
        ai_message = Message(
            text="I'll calculate that for you",
            sender="Machine",
            data={
                "has_tool_calls": True,
                "tool_calls": [
                    {"name": "calculator", "args": {"x": 5}, "id": "call_1"},
                    {"name": "search", "args": {"query": "test"}, "id": "call_2"},
                ],
            },
        )

        # ExecuteTool should be able to receive it
        execute_tool = ExecuteToolComponent()
        execute_tool.tool_calls_message = ai_message
        # Just verify it can be set without error
        assert execute_tool.tool_calls_message == ai_message

    def test_while_loop_provides_dataframe_to_agent_step(self):
        """Test that WhileLoop builds a DataFrame that AgentStep can process."""
        from lfx.components.flow_controls.while_loop import WhileLoopComponent
        from lfx.schema.dataframe import DataFrame

        # Setup WhileLoop with initial user message
        while_loop = WhileLoopComponent()
        while_loop.input_value = Message(text="What is 5+3?", sender="User")
        while_loop.initial_state = None

        # Get initial state (this is what loop body receives)
        initial_df = while_loop._build_initial_state()

        # Verify it's a DataFrame that AgentStep can use
        assert isinstance(initial_df, DataFrame)
        assert len(initial_df) == 1
        assert initial_df.iloc[0]["text"] == "What is 5+3?"

        # Verify AgentStep can convert it to LangChain messages
        agent_step = AgentStepComponent()
        lc_messages = agent_step._convert_to_lc_messages(initial_df)

        assert len(lc_messages) == 1
        assert lc_messages[0].__class__.__name__ == "HumanMessage"
        assert lc_messages[0].content == "What is 5+3?"


class TestStoreMessageUpdateVsCreate:
    """Tests for _store_message update vs create behavior."""

    @pytest.mark.asyncio
    async def test_store_message_creates_new_when_no_id(self):
        """Test that _store_message calls astore_message when message has no ID."""
        from unittest.mock import AsyncMock, MagicMock, patch

        component = AgentStepComponent()

        # Mock the graph
        mock_graph = MagicMock()
        mock_graph.flow_id = "test-flow-id"
        mock_vertex = MagicMock()
        mock_vertex.graph = mock_graph
        component._vertex = mock_vertex

        # Create message WITHOUT an ID
        message = Message(text="Test", sender="Machine", sender_name="AI", session_id="test-session")
        assert not message.has_id(), "Message should not have ID initially"

        # Mock astore_message to return a message with ID
        stored_message = Message(text="Test", sender="Machine", sender_name="AI", session_id="test-session")
        stored_message.id = "new-generated-id"

        with (
            patch("lfx.custom.custom_component.component.astore_message", new_callable=AsyncMock) as mock_store,
            patch("lfx.custom.custom_component.component.aupdate_messages", new_callable=AsyncMock) as mock_update,
        ):
            mock_store.return_value = [stored_message]

            result = await component._store_message(message)

            # Should call astore_message, not aupdate_messages
            mock_store.assert_called_once()
            mock_update.assert_not_called()
            assert result.id == "new-generated-id"

    @pytest.mark.asyncio
    async def test_store_message_updates_when_has_id(self):
        """Test that _store_message calls aupdate_messages when message has an ID."""
        from unittest.mock import AsyncMock, MagicMock, patch

        component = AgentStepComponent()

        # Mock the graph
        mock_graph = MagicMock()
        mock_graph.flow_id = "test-flow-id"
        mock_vertex = MagicMock()
        mock_vertex.graph = mock_graph
        component._vertex = mock_vertex

        # Create message WITH an ID (simulating reuse from previous iteration)
        message = Message(text="Updated text", sender="Machine", sender_name="AI", session_id="test-session")
        message.id = "existing-message-id"
        assert message.has_id(), "Message should have ID"

        # Mock aupdate_messages to return updated message
        updated_message = Message(text="Updated text", sender="Machine", sender_name="AI", session_id="test-session")
        updated_message.id = "existing-message-id"

        with (
            patch("lfx.custom.custom_component.component.astore_message", new_callable=AsyncMock) as mock_store,
            patch("lfx.custom.custom_component.component.aupdate_messages", new_callable=AsyncMock) as mock_update,
        ):
            mock_update.return_value = [updated_message]

            result = await component._store_message(message)

            # Should call aupdate_messages, not astore_message
            mock_update.assert_called_once()
            mock_store.assert_not_called()
            assert result.id == "existing-message-id"


class TestMessageHasId:
    """Tests for Message.has_id() behavior."""

    def test_message_has_id_returns_false_when_no_id(self):
        """Test that has_id returns False for messages without ID."""
        message = Message(text="Test", sender="User")
        assert not message.has_id()

    def test_message_has_id_returns_true_when_id_set(self):
        """Test that has_id returns True when ID is set via attribute."""
        message = Message(text="Test", sender="User")
        message.id = "test-id-123"
        assert message.has_id()

    def test_message_has_id_returns_true_when_id_in_data(self):
        """Test that has_id returns True when ID is in data dict."""
        message = Message(text="Test", sender="User", data={"id": "test-id-456"})
        assert message.has_id()

    def test_message_has_id_returns_false_for_none_id(self):
        """Test that has_id returns False when ID is explicitly None."""
        message = Message(text="Test", sender="User", data={"id": None})
        assert not message.has_id()


class TestParentGraphDelegation:
    """Additional tests for parent graph delegation in is_connected_to_chat_output."""

    def test_returns_true_immediately_when_current_graph_has_chat_output(self):
        """Test is_connected_to_chat_output returns True without checking parent."""
        from unittest.mock import MagicMock, patch

        component = AgentStepComponent()

        # Create mock subgraph that IS connected to ChatOutput
        mock_subgraph = MagicMock()
        mock_subgraph.get_vertex_neighbors = MagicMock(return_value=[MagicMock()])

        # Parent graph should NOT be checked
        mock_parent_graph = MagicMock()
        mock_subgraph._parent_graph = mock_parent_graph

        mock_vertex = MagicMock()
        mock_vertex.id = "AgentStep-123"
        mock_vertex.graph = mock_subgraph
        component._vertex = mock_vertex

        with patch("lfx.graph.utils.has_chat_output") as mock_has_chat_output:
            # First call returns True (current graph has ChatOutput)
            mock_has_chat_output.return_value = True

            result = component.is_connected_to_chat_output()

            assert result is True
            # Should only be called once (for current graph), parent not checked
            assert mock_has_chat_output.call_count == 1

    def test_returns_false_when_parent_vertex_not_found(self):
        """Test that is_connected_to_chat_output returns False when parent vertex doesn't exist."""
        from unittest.mock import MagicMock, patch

        component = AgentStepComponent()

        # Subgraph without ChatOutput
        mock_subgraph = MagicMock()
        mock_subgraph.get_vertex_neighbors = MagicMock(return_value=[])

        # Parent graph exists but can't find the vertex
        mock_parent_graph = MagicMock()
        mock_parent_graph.get_vertex = MagicMock(return_value=None)  # Vertex not found
        mock_subgraph._parent_graph = mock_parent_graph

        mock_vertex = MagicMock()
        mock_vertex.id = "AgentStep-123"
        mock_vertex.graph = mock_subgraph
        component._vertex = mock_vertex

        with patch("lfx.graph.utils.has_chat_output", return_value=False):
            result = component.is_connected_to_chat_output()

            assert result is False
            # Parent's get_vertex was called
            mock_parent_graph.get_vertex.assert_called_once_with("AgentStep-123")


class TestMultiIterationIdFlow:
    """Tests simulating multiple loop iterations with ID preservation."""

    def test_three_iteration_id_flow(self):
        """Test that message ID is preserved through 3 loop iterations."""
        from lfx.base.agents.message_utils import extract_message_id_from_dataframe
        from lfx.base.agents.tool_execution import build_ai_message_row, build_tool_result_row
        from lfx.schema.dataframe import DataFrame

        original_message_id = "original-msg-id-abc123"

        # Iteration 1: User message -> AgentStep creates message with ID
        iteration1_input = DataFrame([{"text": "Search for cats", "sender": "User"}])

        # AgentStep output (would have ID after send_message)
        ai_row_1 = build_ai_message_row(
            text="I'll search for that",
            tool_calls=[{"name": "search", "args": {"q": "cats"}, "id": "call_1"}],
            message_id=original_message_id,
            content_blocks=None,
        )
        tool_row_1 = build_tool_result_row("search", "call_1", result="Found 10 results about cats")

        # ExecuteTool returns DataFrame with AI message + tool results
        iteration1_output = DataFrame([ai_row_1, tool_row_1])

        # WhileLoop accumulates
        accumulated_1 = iteration1_input.add_rows(iteration1_output.to_dict(orient="records"))

        # Iteration 2: AgentStep extracts ID from accumulated state
        extracted_id_iter2 = extract_message_id_from_dataframe(accumulated_1)
        assert extracted_id_iter2 == original_message_id, f"Iteration 2 should find ID, got {extracted_id_iter2}"

        # AgentStep iteration 2 would reuse this ID
        ai_row_2 = build_ai_message_row(
            text="Let me search for more",
            tool_calls=[{"name": "search", "args": {"q": "cute cats"}, "id": "call_2"}],
            message_id=extracted_id_iter2,  # Reusing the same ID
            content_blocks=None,
        )
        tool_row_2 = build_tool_result_row("search", "call_2", result="Found 5 more results")
        iteration2_output = DataFrame([ai_row_2, tool_row_2])

        # WhileLoop accumulates again
        accumulated_2 = accumulated_1.add_rows(iteration2_output.to_dict(orient="records"))

        # Iteration 3: AgentStep extracts ID again
        extracted_id_iter3 = extract_message_id_from_dataframe(accumulated_2)
        assert extracted_id_iter3 == original_message_id, f"Iteration 3 should find ID, got {extracted_id_iter3}"

        # Final verification: ID is consistent across all extractions
        assert extracted_id_iter2 == extracted_id_iter3 == original_message_id

    def test_id_preserved_even_with_multiple_ai_rows(self):
        """Test that the first AI message ID is found even when there are multiple AI rows."""
        from lfx.base.agents.message_utils import extract_message_id_from_dataframe
        from lfx.base.agents.tool_execution import build_ai_message_row, build_tool_result_row
        from lfx.schema.dataframe import DataFrame

        # Build a DataFrame with multiple AI message rows (from multiple iterations)
        rows = [
            {"text": "User question", "sender": "User"},
            build_ai_message_row("First AI response", [{"name": "t1", "args": {}, "id": "c1"}], "first-id", None),
            build_tool_result_row("t1", "c1", result="result1"),
            build_ai_message_row("Second AI response", [{"name": "t2", "args": {}, "id": "c2"}], "first-id", None),
            build_tool_result_row("t2", "c2", result="result2"),
        ]

        df = DataFrame(rows)

        # Should find the first non-null _agent_message_id
        extracted_id = extract_message_id_from_dataframe(df)
        assert extracted_id == "first-id"


class TestWhileLoopParentGraphSetup:
    """Tests for WhileLoop setting up parent graph reference."""

    def test_while_loop_has_parent_graph_attribute_setup_code(self):
        """Verify WhileLoop's execute_loop sets _parent_graph on subgraph."""
        import inspect

        from lfx.components.flow_controls.while_loop import WhileLoopComponent

        # Get the source code of execute_loop
        source = inspect.getsource(WhileLoopComponent.execute_loop)

        # Verify the parent graph setup is in the code
        assert "_parent_graph" in source, "execute_loop should set _parent_graph on subgraph"
        assert "iteration_subgraph._parent_graph = self.graph" in source, (
            "Should assign self.graph to subgraph._parent_graph"
        )


class TestMessageIdFlowDebug:
    """Debug tests for tracing message ID flow through the agent loop."""

    def test_message_id_extracted_from_message_data(self):
        """Test that message ID is correctly extracted from Message.data after send_message simulation."""
        # Simulate what happens after send_message stores a message
        # The stored message has id in message.data["id"]
        stored_message = Message(
            text="I'll search for that",
            sender="Machine",
            sender_name="AI",
        )
        # Simulate what astore_message does - sets the ID in the data dict
        stored_message.id = "stored-msg-id-123"

        # Now simulate AgentStep adding tool_calls to the result
        stored_message.data["has_tool_calls"] = True
        stored_message.data["tool_calls"] = [{"name": "search", "args": {}, "id": "call_1"}]

        # This message goes to ExecuteTool
        # ExecuteTool extracts the ID like this:
        extracted_id = getattr(stored_message, "id", None)

        assert extracted_id == "stored-msg-id-123", f"Expected 'stored-msg-id-123', got {extracted_id}"

        # Now ExecuteTool builds a DataFrame with _agent_message_id
        from lfx.base.agents.tool_execution import build_ai_message_row, build_tool_result_row

        ai_row = build_ai_message_row(
            text="I'll search for that",
            tool_calls=[{"name": "search", "args": {}, "id": "call_1"}],
            message_id=extracted_id,
            content_blocks=None,
        )
        tool_row = build_tool_result_row("search", "call_1", result="found it")

        # WhileLoop accumulates into DataFrame
        from lfx.schema.dataframe import DataFrame

        accumulated_df = DataFrame([{"text": "user query", "sender": "User"}])
        accumulated_df = accumulated_df.add_rows([ai_row, tool_row])

        # AgentStep extracts ID from DataFrame
        from lfx.base.agents.message_utils import extract_message_id_from_dataframe

        extracted_id_2 = extract_message_id_from_dataframe(accumulated_df)

        assert extracted_id_2 == "stored-msg-id-123", f"Expected 'stored-msg-id-123', got {extracted_id_2}"

        # Now AgentStep creates a new message with that ID
        new_message = Message(
            text="",  # Will be filled by streaming
            sender="Machine",
            sender_name="AI",
        )
        new_message.id = extracted_id_2

        assert new_message.has_id(), "new_message should have ID"


class TestGraphStreamToPlayground:
    """Tests for graph._stream_to_playground flag bypassing _should_skip_message."""

    def test_should_skip_message_returns_false_when_graph_has_stream_to_playground(self):
        """Test that _should_skip_message returns False when graph._stream_to_playground is True.

        This simulates the WhileLoop setting _stream_to_playground on the subgraph
        when it's connected to ChatOutput. Components inside the subgraph should
        NOT skip messages in this case.
        """
        from unittest.mock import MagicMock

        component = AgentStepComponent()

        # Create mock graph WITH _stream_to_playground flag set
        mock_graph = MagicMock()
        mock_graph._stream_to_playground = True
        mock_graph.get_vertex_neighbors = MagicMock(return_value=[])

        # Mock vertex
        mock_vertex = MagicMock()
        mock_vertex.is_output = False
        mock_vertex.is_input = False
        mock_vertex.graph = mock_graph
        component._vertex = mock_vertex

        # Create a test message
        message = Message(text="Test", sender="Machine")

        # _should_skip_message should return False because graph._stream_to_playground is True
        result = component._should_skip_message(message)
        assert result is False, "Should NOT skip message when graph._stream_to_playground is True"

    def test_should_skip_message_returns_true_without_stream_to_playground(self):
        """Test that _should_skip_message returns True when graph._stream_to_playground is False/missing.

        This confirms that messages ARE skipped when the flag is not set
        (and component is not connected to ChatOutput).
        """
        from unittest.mock import MagicMock, patch

        component = AgentStepComponent()

        # Create mock graph WITHOUT _stream_to_playground flag
        mock_graph = MagicMock()
        mock_graph._stream_to_playground = False
        mock_graph.get_vertex_neighbors = MagicMock(return_value=[])
        mock_graph._parent_graph = None

        # Mock vertex - NOT an input or output
        mock_vertex = MagicMock()
        mock_vertex.is_output = False
        mock_vertex.is_input = False
        mock_vertex.graph = mock_graph
        component._vertex = mock_vertex

        # Create a test message
        message = Message(text="Test", sender="Machine")

        # Patch has_chat_output to return False
        with patch("lfx.graph.utils.has_chat_output", return_value=False):
            result = component._should_skip_message(message)
            assert result is True, "Should skip message when graph._stream_to_playground is False"

    def test_while_loop_sets_stream_to_playground_on_subgraph(self):
        """Verify that WhileLoop's execute_loop sets _stream_to_playground on subgraph."""
        import inspect

        from lfx.components.flow_controls.while_loop import WhileLoopComponent

        # Get the source code of execute_loop
        source = inspect.getsource(WhileLoopComponent.execute_loop)

        # Verify the _stream_to_playground setup is in the code
        assert "_stream_to_playground" in source, "execute_loop should set _stream_to_playground on subgraph"
        assert "iteration_subgraph._stream_to_playground" in source, "Should assign _stream_to_playground to subgraph"
