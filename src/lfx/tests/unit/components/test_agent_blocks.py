"""Tests for agent building block components."""

from lfx.components.agent_blocks import (
    CallModelComponent,
    CheckDoneComponent,
    ExecuteToolComponent,
    ParseCallsComponent,
)
from lfx.schema.message import Message


class TestCallModelComponent:
    """Tests for CallModelComponent."""

    def test_component_instantiation(self):
        """Test that CallModelComponent can be instantiated."""
        comp = CallModelComponent()
        assert comp is not None
        assert comp.display_name == "Call Model"

    def test_has_expected_inputs(self):
        """Test that CallModelComponent has expected inputs."""
        comp = CallModelComponent()
        input_names = [i.name for i in comp.inputs]

        # Should have LLM inputs from mixin
        assert "provider" in input_names
        assert "model_name" in input_names
        assert "api_key" in input_names

        # Should have component-specific inputs
        assert "messages" in input_names
        assert "system_message" in input_names
        assert "tools" in input_names

    def test_has_expected_outputs(self):
        """Test that CallModelComponent has expected outputs."""
        comp = CallModelComponent()
        output_names = [o.name for o in comp.outputs]

        # ai_message fires when done (no tool calls)
        assert "ai_message" in output_names
        # tool_calls fires when model wants to call tools
        assert "tool_calls" in output_names

    def test_outputs_are_conditional(self):
        """Test that CallModel outputs route based on has_tool_calls."""
        comp = CallModelComponent()

        # Verify both outputs exist
        output_names = [o.name for o in comp.outputs]
        assert "ai_message" in output_names
        assert "tool_calls" in output_names

    def test_convert_messages_to_lc_format(self):
        """Test message conversion to LangChain format."""
        comp = CallModelComponent()

        messages = [
            Message(text="Hello", sender="User"),
            Message(text="Hi there!", sender="Machine"),
        ]

        lc_messages = comp._convert_to_lc_messages(messages)

        assert len(lc_messages) == 2
        assert lc_messages[0].content == "Hello"
        assert lc_messages[1].content == "Hi there!"


class TestCheckDoneComponent:
    """Tests for CheckDoneComponent."""

    def test_component_instantiation(self):
        """Test that CheckDoneComponent can be instantiated."""
        comp = CheckDoneComponent()
        assert comp is not None
        assert comp.display_name == "Check Done"

    def test_has_expected_inputs(self):
        """Test that CheckDoneComponent has expected inputs."""
        comp = CheckDoneComponent()
        input_names = [i.name for i in comp.inputs]

        assert "ai_message" in input_names
        assert "max_iterations" in input_names

    def test_has_expected_outputs(self):
        """Test that CheckDoneComponent has expected outputs."""
        comp = CheckDoneComponent()
        output_names = [o.name for o in comp.outputs]

        assert "done" in output_names
        assert "continue_output" in output_names

    def test_has_tool_calls_with_tool_calls(self):
        """Test _has_tool_calls returns True when tool_calls present."""
        comp = CheckDoneComponent()
        comp.ai_message = Message(
            text="Let me help",
            data={
                "has_tool_calls": True,
                "tool_calls": [{"name": "calculator", "args": {"x": 5}}],
            },
        )

        assert comp._has_tool_calls() is True

    def test_has_tool_calls_without_tool_calls(self):
        """Test _has_tool_calls returns False when no tool_calls."""
        comp = CheckDoneComponent()
        comp.ai_message = Message(text="Here is the answer", data={"has_tool_calls": False})

        assert comp._has_tool_calls() is False

    def test_has_tool_calls_with_none_message(self):
        """Test _has_tool_calls returns False when message is None."""
        comp = CheckDoneComponent()
        comp.ai_message = None

        assert comp._has_tool_calls() is False


class TestParseCallsComponent:
    """Tests for ParseCallsComponent."""

    def test_component_instantiation(self):
        """Test that ParseCallsComponent can be instantiated."""
        comp = ParseCallsComponent()
        assert comp is not None
        assert comp.display_name == "Parse Calls"

    def test_has_expected_inputs(self):
        """Test that ParseCallsComponent has expected inputs."""
        comp = ParseCallsComponent()
        input_names = [i.name for i in comp.inputs]

        assert "ai_message" in input_names

    def test_has_expected_outputs(self):
        """Test that ParseCallsComponent has expected outputs."""
        comp = ParseCallsComponent()
        output_names = [o.name for o in comp.outputs]

        assert "tool_calls" in output_names

    def test_parse_calls_extracts_all_tool_calls(self):
        """Test that parse_calls extracts all tool calls from message."""
        comp = ParseCallsComponent()
        comp.ai_message = Message(
            text="Let me calculate that",
            data={
                "tool_calls": [
                    {"name": "calculator", "args": {"expression": "2+2"}, "id": "call_123"},
                    {"name": "search", "args": {"query": "weather"}, "id": "call_456"},
                ],
            },
        )

        results = comp.parse_calls()

        # Returns list of Data objects with all tool calls
        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0].data["name"] == "calculator"
        assert results[0].data["args"] == {"expression": "2+2"}
        assert results[0].data["id"] == "call_123"
        assert results[1].data["name"] == "search"
        assert results[1].data["args"] == {"query": "weather"}
        assert results[1].data["id"] == "call_456"

    def test_parse_calls_with_no_tool_calls(self):
        """Test that parse_calls returns error Data when no tool_calls."""
        comp = ParseCallsComponent()
        comp.ai_message = Message(text="Done", data={})

        results = comp.parse_calls()

        assert isinstance(results, list)
        assert "error" in results[0].data

    def test_parse_calls_with_none_message(self):
        """Test that parse_calls returns error Data when message is None."""
        comp = ParseCallsComponent()
        comp.ai_message = None

        results = comp.parse_calls()

        assert isinstance(results, list)
        assert "error" in results[0].data


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

        assert "ai_message" in input_names
        assert "tools" in input_names

    def test_has_expected_outputs(self):
        """Test that ExecuteToolComponent has expected outputs."""
        comp = ExecuteToolComponent()
        output_names = [o.name for o in comp.outputs]

        # Output is now "messages" (DataFrame) not "tool_results"
        assert "messages" in output_names


class TestCallModelConditionalRouting:
    """Tests for CallModel's conditional output routing.

    Note: Full graph-based integration tests for conditional routing are in
    src/backend/tests/unit/components/agent_blocks/test_agent_blocks_integration.py
    """

    def test_call_model_has_two_outputs(self):
        """Test that CallModel has both ai_message and tool_calls outputs."""
        comp = CallModelComponent()
        output_names = [o.name for o in comp.outputs]

        assert "ai_message" in output_names
        assert "tool_calls" in output_names

    def test_outputs_are_grouped(self):
        """Test that both outputs have group_outputs=True for conditional routing."""
        comp = CallModelComponent()

        for output in comp.outputs:
            if output.name in ["ai_message", "tool_calls"]:
                assert output.group_outputs is True, f"{output.name} should have group_outputs=True"


class TestCallModelMessageConversion:
    """Tests for CallModel's message conversion from DataFrame."""

    def test_convert_dataframe_with_user_message(self):
        """Test converting DataFrame with user message to LangChain format."""
        from lfx.schema.dataframe import DataFrame

        comp = CallModelComponent()
        df = DataFrame([{"text": "Hello", "sender": "User"}])

        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 1
        assert lc_messages[0].content == "Hello"
        assert lc_messages[0].__class__.__name__ == "HumanMessage"

    def test_convert_dataframe_with_ai_message(self):
        """Test converting DataFrame with AI message to LangChain format."""
        from lfx.schema.dataframe import DataFrame

        comp = CallModelComponent()
        df = DataFrame([{"text": "I can help", "sender": "Machine"}])

        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 1
        assert lc_messages[0].content == "I can help"
        assert lc_messages[0].__class__.__name__ == "AIMessage"

    def test_convert_dataframe_with_tool_result(self):
        """Test converting DataFrame with tool result to LangChain format."""
        from lfx.schema.dataframe import DataFrame

        comp = CallModelComponent()
        df = DataFrame([{"text": "42", "is_tool_result": True, "tool_call_id": "call_123"}])

        lc_messages = comp._convert_to_lc_messages(df)

        assert len(lc_messages) == 1
        assert lc_messages[0].content == "42"
        assert lc_messages[0].__class__.__name__ == "ToolMessage"
        assert lc_messages[0].tool_call_id == "call_123"

    def test_convert_dataframe_with_ai_message_and_tool_calls(self):
        """Test converting DataFrame with AI message that has tool_calls."""
        from lfx.schema.dataframe import DataFrame

        comp = CallModelComponent()
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

        comp = CallModelComponent()
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
        call_model = CallModelComponent()
        check_done = CheckDoneComponent()
        parse_calls = ParseCallsComponent()
        execute_tool = ExecuteToolComponent()

        assert all(
            [
                call_model,
                check_done,
                parse_calls,
                execute_tool,
            ]
        )

    def test_message_flow_data_structure(self):
        """Test that message data structure is compatible across blocks."""
        # Create a message like CallModel would produce
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

        # CheckDone should be able to route it
        check_done = CheckDoneComponent()
        check_done.ai_message = ai_message
        assert check_done._has_tool_calls() is True

        # ParseCalls should be able to extract all tool calls
        parse_calls = ParseCallsComponent()
        parse_calls.ai_message = ai_message
        tool_calls = parse_calls.parse_calls()
        assert isinstance(tool_calls, list)
        assert len(tool_calls) == 2
        assert tool_calls[0].data["name"] == "calculator"
        assert tool_calls[1].data["name"] == "search"

    def test_while_loop_provides_dataframe_to_call_model(self):
        """Test that WhileLoop outputs a DataFrame that CallModel can process."""
        from lfx.components.flow_controls.while_loop import WhileLoopComponent
        from lfx.schema.dataframe import DataFrame

        # Setup WhileLoop with initial user message
        while_loop = WhileLoopComponent()
        while_loop.input_value = Message(text="What is 5+3?", sender="User")

        # Get output
        initial_df = while_loop.loop_output()

        # Verify it's a DataFrame that CallModel can use
        assert isinstance(initial_df, DataFrame)
        assert len(initial_df) == 1
        assert initial_df.iloc[0]["text"] == "What is 5+3?"

        # Verify CallModel can convert it to LangChain messages
        call_model = CallModelComponent()
        lc_messages = call_model._convert_to_lc_messages(initial_df)

        assert len(lc_messages) == 1
        assert lc_messages[0].__class__.__name__ == "HumanMessage"
        assert lc_messages[0].content == "What is 5+3?"
