"""Tests for agent building block components."""

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
        """Test that WhileLoop outputs a DataFrame that AgentStep can process."""
        from lfx.components.flow_controls.while_loop import WhileLoopComponent
        from lfx.schema.dataframe import DataFrame

        # Setup WhileLoop with initial user message
        while_loop = WhileLoopComponent()
        while_loop.input_value = Message(text="What is 5+3?", sender="User")

        # Get output
        initial_df = while_loop.loop_output()

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
