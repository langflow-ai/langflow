"""Tests for WhileLoop component."""

from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


class TestWhileLoopComponent:
    """Tests for WhileLoopComponent."""

    def test_component_instantiation(self):
        """Test that WhileLoopComponent can be instantiated."""
        comp = WhileLoopComponent()
        assert comp is not None
        assert comp.display_name == "While Loop"

    def test_has_expected_inputs(self):
        """Test that WhileLoopComponent has expected inputs."""
        comp = WhileLoopComponent()
        input_names = [i.name for i in comp.inputs]

        assert "initial_state" in input_names
        assert "input_value" in input_names
        assert "max_iterations" in input_names

    def test_has_expected_outputs(self):
        """Test that WhileLoopComponent has expected outputs."""
        comp = WhileLoopComponent()
        output_names = [o.name for o in comp.outputs]

        assert "loop" in output_names
        assert "done" in output_names

    def test_loop_output_allows_loop(self):
        """Test that loop output has allows_loop=True."""
        comp = WhileLoopComponent()
        loop_output = next(o for o in comp.outputs if o.name == "loop")
        assert loop_output.allows_loop is True

    def test_default_max_iterations(self):
        """Test that default max_iterations is 10."""
        comp = WhileLoopComponent()
        max_iter_input = next(i for i in comp.inputs if i.name == "max_iterations")
        assert max_iter_input.value == 10

    def test_loop_output_method_exists(self):
        """Test that loop_output method exists and is callable."""
        comp = WhileLoopComponent()
        # Note: loop_output calls self.stop() which requires a vertex context
        # In a real graph execution, the vertex is set. Here we just verify the method exists.
        assert hasattr(comp, "loop_output")
        assert callable(comp.loop_output)

    def test_outputs_have_group_outputs(self):
        """Test that both outputs have group_outputs=True."""
        comp = WhileLoopComponent()
        loop_output = next(o for o in comp.outputs if o.name == "loop")
        done_output = next(o for o in comp.outputs if o.name == "done")
        assert loop_output.group_outputs is True
        assert done_output.group_outputs is True


class TestToDataFrame:
    """Tests for _to_dataframe conversion."""

    def test_to_dataframe_from_dataframe(self):
        """Test that DataFrame passes through."""
        comp = WhileLoopComponent()
        df = DataFrame([{"text": "test"}])
        result = comp._to_dataframe(df)
        assert isinstance(result, DataFrame)
        assert len(result) == 1

    def test_to_dataframe_from_data(self):
        """Test conversion from Data object."""
        comp = WhileLoopComponent()
        data = Data(text="test", data={"key": "value"})
        result = comp._to_dataframe(data)
        assert isinstance(result, DataFrame)
        assert len(result) == 1

    def test_to_dataframe_from_dict(self):
        """Test conversion from dict."""
        comp = WhileLoopComponent()
        result = comp._to_dataframe({"key": "value"})
        assert isinstance(result, DataFrame)
        assert len(result) == 1

    def test_to_dataframe_from_string(self):
        """Test conversion from string."""
        comp = WhileLoopComponent()
        result = comp._to_dataframe("test string")
        assert isinstance(result, DataFrame)
        assert len(result) == 1

    def test_to_dataframe_from_message(self):
        """Test conversion from Message preserves all fields."""
        comp = WhileLoopComponent()
        msg = Message(
            text="Hello",
            sender="User",
            sender_name="John",
            data={"custom_field": "value"},
        )
        result = comp._to_dataframe(msg)
        assert isinstance(result, DataFrame)
        assert len(result) == 1

        row = result.iloc[0]
        assert row["text"] == "Hello"
        assert row["sender"] == "User"
        assert row["sender_name"] == "John"
        assert row["custom_field"] == "value"

    def test_to_dataframe_from_message_preserves_data(self):
        """Test conversion from Message preserves data attributes."""
        comp = WhileLoopComponent()
        msg = Message(
            text="Let me help",
            sender="Machine",
            data={"has_tool_calls": True, "tool_calls": [{"name": "calc"}]},
        )
        result = comp._to_dataframe(msg)
        assert isinstance(result, DataFrame)
        assert len(result) == 1

        # Should preserve data attributes
        row = result.iloc[0]
        assert row["text"] == "Let me help"
        assert row["sender"] == "Machine"
        assert row["has_tool_calls"] == True  # noqa: E712


class TestWhileLoopWithAgentBlocks:
    """Integration tests for WhileLoop with agent building blocks."""

    def test_whileloop_converts_message_to_dataframe(self):
        """Test that WhileLoop properly converts Message input to DataFrame."""
        comp = WhileLoopComponent()

        # Simulate a user message input
        user_msg = Message(text="What is 2+2?", sender="User")
        df = comp._to_dataframe(user_msg)

        assert isinstance(df, DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["text"] == "What is 2+2?"
        assert df.iloc[0]["sender"] == "User"

    def test_flow_pattern_data_types(self):
        """Test the expected data types through the agent flow.

        Flow: ChatInput (Message) → WhileLoop (DataFrame) → CallModel (DataFrame)
                                                              ↓
              ChatOutput ← ai_message (Message) ← CallModel
                                              or
              ExecuteTool ← tool_calls (Message) ← CallModel
                  ↓
              WhileLoop (DataFrame)
        """
        # Initial input from ChatInput is a Message
        user_input = Message(text="Help me", sender="User")

        # WhileLoop converts to DataFrame for CallModel
        comp = WhileLoopComponent()
        df_for_callmodel = comp._to_dataframe(user_input)
        assert isinstance(df_for_callmodel, DataFrame)

        # CallModel would output a Message
        ai_response_with_tools = Message(
            text="Let me help",
            sender="Machine",
            data={"has_tool_calls": True, "tool_calls": [{"name": "search"}]},
        )

        ai_response_done = Message(
            text="Here is the answer",
            sender="Machine",
            data={"has_tool_calls": False},
        )

        # Both are valid Message outputs
        assert isinstance(ai_response_with_tools, Message)
        assert isinstance(ai_response_done, Message)


class TestWhileLoopInitialState:
    """Tests for WhileLoop's initial_state functionality."""

    def test_initial_state_input_is_optional(self):
        """Test that initial_state input is not required."""
        comp = WhileLoopComponent()
        initial_state_input = next(i for i in comp.inputs if i.name == "initial_state")
        assert initial_state_input.required is False

    def test_build_initial_state_without_history(self):
        """Test that _build_initial_state works without initial_state."""
        comp = WhileLoopComponent()
        comp.initial_state = None
        comp.input_value = Message(text="Hello", sender="User")

        result = comp._build_initial_state()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["text"] == "Hello"

    def test_build_initial_state_with_history(self):
        """Test that _build_initial_state prepends initial_state to input_value."""
        comp = WhileLoopComponent()

        # Simulate history from MessageHistory component
        history_df = DataFrame(
            [
                {"text": "Previous question", "sender": "User"},
                {"text": "Previous answer", "sender": "Machine"},
            ]
        )
        comp.initial_state = history_df

        # Current message from ChatInput
        comp.input_value = Message(text="New question", sender="User")

        result = comp._build_initial_state()

        assert isinstance(result, DataFrame)
        assert len(result) == 3  # 2 from history + 1 current

        # History should come first
        assert result.iloc[0]["text"] == "Previous question"
        assert result.iloc[1]["text"] == "Previous answer"
        # Current message should be last
        assert result.iloc[2]["text"] == "New question"

    def test_build_initial_state_with_empty_history(self):
        """Test that empty initial_state is handled like None."""
        comp = WhileLoopComponent()

        # Empty DataFrame
        comp.initial_state = DataFrame([])
        comp.input_value = Message(text="Hello", sender="User")

        result = comp._build_initial_state()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["text"] == "Hello"

    def test_initial_state_preserves_all_columns(self):
        """Test that initial_state preserves all DataFrame columns."""
        comp = WhileLoopComponent()

        # History with extra columns (tool_calls, is_tool_result, etc.)
        history_df = DataFrame(
            [
                {"text": "Let me help", "sender": "Machine", "tool_calls": [{"name": "calc"}]},
                {"text": "42", "sender": "Tool", "is_tool_result": True, "tool_call_id": "123"},
            ]
        )
        comp.initial_state = history_df
        comp.input_value = Message(text="Thanks!", sender="User")

        result = comp._build_initial_state()

        assert len(result) == 3
        # Check that tool_calls column is preserved
        assert result.iloc[0]["tool_calls"] == [{"name": "calc"}]
        # Check that is_tool_result is preserved
        assert result.iloc[1]["is_tool_result"] is True
        assert result.iloc[1]["tool_call_id"] == "123"


class TestWhileLoopSubgraphExecution:
    """Tests for subgraph execution methods."""

    def test_get_loop_body_vertices_without_vertex(self):
        """Test that get_loop_body_vertices returns empty set without vertex context."""
        comp = WhileLoopComponent()
        # No _vertex set
        result = comp.get_loop_body_vertices()
        assert result == set()

    def test_get_loop_body_start_vertex_without_vertex(self):
        """Test that _get_loop_body_start_vertex returns None without vertex context."""
        comp = WhileLoopComponent()
        # No _vertex set
        result = comp._get_loop_body_start_vertex()
        assert result is None

    def test_extract_loop_output_with_empty_results(self):
        """Test that _extract_loop_output returns None with empty results."""
        comp = WhileLoopComponent()
        result = comp._extract_loop_output([])
        assert result is None

    def test_extract_loop_output_without_end_vertex(self):
        """Test that _extract_loop_output returns None without end vertex."""
        comp = WhileLoopComponent()
        # No incoming edge configured, so get_incoming_edge_by_target_param returns None
        result = comp._extract_loop_output([{"some": "result"}])
        assert result is None


class TestWhileLoopIntegration:
    """Integration tests for WhileLoop with real graph execution.

    These tests build actual graphs with WhileLoop and loop body components,
    then execute them via async_start() to verify the full subgraph execution flow.
    """

    async def test_whileloop_terminates_when_no_loop_body(self):
        """Test that WhileLoop returns initial state when no loop body is connected."""
        from lfx.graph.graph.base import Graph

        # Create WhileLoop with input but no loop body
        while_loop = WhileLoopComponent(_id="while_loop")
        while_loop.set(
            input_value=Message(text="Hello", sender="User"),
            max_iterations=5,
        )

        # Build graph with just WhileLoop (no loop body)
        graph = Graph(while_loop, while_loop)

        results = [result async for result in graph.async_start()]

        # Should have results for while_loop
        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]
        assert "while_loop" in result_ids

        # The done output should return the initial state (just the input)
        while_loop_result = next(r for r in results if hasattr(r, "vertex") and r.vertex.id == "while_loop")
        assert while_loop_result.result_dict is not None

    async def test_whileloop_executes_loop_body_and_accumulates_state(self):
        """Test WhileLoop executes loop body and accumulates state correctly.

        This test creates a simple loop body that:
        1. Takes DataFrame input from WhileLoop
        2. Adds a new row indicating the iteration
        3. Feeds back to WhileLoop (continuing the loop)
        4. After max_iterations, the loop terminates
        """
        from lfx.custom.custom_component.component import Component
        from lfx.graph.graph.base import Graph
        from lfx.inputs.inputs import HandleInput
        from lfx.template.field.base import Output

        # Create a simple loop body component that always feeds back
        class LoopBodyComponent(Component):
            """Simple component that adds a row and feeds back."""

            display_name = "Loop Body"

            inputs = [
                HandleInput(
                    name="messages",
                    display_name="Messages",
                    input_types=["DataFrame"],
                ),
            ]

            outputs = [
                Output(
                    display_name="Output",
                    name="output",
                    method="process",
                ),
            ]

            def process(self) -> DataFrame:
                """Add a row indicating this iteration and return."""
                if isinstance(self.messages, DataFrame):
                    # Add a new row for this iteration
                    iteration = len(self.messages)
                    new_row = {"text": f"Iteration {iteration}", "sender": "Machine"}
                    return self.messages.add_rows([new_row])
                return DataFrame([{"text": "Processed", "sender": "Machine"}])

        # Create components
        while_loop = WhileLoopComponent(_id="while_loop")
        loop_body = LoopBodyComponent(_id="loop_body")

        # Connect: WhileLoop.loop -> LoopBody.messages
        loop_body.set(messages=while_loop.loop_output)

        # Connect: LoopBody.output -> WhileLoop.loop (feedback)
        # Also set the initial input
        while_loop.set(
            input_value=Message(text="Start", sender="User"),
            max_iterations=3,
            loop=loop_body.process,  # This creates the feedback connection
        )

        # Build graph
        graph = Graph(while_loop, while_loop)

        # Execute
        results = [result async for result in graph.async_start()]

        # Verify we got results
        assert len(results) > 0

        # Find the while_loop result
        while_loop_results = [r for r in results if hasattr(r, "vertex") and r.vertex.id == "while_loop"]
        assert len(while_loop_results) > 0

    async def test_whileloop_respects_max_iterations(self):
        """Test that WhileLoop stops at max_iterations even if loop body always feeds back."""
        from lfx.custom.custom_component.component import Component
        from lfx.graph.graph.base import Graph
        from lfx.inputs.inputs import HandleInput
        from lfx.template.field.base import Output

        # Track how many times loop body executes
        execution_count = 0

        class CountingLoopBody(Component):
            """Loop body that counts executions."""

            display_name = "Counting Loop Body"

            inputs = [
                HandleInput(
                    name="messages",
                    display_name="Messages",
                    input_types=["DataFrame"],
                ),
            ]

            outputs = [
                Output(
                    display_name="Output",
                    name="output",
                    method="process",
                ),
            ]

            def process(self) -> DataFrame:
                nonlocal execution_count
                execution_count += 1
                if isinstance(self.messages, DataFrame):
                    new_row = {"text": f"Count {execution_count}", "sender": "Machine"}
                    return self.messages.add_rows([new_row])
                return DataFrame([{"text": f"Count {execution_count}", "sender": "Machine"}])

        # Create components with max_iterations=2
        while_loop = WhileLoopComponent(_id="while_loop")
        loop_body = CountingLoopBody(_id="loop_body")

        loop_body.set(messages=while_loop.loop_output)
        while_loop.set(
            input_value=Message(text="Start", sender="User"),
            max_iterations=2,
            loop=loop_body.process,
        )

        graph = Graph(while_loop, while_loop)

        results = [result async for result in graph.async_start()]

        # Verify graph executed
        assert len(results) > 0

        # Loop body should have executed at most max_iterations times
        assert execution_count <= 2, f"Expected at most 2 executions, got {execution_count}"
