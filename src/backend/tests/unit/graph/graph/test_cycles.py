import os

import pytest
from langflow.components.inputs import ChatInput
from langflow.components.models import OpenAIModelComponent
from langflow.components.outputs import ChatOutput, TextOutputComponent
from langflow.components.prompts import PromptComponent
from langflow.components.prototypes import ConditionalRouterComponent
from langflow.custom import Component
from langflow.graph import Graph
from langflow.graph.graph.utils import find_cycle_vertices
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


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


@pytest.mark.skip(reason="Temporarily disabled")
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

    with pytest.raises(ValueError, match="Max iterations reached"):
        list(graph.start(max_iterations=2, config={"output": {"cache": False}}))


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
    cycle_outputs_lists = [graph.vertex_map[vertex_id].custom_component.outputs for vertex_id in cycle_vertices]
    cycle_outputs = [output for outputs in cycle_outputs_lists for output in outputs]
    for output in cycle_outputs:
        assert output.cache is False

    non_cycle_outputs_lists = [
        vertex.custom_component.outputs for vertex in graph.vertices if vertex.id not in cycle_vertices
    ]
    non_cycle_outputs = [output for outputs in non_cycle_outputs_lists for output in outputs]
    for output in non_cycle_outputs:
        assert output.cache is True


@pytest.mark.api_key_required
def test_updated_graph_with_prompts():
    # Chat input initialization
    chat_input = ChatInput(_id="chat_input").set(input_value="bacon")

    # First prompt: Guessing game with hints
    prompt_component_1 = PromptComponent(_id="prompt_component_1").set(
        template="Try to guess a word. I will give you hints if you get it wrong.\n"
        "Hint: {hint}\n"
        "Last try: {last_try}\n"
        "Answer:",
    )

    # First OpenAI LLM component (Processes the guessing prompt)
    openai_component_1 = OpenAIModelComponent(_id="openai_1").set(
        input_value=prompt_component_1.build_prompt, api_key=os.getenv("OPENAI_API_KEY")
    )

    # Conditional router based on agent response
    router = ConditionalRouterComponent(_id="router").set(
        input_text=openai_component_1.text_response,
        match_text=chat_input.message_response,
        operator="contains",
        message=openai_component_1.text_response,
    )

    # Second prompt: After the last try, provide a new hint
    prompt_component_2 = PromptComponent(_id="prompt_component_2")
    prompt_component_2.set(
        template="Given the following word and the following last try. Give the guesser a new hint.\n"
        "Last try: {last_try}\n"
        "Word: {word}\n"
        "Hint:",
        word=chat_input.message_response,
        last_try=router.false_response,
    )

    # Second OpenAI component (handles the router's response)
    openai_component_2 = OpenAIModelComponent(_id="openai_2")
    openai_component_2.set(input_value=prompt_component_2.build_prompt, api_key=os.getenv("OPENAI_API_KEY"))

    prompt_component_1.set(hint=openai_component_2.text_response, last_try=router.false_response)

    # chat output for the final OpenAI response
    chat_output_1 = ChatOutput(_id="chat_output_1")
    chat_output_1.set(input_value=router.true_response)

    # Build the graph without concatenate
    graph = Graph(chat_input, chat_output_1)

    # Assertions for graph cyclicity and correctness
    assert graph.is_cyclic is True, "Graph should contain cycles."

    # Run and validate the execution of the graph
    results = []
    max_iterations = 20
    snapshots = [graph.get_snapshot()]

    for result in graph.start(max_iterations=max_iterations, config={"output": {"cache": False}}):
        snapshots.append(graph.get_snapshot())
        results.append(result)

    assert len(snapshots) > 2, "Graph should have more than one snapshot"
    # Extract the vertex IDs for analysis
    results_ids = [result.vertex.id for result in results if hasattr(result, "vertex")]
    assert "chat_output_1" in results_ids, f"Expected outputs not in results: {results_ids}"
