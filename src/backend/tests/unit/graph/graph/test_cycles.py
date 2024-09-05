import pytest

from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.outputs.TextOutput import TextOutputComponent
from langflow.components.prototypes.ConditionalRouter import ConditionalRouterComponent
from langflow.custom.custom_component.component import Component
from langflow.graph.graph.base import Graph
from langflow.graph.graph.utils import find_cycle_vertices
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


@pytest.fixture
def client():
    pass


class Concatenate(Component):
    display_name = "Concatenate"
    description = "Concatenates two strings"

    inputs = [
        MessageTextInput(name="text", display_name="Text", required=True),
    ]
    outputs = [
        Output(display_name="Text", name="some_text", method="concatenate"),
    ]

    def concatenate(self) -> Message:
        return Message(text=f"{self.text}{self.text}" or "test")


def test_cycle_in_graph():
    chat_input = ChatInput(_id="chat_input")
    router = ConditionalRouterComponent(_id="router")
    chat_input.set(input_value=router.false_response)
    concat_component = Concatenate(_id="concatenate")
    concat_component.set(text=chat_input.message_response)
    router.set(
        input_text=chat_input.message_response,
        match_text="testtesttesttest",
        operator="equals",
        message=concat_component.concatenate,
    )
    text_output = TextOutputComponent(_id="text_output")
    text_output.set(input_value=router.true_response)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=text_output.text_response)

    graph = Graph(chat_input, chat_output)
    assert graph.is_cyclic is True

    # Run queue should contain chat_input and not router
    assert "chat_input" in graph._run_queue
    assert "router" not in graph._run_queue
    results = []
    max_iterations = 20
    snapshots = [graph._snapshot()]
    for result in graph.start(max_iterations=max_iterations, config={"output": {"cache": False}}):
        snapshots.append(graph._snapshot())
        results.append(result)
    results_ids = [result.vertex.id for result in results if hasattr(result, "vertex")]
    assert results_ids[-2:] == ["text_output", "chat_output"]
    assert len(results_ids) > len(graph.vertices), snapshots
    # Check that chat_output and text_output are the last vertices in the results
    assert results_ids == [
        "chat_input",
        "concatenate",
        "router",
        "chat_input",
        "concatenate",
        "router",
        "chat_input",
        "concatenate",
        "router",
        "chat_input",
        "concatenate",
        "router",
        "text_output",
        "chat_output",
    ], f"Results: {results_ids}"


def test_cycle_in_graph_max_iterations():
    chat_input = ChatInput(_id="chat_input")
    router = ConditionalRouterComponent(_id="router")
    chat_input.set(input_value=router.false_response)
    concat_component = Concatenate(_id="concatenate")
    concat_component.set(text=chat_input.message_response)
    router.set(
        input_text=chat_input.message_response,
        match_text="testtesttesttest",
        operator="equals",
        message=concat_component.concatenate,
    )
    text_output = TextOutputComponent(_id="text_output")
    text_output.set(input_value=router.true_response)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=text_output.text_response)

    graph = Graph(chat_input, chat_output)
    assert graph.is_cyclic is True

    # Run queue should contain chat_input and not router
    assert "chat_input" in graph._run_queue
    assert "router" not in graph._run_queue
    results = []

    with pytest.raises(ValueError, match="Max iterations reached"):
        for result in graph.start(max_iterations=2, config={"output": {"cache": False}}):
            results.append(result)


def test_that_outputs_cache_is_set_to_false_in_cycle():
    chat_input = ChatInput(_id="chat_input")
    router = ConditionalRouterComponent(_id="router")
    chat_input.set(input_value=router.false_response)
    concat_component = Concatenate(_id="concatenate")
    concat_component.set(text=chat_input.message_response)
    router.set(
        input_text=chat_input.message_response,
        match_text="testtesttesttest",
        operator="equals",
        message=concat_component.concatenate,
    )
    text_output = TextOutputComponent(_id="text_output")
    text_output.set(input_value=router.true_response)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=text_output.text_response)

    graph = Graph(chat_input, chat_output)
    cycle_vertices = find_cycle_vertices(graph._get_edges_as_list_of_tuples())
    cycle_outputs_lists = [graph.vertex_map[vertex_id]._custom_component.outputs for vertex_id in cycle_vertices]
    cycle_outputs = [output for outputs in cycle_outputs_lists for output in outputs]
    for output in cycle_outputs:
        assert output.cache is False

    non_cycle_outputs_lists = [
        vertex._custom_component.outputs for vertex in graph.vertices if vertex.id not in cycle_vertices
    ]
    non_cycle_outputs = [output for outputs in non_cycle_outputs_lists for output in outputs]
    for output in non_cycle_outputs:
        assert output.cache is True
