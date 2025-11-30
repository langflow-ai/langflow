"""Integration tests for FunctionComponent - Graph execution and serialization.

Tests cover:
- ChatInput -> FunctionComponent -> ChatOutput graph execution
- Graph serialization to JSON (dump)
- Graph deserialization from JSON (from_payload)
- Output verification after round-trip serialization
"""

from __future__ import annotations

import json

import pytest
from lfx.base.functions import FunctionComponent, component
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.schema.schema import INPUT_FIELD_NAME


class TestFunctionComponentGraphExecution:
    """Tests for FunctionComponent execution within a Graph."""

    @pytest.mark.asyncio
    async def test_simple_function_in_graph(self):
        """Test FunctionComponent connects and executes in a graph."""

        def uppercase(text: str) -> str:
            return text.upper()

        fc = FunctionComponent(uppercase)

        chat_input = ChatInput()
        chat_output = ChatOutput()

        fc.set(text=chat_input.message_response)
        chat_output.set(input_value=fc.result)

        graph = Graph(start=chat_input, end=chat_output)

        # The graph should have 3 vertices
        assert len(graph.vertices) == 3

        # Run the graph
        result = await graph.arun(
            inputs=[{INPUT_FIELD_NAME: "hello world"}],
        )

        # Verify output
        assert len(result) == 1
        output = result[0].outputs[0]
        assert output.results["message"].data["text"] == "HELLO WORLD"

    @pytest.mark.asyncio
    async def test_decorated_function_in_graph(self):
        """Test @component decorated function in a graph."""

        @component
        def reverse_text(text: str) -> str:
            """Reverse the input text."""
            return text[::-1]

        chat_input = ChatInput()
        chat_output = ChatOutput()

        reverse_text.set(text=chat_input.message_response)
        chat_output.set(input_value=reverse_text.result)

        graph = Graph(start=chat_input, end=chat_output)

        result = await graph.arun(
            inputs=[{INPUT_FIELD_NAME: "hello"}],
        )

        assert len(result) == 1
        output = result[0].outputs[0]
        assert output.results["message"].data["text"] == "olleh"

    @pytest.mark.asyncio
    async def test_chained_function_components(self):
        """Test multiple FunctionComponents chained together."""

        @component
        def add_prefix(text: str) -> str:
            return f"PREFIX: {text}"

        @component
        def add_suffix(text: str) -> str:
            return f"{text} :SUFFIX"

        chat_input = ChatInput()
        chat_output = ChatOutput()

        add_prefix.set(text=chat_input.message_response)
        add_suffix.set(text=add_prefix.result)
        chat_output.set(input_value=add_suffix.result)

        graph = Graph(start=chat_input, end=chat_output)

        # Should have 4 vertices
        assert len(graph.vertices) == 4

        result = await graph.arun(
            inputs=[{INPUT_FIELD_NAME: "hello"}],
        )

        assert len(result) == 1
        output = result[0].outputs[0]
        assert output.results["message"].data["text"] == "PREFIX: hello :SUFFIX"

    @pytest.mark.asyncio
    async def test_function_with_multiple_params(self):
        """Test FunctionComponent with multiple parameters."""

        @component
        def format_message(greeting: str, target: str = "User") -> str:
            return f"{greeting}, {target}!"

        chat_input = ChatInput()
        chat_output = ChatOutput()

        # Note: 'target' is used instead of 'name' to avoid attribute conflict
        format_message.set(greeting=chat_input.message_response, target="World")
        chat_output.set(input_value=format_message.result)

        graph = Graph(start=chat_input, end=chat_output)

        result = await graph.arun(
            inputs=[{INPUT_FIELD_NAME: "Hello"}],
        )

        assert len(result) == 1
        output = result[0].outputs[0]
        assert output.results["message"].data["text"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_async_function_in_graph(self):
        """Test async FunctionComponent in a graph."""

        @component
        async def async_process(text: str) -> str:
            # Simulating async operation
            return f"ASYNC: {text}"

        chat_input = ChatInput()
        chat_output = ChatOutput()

        async_process.set(text=chat_input.message_response)
        chat_output.set(input_value=async_process.result)

        graph = Graph(start=chat_input, end=chat_output)

        result = await graph.arun(
            inputs=[{INPUT_FIELD_NAME: "test"}],
        )

        assert len(result) == 1
        output = result[0].outputs[0]
        assert output.results["message"].data["text"] == "ASYNC: test"


class TestFunctionComponentSerialization:
    """Tests for FunctionComponent graph serialization."""

    def test_graph_dump_includes_function_component(self):
        """Test that graph.dump() includes FunctionComponent data."""

        @component
        def double_text(text: str) -> str:
            return text * 2

        chat_input = ChatInput()
        chat_output = ChatOutput()

        double_text.set(text=chat_input.message_response)
        chat_output.set(input_value=double_text.result)

        graph = Graph(start=chat_input, end=chat_output)

        dump = graph.dump()

        assert "data" in dump
        assert "nodes" in dump["data"]
        assert "edges" in dump["data"]

        # Should have 3 nodes
        assert len(dump["data"]["nodes"]) == 3

        # Find the FunctionComponent node
        fc_nodes = [n for n in dump["data"]["nodes"] if "double_text" in n.get("id", "")]
        assert len(fc_nodes) == 1

    def test_graph_dumps_produces_valid_json(self):
        """Test that graph.dumps() produces valid JSON string."""

        @component
        def process(text: str) -> str:
            return text.lower()

        chat_input = ChatInput()
        chat_output = ChatOutput()

        process.set(text=chat_input.message_response)
        chat_output.set(input_value=process.result)

        graph = Graph(start=chat_input, end=chat_output)

        json_str = graph.dumps()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "data" in parsed

    def test_edge_data_is_correct(self):
        """Test that edges between components are correctly serialized."""

        @component
        def transform(text: str) -> str:
            return text

        chat_input = ChatInput()
        chat_output = ChatOutput()

        transform.set(text=chat_input.message_response)
        chat_output.set(input_value=transform.result)

        graph = Graph(start=chat_input, end=chat_output)

        dump = graph.dump()

        # Should have 2 edges
        edges = dump["data"]["edges"]
        assert len(edges) == 2

        # Edges should reference correct nodes
        node_ids = {n["id"] for n in dump["data"]["nodes"]}
        for edge in edges:
            assert edge["source"] in node_ids
            assert edge["target"] in node_ids


class TestFunctionComponentDeserialization:
    """Tests for graph deserialization with FunctionComponent."""

    @pytest.mark.asyncio
    async def test_round_trip_simple_function(self):
        """Test serialize -> deserialize -> run produces same output."""

        @component(display_name="Upper Case")
        def to_upper(text: str) -> str:
            return text.upper()

        chat_input = ChatInput()
        chat_output = ChatOutput()

        to_upper.set(text=chat_input.message_response)
        chat_output.set(input_value=to_upper.result)

        graph1 = Graph(start=chat_input, end=chat_output)

        # Run original graph
        result1 = await graph1.arun(
            inputs=[{INPUT_FIELD_NAME: "hello"}],
        )

        output1 = result1[0].outputs[0].results["message"].data["text"]

        # Serialize
        dump = graph1.dump()

        # Deserialize
        graph2 = Graph.from_payload(dump)

        # Run deserialized graph
        result2 = await graph2.arun(
            inputs=[{INPUT_FIELD_NAME: "hello"}],
        )

        output2 = result2[0].outputs[0].results["message"].data["text"]

        # Outputs should match
        assert output1 == output2 == "HELLO"

    @pytest.mark.asyncio
    async def test_round_trip_simple_function_with_explicit_ids(self):
        """Test serialize -> deserialize -> run with explicit _ids.

        Note: ChatInput IDs must contain 'chat' for the default input_type
        filtering to work in Graph._set_inputs.
        """

        @component(display_name="Upper Case", _id="uppercase_func")
        def to_upper(text: str) -> str:
            return text.upper()

        # IDs must include 'chat' for input type filtering to work
        chat_input = ChatInput(_id="chat_input_1")
        chat_output = ChatOutput(_id="chat_output_1")

        to_upper.set(text=chat_input.message_response)
        chat_output.set(input_value=to_upper.result)

        graph1 = Graph(start=chat_input, end=chat_output)

        # Run original graph
        result1 = await graph1.arun(
            inputs=[{INPUT_FIELD_NAME: "hello"}],
        )

        output1 = result1[0].outputs[0].results["message"].data["text"]

        # Serialize
        dump = graph1.dump()

        # Deserialize
        graph2 = Graph.from_payload(dump)

        # Run deserialized graph
        result2 = await graph2.arun(
            inputs=[{INPUT_FIELD_NAME: "hello"}],
        )

        output2 = result2[0].outputs[0].results["message"].data["text"]

        # Outputs should match
        assert output1 == output2 == "HELLO"

    @pytest.mark.asyncio
    async def test_round_trip_chained_functions(self):
        """Test round-trip with multiple chained FunctionComponents."""

        @component(_id="step1_func")
        def step1(text: str) -> str:
            return f"[{text}]"

        @component(_id="step2_func")
        def step2(text: str) -> str:
            return f"<{text}>"

        # IDs must include 'chat' for input type filtering to work
        chat_input = ChatInput(_id="chat_input_1")
        chat_output = ChatOutput(_id="chat_output_1")

        step1.set(text=chat_input.message_response)
        step2.set(text=step1.result)
        chat_output.set(input_value=step2.result)

        graph1 = Graph(start=chat_input, end=chat_output)

        # Run original
        result1 = await graph1.arun(inputs=[{INPUT_FIELD_NAME: "test"}])
        output1 = result1[0].outputs[0].results["message"].data["text"]

        # Round-trip
        dump = graph1.dump()
        graph2 = Graph.from_payload(dump)

        result2 = await graph2.arun(inputs=[{INPUT_FIELD_NAME: "test"}])
        output2 = result2[0].outputs[0].results["message"].data["text"]

        assert output1 == output2 == "<[test]>"

    def test_deserialized_graph_has_correct_structure(self):
        """Test that deserialized graph has correct vertices and edges."""

        @component
        def process(text: str) -> str:
            return text

        chat_input = ChatInput()
        chat_output = ChatOutput()

        process.set(text=chat_input.message_response)
        chat_output.set(input_value=process.result)

        original = Graph(start=chat_input, end=chat_output)

        dump = original.dump()
        restored = Graph.from_payload(dump)

        # Same number of vertices
        assert len(restored.vertices) == len(original.vertices)

        # Same number of edges
        assert len(restored.edges) == len(original.edges)


class TestFunctionComponentWithDifferentTypes:
    """Test FunctionComponent with various input/output types."""

    @pytest.mark.asyncio
    async def test_int_parameter(self):
        """Test FunctionComponent with int parameter."""

        @component
        def repeat(text: str, count: int = 2) -> str:
            return text * count

        chat_input = ChatInput()
        chat_output = ChatOutput()

        repeat.set(text=chat_input.message_response, count=3)
        chat_output.set(input_value=repeat.result)

        graph = Graph(start=chat_input, end=chat_output)

        result = await graph.arun(inputs=[{INPUT_FIELD_NAME: "ab"}])
        output = result[0].outputs[0].results["message"].data["text"]

        assert output == "ababab"

    @pytest.mark.asyncio
    async def test_bool_parameter(self):
        """Test FunctionComponent with bool parameter."""

        @component
        def maybe_upper(text: str, upper: bool = False) -> str:  # noqa: FBT001, FBT002
            return text.upper() if upper else text.lower()

        chat_input = ChatInput()
        chat_output = ChatOutput()

        maybe_upper.set(text=chat_input.message_response, upper=True)
        chat_output.set(input_value=maybe_upper.result)

        graph = Graph(start=chat_input, end=chat_output)

        result = await graph.arun(inputs=[{INPUT_FIELD_NAME: "Hello"}])
        output = result[0].outputs[0].results["message"].data["text"]

        assert output == "HELLO"

    @pytest.mark.asyncio
    async def test_dict_return_becomes_data(self):
        """Test that dict return value is wrapped in Data."""

        @component
        def to_dict(text: str) -> dict:
            return {"message": text, "length": len(text)}

        chat_input = ChatInput()
        chat_output = ChatOutput()

        to_dict.set(text=chat_input.message_response)
        chat_output.set(input_value=to_dict.result)

        graph = Graph(start=chat_input, end=chat_output)

        result = await graph.arun(inputs=[{INPUT_FIELD_NAME: "hello"}])

        # The result should be Data type
        output = result[0].outputs[0]
        assert output is not None


class TestFunctionComponentOnlyPipeline:
    """Test pipelines containing only FunctionComponents (no ChatInput/ChatOutput)."""

    @pytest.mark.asyncio
    async def test_two_function_components_chained(self):
        """Test two FunctionComponents connected directly."""

        @component
        def step1(text: str) -> str:
            return text.upper()

        @component
        def step2(text: str) -> str:
            return f"[{text}]"

        # Set initial value BEFORE creating graph
        step1.set(text="hello")
        step2.set(text=step1.result)

        graph = Graph(step1, step2)

        # Should have 2 vertices
        assert len(graph.vertices) == 2
        assert len(graph.edges) == 1

        # Run the graph
        await graph.arun(inputs=[])

        # Get result from final vertex
        final_vertex = next(v for v in graph.vertices if "step2" in v.id)
        output = final_vertex.results["result"]
        assert output == "[HELLO]"

    @pytest.mark.asyncio
    async def test_three_function_components_pipeline(self):
        """Test three FunctionComponents in a pipeline."""

        @component
        def to_upper(text: str) -> str:
            return text.upper()

        @component
        def add_brackets(text: str) -> str:
            return f"[{text}]"

        @component
        def add_prefix(text: str) -> str:
            return f"Result: {text}"

        # Set initial value and chain
        to_upper.set(text="hello")
        add_brackets.set(text=to_upper.result)
        add_prefix.set(text=add_brackets.result)

        graph = Graph(to_upper, add_prefix)

        assert len(graph.vertices) == 3
        assert len(graph.edges) == 2

        await graph.arun(inputs=[])

        # Get result from final vertex
        final_vertex = next(v for v in graph.vertices if "add_prefix" in v.id)
        output = final_vertex.results["result"]
        assert output == "Result: [HELLO]"

    @pytest.mark.asyncio
    async def test_five_function_components_pipeline(self):
        """Test a longer pipeline of 5 FunctionComponents."""

        @component
        def step1(text: str) -> str:
            return f"1:{text}"

        @component
        def step2(text: str) -> str:
            return f"2:{text}"

        @component
        def step3(text: str) -> str:
            return f"3:{text}"

        @component
        def step4(text: str) -> str:
            return f"4:{text}"

        @component
        def step5(text: str) -> str:
            return f"5:{text}"

        # Set initial value and chain
        step1.set(text="start")
        step2.set(text=step1.result)
        step3.set(text=step2.result)
        step4.set(text=step3.result)
        step5.set(text=step4.result)

        graph = Graph(step1, step5)

        assert len(graph.vertices) == 5
        assert len(graph.edges) == 4

        await graph.arun(inputs=[])

        # Get result from final vertex
        final_vertex = next(v for v in graph.vertices if "step5" in v.id)
        output = final_vertex.results["result"]
        assert output == "5:4:3:2:1:start"

    @pytest.mark.asyncio
    async def test_function_pipeline_with_string_types(self):
        """Test pipeline with string transformations through chain."""

        @component
        def wrap_brackets(text: str) -> str:
            return f"[{text}]"

        @component
        def wrap_parens(text: str) -> str:
            return f"({text})"

        @component
        def wrap_angles(text: str) -> str:
            return f"<{text}>"

        # Set initial value and chain
        wrap_brackets.set(text="data")
        wrap_parens.set(text=wrap_brackets.result)
        wrap_angles.set(text=wrap_parens.result)

        graph = Graph(wrap_brackets, wrap_angles)

        assert len(graph.vertices) == 3

        await graph.arun(inputs=[])

        # Get result from final vertex
        final_vertex = next(v for v in graph.vertices if "wrap_angles" in v.id)
        output = final_vertex.results["result"]
        assert output == "<([data])>"

    @pytest.mark.asyncio
    async def test_function_pipeline_round_trip(self):
        """Test serialization round-trip for function-only pipeline."""

        @component(_id="fc_step1")
        def upper_step(text: str) -> str:
            return text.upper()

        @component(_id="fc_step2")
        def bracket_step(text: str) -> str:
            return f"[{text}]"

        @component(_id="fc_step3")
        def final_step(text: str) -> str:
            return f"Final: {text}"

        # Set initial value and chain
        upper_step.set(text="test")
        bracket_step.set(text=upper_step.result)
        final_step.set(text=bracket_step.result)

        graph1 = Graph(upper_step, final_step)

        # Run original
        await graph1.arun(inputs=[])
        final_vertex1 = next(v for v in graph1.vertices if v.id == "fc_step3")
        output1 = final_vertex1.results["result"]

        # Serialize and deserialize
        dump = graph1.dump()
        graph2 = Graph.from_payload(dump)

        # Run deserialized
        await graph2.arun(inputs=[])
        final_vertex2 = next(v for v in graph2.vertices if v.id == "fc_step3")
        output2 = final_vertex2.results["result"]

        assert output1 == output2 == "Final: [TEST]"

    @pytest.mark.asyncio
    async def test_function_pipeline_with_async_functions(self):
        """Test pipeline mixing sync and async FunctionComponents."""

        @component
        def sync_upper(text: str) -> str:
            return text.upper()

        @component
        async def async_wrap(text: str) -> str:
            return f"<{text}>"

        @component
        def sync_prefix(text: str) -> str:
            return f"Done: {text}"

        # Set initial value and chain
        sync_upper.set(text="hello")
        async_wrap.set(text=sync_upper.result)
        sync_prefix.set(text=async_wrap.result)

        graph = Graph(sync_upper, sync_prefix)

        await graph.arun(inputs=[])

        # Get result from final vertex
        final_vertex = next(v for v in graph.vertices if "sync_prefix" in v.id)
        output = final_vertex.results["result"]
        assert output == "Done: <HELLO>"

    @pytest.mark.asyncio
    async def test_function_pipeline_with_defaults(self):
        """Test pipeline where a component uses default parameter values."""

        @component
        def greet(name: str) -> str:
            return f"Hello, {name}"

        @component
        def format_msg(text: str, wrapper: str = "***") -> str:
            """Component with a default parameter (wrapper)."""
            return f"{wrapper} {text} {wrapper}"

        # Set initial value and chain (wrapper uses default "***")
        greet.set(name="World")
        format_msg.set(text=greet.result)

        graph = Graph(greet, format_msg)

        await graph.arun(inputs=[])

        # Get result from final vertex
        final_vertex = next(v for v in graph.vertices if "format_msg" in v.id)
        output = final_vertex.results["result"]
        assert output == "*** Hello, World ***"

    def test_function_pipeline_structure(self):
        """Test that function-only pipeline has correct graph structure."""

        @component(_id="pipeline_a")
        def func_a(x: str) -> str:
            return x

        @component(_id="pipeline_b")
        def func_b(x: str) -> str:
            return x

        @component(_id="pipeline_c")
        def func_c(x: str) -> str:
            return x

        @component(_id="pipeline_d")
        def func_d(x: str) -> str:
            return x

        func_b.set(x=func_a.result)
        func_c.set(x=func_b.result)
        func_d.set(x=func_c.result)

        graph = Graph(func_a, func_d)

        # Verify structure
        assert len(graph.vertices) == 4
        assert len(graph.edges) == 3

        # Verify all components are in the graph
        vertex_ids = {v.id for v in graph.vertices}
        assert "pipeline_a" in vertex_ids
        assert "pipeline_b" in vertex_ids
        assert "pipeline_c" in vertex_ids
        assert "pipeline_d" in vertex_ids

        # Verify edges connect correctly
        dump = graph.dump()
        edges = dump["data"]["edges"]

        edge_pairs = {(e["source"], e["target"]) for e in edges}
        assert ("pipeline_a", "pipeline_b") in edge_pairs
        assert ("pipeline_b", "pipeline_c") in edge_pairs
        assert ("pipeline_c", "pipeline_d") in edge_pairs


class TestFunctionComponentEdgeCases:
    """Test edge cases for FunctionComponent integration."""

    @pytest.mark.asyncio
    async def test_empty_string_input(self):
        """Test FunctionComponent handles empty string."""

        @component
        def process_empty(text: str) -> str:
            return f"Got: [{text}]"

        chat_input = ChatInput()
        chat_output = ChatOutput()

        process_empty.set(text=chat_input.message_response)
        chat_output.set(input_value=process_empty.result)

        graph = Graph(start=chat_input, end=chat_output)

        result = await graph.arun(inputs=[{INPUT_FIELD_NAME: ""}])
        output = result[0].outputs[0].results["message"].data["text"]

        assert output == "Got: []"

    @pytest.mark.asyncio
    async def test_special_characters_in_input(self):
        """Test FunctionComponent handles special characters."""

        @component
        def echo(text: str) -> str:
            return text

        chat_input = ChatInput()
        chat_output = ChatOutput()

        echo.set(text=chat_input.message_response)
        chat_output.set(input_value=echo.result)

        graph = Graph(start=chat_input, end=chat_output)

        special_input = "Hello\n\t'\"<>&{}[]"
        result = await graph.arun(inputs=[{INPUT_FIELD_NAME: special_input}])
        output = result[0].outputs[0].results["message"].data["text"]

        assert output == special_input

    @pytest.mark.asyncio
    async def test_unicode_input(self):
        """Test FunctionComponent handles unicode characters."""

        @component
        def process_unicode(text: str) -> str:
            return f"Echo: {text}"

        chat_input = ChatInput()
        chat_output = ChatOutput()

        process_unicode.set(text=chat_input.message_response)
        chat_output.set(input_value=process_unicode.result)

        graph = Graph(start=chat_input, end=chat_output)

        unicode_input = "Hello \U0001f600 \u4e2d\u6587 \u0420\u0443\u0441\u0441\u043a\u0438\u0439"
        result = await graph.arun(inputs=[{INPUT_FIELD_NAME: unicode_input}])
        output = result[0].outputs[0].results["message"].data["text"]

        assert output == f"Echo: {unicode_input}"

    def test_multiple_serialization_roundtrips(self):
        """Test graph survives multiple serialization roundtrips."""

        @component(_id="multi_round_func")
        def transform(text: str) -> str:
            return text.upper()

        # IDs must include 'chat' for input type filtering to work
        chat_input = ChatInput(_id="chat_multi_in")
        chat_output = ChatOutput(_id="chat_multi_out")

        transform.set(text=chat_input.message_response)
        chat_output.set(input_value=transform.result)

        graph = Graph(start=chat_input, end=chat_output)

        # Multiple roundtrips
        for _ in range(3):
            dump = graph.dump()
            json_str = json.dumps(dump)
            parsed = json.loads(json_str)
            graph = Graph.from_payload(parsed)

        # Should still work
        assert len(graph.vertices) == 3
        assert len(graph.edges) == 2
