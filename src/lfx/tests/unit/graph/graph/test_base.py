from collections import deque

import pytest
from ag_ui.core import RunFinishedEvent, RunStartedEvent
from lfx.components.input_output import ChatInput, ChatOutput, TextOutputComponent
from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
from lfx.components.processing.combine_text import CombineTextComponent
from lfx.graph import Graph
from lfx.graph.graph.constants import Finish


@pytest.mark.asyncio
async def test_graph_not_prepared():
    chat_input = ChatInput()
    chat_output = ChatOutput()
    graph = Graph()
    graph.add_component(chat_input)
    graph.add_component(chat_output)
    with pytest.raises(ValueError, match="Graph not prepared"):
        await graph.astep()


@pytest.mark.asyncio
async def test_graph_with_edge():
    chat_input = ChatInput()
    chat_output = ChatOutput()
    graph = Graph()
    input_id = graph.add_component(chat_input)
    output_id = graph.add_component(chat_output)
    graph.add_component_edge(input_id, (chat_input.outputs[0].name, chat_input.inputs[0].name), output_id)
    graph.prepare()
    # ensure prepare is idempotent
    graph.prepare()
    assert graph._run_queue == deque([input_id])
    await graph.astep()
    assert graph._run_queue == deque([output_id])

    assert graph.vertices[0].id == input_id
    assert graph.vertices[1].id == output_id
    assert graph.edges[0].source_id == input_id
    assert graph.edges[0].target_id == output_id


@pytest.mark.asyncio
async def test_graph_functional():
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    graph = Graph(chat_input, chat_output)
    assert graph._run_queue == deque(["chat_input"])
    await graph.astep()
    assert graph._run_queue == deque(["chat_output"])

    assert graph.vertices[0].id == "chat_input"
    assert graph.vertices[1].id == "chat_output"
    assert graph.edges[0].source_id == "chat_input"
    assert graph.edges[0].target_id == "chat_output"


@pytest.mark.asyncio
async def test_graph_functional_async_start():
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    graph = Graph(chat_input, chat_output)
    # Now iterate through the graph
    # and check that the graph is running
    # correctly
    ids = ["chat_input", "chat_output"]
    results = [result async for result in graph.async_start()]

    assert len(results) == 3
    assert all(result.vertex.id in ids for result in results if hasattr(result, "vertex"))
    assert results[-1] == Finish()


def test_graph_functional_start_end():
    chat_input = ChatInput(_id="chat_input")
    text_output = TextOutputComponent(_id="text_output")
    text_output.set(input_value=chat_input.message_response)
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(input_value=text_output.text_response)
    graph = Graph(chat_input, text_output)
    graph.prepare()
    # Now iterate through the graph
    # and check that the graph is running
    # correctly
    ids = ["chat_input", "text_output"]
    results = list(graph.start())

    assert len(results) == len(ids) + 1
    assert all(result.vertex.id in ids for result in results if hasattr(result, "vertex"))
    assert results[-1] == Finish()
    # Now, using the same components but different start and end components
    graph = Graph(chat_input, chat_output)
    graph.prepare()
    ids = ["chat_input", "chat_output", "text_output"]
    results = []
    for result in graph.start():
        results.append(result)

    assert len(results) == len(ids) + 1
    assert all(result.vertex.id in ids for result in results if hasattr(result, "vertex"))
    assert results[-1] == Finish()


def test_get_terminal_nodes():
    """Test the get_terminal_nodes method identifies vertices with no outgoing edges."""
    # Create a simple linear graph structure:
    # chat_input -> text_output -> chat_output
    # Terminal node should be: chat_output

    chat_input = ChatInput(_id="chat_input")
    text_output = TextOutputComponent(_id="text_output")
    chat_output = ChatOutput(_id="chat_output")

    text_output.set(input_value=chat_input.message_response)
    chat_output.set(input_value=text_output.text_response)

    graph = Graph(chat_input, chat_output)

    # Test get_terminal_nodes
    terminal_nodes = graph.get_terminal_nodes()

    # Should return the terminal nodes (no outgoing edges)
    # In this case: only chat_output
    expected_terminal_ids = {"chat_output"}
    actual_terminal_ids = set(terminal_nodes)

    assert actual_terminal_ids == expected_terminal_ids, (
        f"Expected terminal nodes {expected_terminal_ids}, got {actual_terminal_ids}"
    )

    # Verify non-terminal nodes are not included
    assert "chat_input" not in terminal_nodes, "Input node should not be terminal (has outgoing edges)"
    assert "text_output" not in terminal_nodes, "Text node should not be terminal (has outgoing edges)"


def test_get_terminal_nodes_with_agent_branches():
    """Test get_terminal_nodes with an agent that has two output branches.

    Graph structure:
    chatInput -> llmAgent -> textEdit -> chatOutput
                          -> textOutput

    Terminal nodes should be: chatOutput, textOutput
    """
    chat_input = ChatInput(_id="chat_input")
    llm_agent = ToolCallingAgentComponent(_id="llm_agent")
    text_edit = CombineTextComponent(_id="text_edit")
    chat_output = ChatOutput(_id="chat_output")
    text_output = TextOutputComponent(_id="text_output")

    # Set up connections using the proper pattern
    # Agent takes input from chat_input
    llm_agent.set(input_value=chat_input.message_response)

    # Text edit component takes agent response and combines it with some text
    text_edit.set(text1=llm_agent.message_response, text2="[Edited]", delimiter=" ")

    # Chat output takes the edited text
    chat_output.set(input_value=text_edit.combined_text)

    # Text output takes the raw agent response (second branch)
    text_output.set(input_value=llm_agent.message_response)

    # Create graph with start and one end component
    # The graph will automatically include all connected components
    graph = Graph(chat_input, chat_output)

    # Add the text_output component since it's in a separate branch and when
    # we create Graph(chat_input, chat_output), it only includes the path from chat_input to chat_output,
    # but the text_output component is in a separate branch that doesn't lead to chat_output.
    graph.add_component(text_output)

    # Test get_terminal_nodes
    terminal_nodes = graph.get_terminal_nodes()

    # Should return both terminal nodes
    expected_terminal_ids = {"chat_output", "text_output"}
    actual_terminal_ids = set(terminal_nodes)

    assert actual_terminal_ids == expected_terminal_ids, (
        f"Expected terminal nodes {expected_terminal_ids}, got {actual_terminal_ids}"
    )

    # Verify non-terminal nodes are not included
    assert "chat_input" not in terminal_nodes, "Input node should not be terminal (has outgoing edges)"
    assert "llm_agent" not in terminal_nodes, "Agent node should not be terminal (has outgoing edges)"
    assert "text_edit" not in terminal_nodes, "Text edit node should not be terminal (has outgoing edges)"


def test_get_terminal_nodes_single_node():
    """Test get_terminal_nodes with a single isolated node."""
    single_node = ChatInput(_id="single_node")

    # Create graph with same component as start and end
    graph = Graph(single_node, single_node)

    terminal_nodes = graph.get_terminal_nodes()

    # Single isolated node should be terminal
    assert terminal_nodes == ["single_node"], f"Expected ['single_node'], got {terminal_nodes}"


def test_get_terminal_nodes_linear_chain():
    """Test get_terminal_nodes with a linear chain of nodes."""
    # Create: A -> B -> C -> D
    # Only D should be terminal

    node_a = ChatInput(_id="node_a")
    node_b = TextOutputComponent(_id="node_b")
    node_c = TextOutputComponent(_id="node_c")
    node_d = ChatOutput(_id="node_d")

    # Set up linear chain connections
    node_b.set(input_value=node_a.message_response)
    node_c.set(input_value=node_b.text_response)
    node_d.set(input_value=node_c.text_response)

    # Create graph with start and end
    graph = Graph(node_a, node_d)

    terminal_nodes = graph.get_terminal_nodes()

    # Only the last node should be terminal
    assert terminal_nodes == ["node_d"], f"Expected only ['node_d'] to be terminal, got {terminal_nodes}"


def test_get_terminal_nodes_empty_graph():
    """Test get_terminal_nodes with an empty graph."""
    graph = Graph()
    graph.initialize()

    terminal_nodes = graph.get_terminal_nodes()

    # Empty graph should have no terminal nodes
    assert terminal_nodes == [], f"Expected empty list, got {terminal_nodes}"


# TODO: Move to Langflow tests
@pytest.mark.skip(reason="Temporarily disabled")
def test_graph_set_with_valid_component():
    from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
    from lfx.components.tools.yahoo_finance import YfinanceToolComponent

    tool = YfinanceToolComponent()
    tool_calling_agent = ToolCallingAgentComponent()
    tool_calling_agent.set(tools=[tool])


def test_graph_before_callback_event():
    """Test that before_callback_event generates the correct RunStartedEvent payload."""
    # Create a simple graph with two components and a flow_id
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    graph = Graph(chat_input, chat_output, flow_id="test_flow_id")

    # Call before_callback_event
    event = graph.before_callback_event()

    # Assert the event is a RunStartedEvent
    assert isinstance(event, RunStartedEvent)

    # Assert the event has the correct run_id and thread_id
    assert event.run_id == graph._run_id
    assert event.thread_id == graph.flow_id
    assert event.thread_id == "test_flow_id"

    # Assert the raw_event contains metrics
    assert event.raw_event is not None
    assert isinstance(event.raw_event, dict)

    # Assert the raw_event contains timestamp
    assert "timestamp" in event.raw_event
    assert isinstance(event.raw_event["timestamp"], float)

    # Assert the raw_event contains total_components
    assert "total_components" in event.raw_event
    assert event.raw_event["total_components"] == len(graph.vertices)
    assert event.raw_event["total_components"] == 2  # chat_input and chat_output


def test_graph_after_callback_event():
    """Test that after_callback_event generates the correct RunFinishedEvent payload."""
    # Create a simple graph with two components and a flow_id
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    graph = Graph(chat_input, chat_output, flow_id="test_flow_id")

    # Call after_callback_event
    event = graph.after_callback_event(result="test_result")

    # Assert the event is a RunFinishedEvent
    assert isinstance(event, RunFinishedEvent)

    # Assert the event has the correct run_id and thread_id
    assert event.run_id == graph._run_id
    assert event.thread_id == graph.flow_id
    assert event.thread_id == "test_flow_id"

    # Assert the result is None (as per the implementation)
    assert event.result is None

    # Assert the raw_event contains metrics
    assert event.raw_event is not None
    assert isinstance(event.raw_event, dict)

    # Assert the raw_event contains timestamp
    assert "timestamp" in event.raw_event
    assert isinstance(event.raw_event["timestamp"], float)

    # Assert the raw_event contains total_components
    assert "total_components" in event.raw_event
    assert event.raw_event["total_components"] == len(graph.vertices)
    assert event.raw_event["total_components"] == 2  # chat_input and chat_output


def test_graph_raw_event_metrics():
    """Test that raw_event_metrics generates the correct metrics dictionary."""
    # Create a simple graph with flow_id
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    graph = Graph(chat_input, chat_output, flow_id="test_flow_id")

    # Call raw_event_metrics with optional fields
    metrics = graph.raw_event_metrics({"custom_field": "custom_value"})

    # Assert metrics is a dictionary
    assert isinstance(metrics, dict)

    # Assert timestamp is present and is a float
    assert "timestamp" in metrics
    assert isinstance(metrics["timestamp"], float)

    # Assert custom field is present
    assert "custom_field" in metrics
    assert metrics["custom_field"] == "custom_value"


def test_graph_raw_event_metrics_no_optional_fields():
    """Test that raw_event_metrics works without optional fields."""
    # Create a simple graph with flow_id
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    graph = Graph(chat_input, chat_output, flow_id="test_flow_id")

    # Call raw_event_metrics without optional fields
    metrics = graph.raw_event_metrics()

    # Assert metrics is a dictionary
    assert isinstance(metrics, dict)

    # Assert timestamp is present and is a float
    assert "timestamp" in metrics
    assert isinstance(metrics["timestamp"], float)

    # Assert only timestamp is present (no optional fields)
    assert len(metrics) == 1
