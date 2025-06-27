import os

import pytest
from langflow.components.input_output import ChatInput, ChatOutput, TextOutputComponent
from langflow.components.input_output.text import TextInputComponent
from langflow.components.logic.conditional_router import ConditionalRouterComponent
from langflow.components.openai.openai_chat_model import OpenAIModelComponent
from langflow.components.processing import PromptComponent
from langflow.custom.custom_component.component import Component
from langflow.graph.graph.base import Graph
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
        Output(display_name="Message", name="some_text", method="concatenate"),
    ]

    def concatenate(self) -> Message:
        return Message(text=f"{self.text}{self.text}" or "test")


@pytest.mark.skip(reason="Temporarily disabled")
def test_cycle_in_graph():
    chat_input = ChatInput(_id="chat_input")
    router = ConditionalRouterComponent(_id="router", default_route="true_result")
    # Use router's true_result output instead of message
    chat_input.set(input_value=router.true_case_message)
    chat_input.set(input_value=router.false_case_message)
    concat_component = Concatenate(_id="concatenate")
    concat_component.set(text=chat_input.message_response)
    router.set(
        input_text=chat_input.message_response,
        match_text="testtesttesttest",
        operator="equals",
        true_case_message=concat_component.concatenate,
        false_case_message=concat_component.concatenate,
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
    text_input = TextInputComponent(_id="text_input")
    router = ConditionalRouterComponent(_id="router")
    text_input.set(input_value=router.false_case_message)
    text_input.set(input_value=router.true_case_message)
    concat_component = Concatenate(_id="concatenate")
    concat_component.set(text=text_input.text_response)
    router.set(
        input_text=text_input.text_response,
        match_text="testtesttesttest",
        operator="equals",
        true_case_message=concat_component.concatenate,
        false_case_message=concat_component.concatenate,
    )
    text_output = TextOutputComponent(_id="text_output")
    text_output.set(input_value=router.true_response)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=text_output.text_response)

    graph = Graph(text_input, chat_output)
    assert graph.is_cyclic is True

    # Run queue should contain chat_input and not router
    assert "text_input" in graph._run_queue
    assert "router" not in graph._run_queue

    with pytest.raises(ValueError, match="Max iterations reached"):
        list(graph.start(max_iterations=2, config={"output": {"cache": False}}))


def test_that_outputs_cache_is_set_to_false_in_cycle():
    chat_input = ChatInput(_id="chat_input")
    router = ConditionalRouterComponent(_id="router")
    # Use router's true_result output instead of message
    chat_input.set(input_value=router.true_case_message)
    chat_input.set(input_value=router.false_case_message)
    concat_component = Concatenate(_id="concatenate")
    concat_component.set(text=chat_input.message_response)
    router.set(
        input_text=chat_input.message_response,
        match_text="testtesttesttest",
        operator="equals",
        true_case_message=concat_component.concatenate,
        false_case_message=concat_component.concatenate,
    )
    text_output = TextOutputComponent(_id="text_output")
    text_output.set(input_value=router.true_response)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=text_output.text_response)

    graph = Graph(chat_input, chat_output)
    cycle_vertices = find_cycle_vertices(graph._get_edges_as_list_of_tuples())
    cycle_outputs_lists = [
        graph.vertex_map[vertex_id].custom_component._outputs_map.values() for vertex_id in cycle_vertices
    ]
    cycle_outputs = [output for outputs in cycle_outputs_lists for output in outputs]
    for output in cycle_outputs:
        assert output.cache is False

    non_cycle_outputs_lists = [
        vertex.custom_component.outputs for vertex in graph.vertices if vertex.id not in cycle_vertices
    ]
    non_cycle_outputs = [output for outputs in non_cycle_outputs_lists for output in outputs]
    for output in non_cycle_outputs:
        assert output.cache is True


@pytest.mark.skip(reason="Cycles now require a LoopComponent to work")
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OpenAI API key required")
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
        true_case_message=openai_component_1.text_response,
        false_case_message=openai_component_1.text_response,
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
    assert "chat_output_1" in results_ids, f"Expected outputs not in results: {results_ids}. Snapshots: {snapshots}"


@pytest.mark.skip(reason="Cycles now require a LoopComponent to work")
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OpenAI API key required")
def test_updated_graph_with_max_iterations():
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
        true_case_message=openai_component_1.text_response,
        false_case_message=openai_component_1.text_response,
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
    assert "chat_output_1" in results_ids, f"Expected outputs not in results: {results_ids}. Snapshots: {snapshots}"


def test_conditional_router_max_iterations():
    # Chat input initialization
    text_input = TextInputComponent(_id="text_input")

    # Conditional router setup with a condition that will never match
    router = ConditionalRouterComponent(_id="router").set(
        input_text=text_input.text_response,
        match_text="bacon",
        operator="equals",
        true_case_message="This message should not be routed to true_result",
        false_case_message="This message should not be routed to false_result",
        max_iterations=5,
        default_route="true_result",
    )

    # Chat output for the true route
    text_input.set(input_value=router.false_response)

    # Chat output for the false route
    chat_output_false = ChatOutput(_id="chat_output_false")
    chat_output_false.set(input_value=router.true_response)

    # Build the graph
    graph = Graph(text_input, chat_output_false)

    # Assertions for graph cyclicity and correctness
    assert graph.is_cyclic is True, "Graph should contain cycles."

    # Run and validate the execution of the graph
    results = []
    snapshots = [graph.get_snapshot()]
    previous_iteration = graph.context.get("router_iteration", 0)
    for result in graph.start(max_iterations=20, config={"output": {"cache": False}}):
        snapshots.append(graph.get_snapshot())
        results.append(result)
        if hasattr(result, "vertex") and result.vertex.id == "router":
            current_iteration = graph.context.get("router_iteration", 0)
            assert current_iteration == previous_iteration + 1, "Iteration should increment by 1"
            previous_iteration = current_iteration

    # Check if the max_iterations logic is working
    router_id = router._id.lower()
    assert graph.context.get(f"{router_id}_iteration", 0) == 5, "Router should stop after max_iterations"

    # Extract the vertex IDs for analysis
    results_ids = [result.vertex.id for result in results if hasattr(result, "vertex")]
    assert "chat_output_false" in results_ids, f"Expected outputs not in results: {results_ids}"
