from collections import deque

import pytest
from lfx.components.input_output import ChatInput, ChatOutput, TextOutputComponent
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
    # Create a simple graph structure:
    # chat_input -> text_output -> chat_output
    # chat_input -> standalone_output
    #
    # Terminal nodes should be: chat_output, standalone_output

    chat_input = ChatInput(_id="chat_input")
    text_output = TextOutputComponent(_id="text_output")
    chat_output = ChatOutput(_id="chat_output")
    standalone_output = TextOutputComponent(_id="standalone_output")

    # Set up connections
    text_output.set(input_value=chat_input.message_response)
    chat_output.set(input_value=text_output.text_response)
    standalone_output.set(input_value=chat_input.message_response)

    # Create graph and add components
    graph = Graph()
    input_id = graph.add_component(chat_input)
    text_id = graph.add_component(text_output)
    output_id = graph.add_component(chat_output)
    standalone_id = graph.add_component(standalone_output)

    # Add edges: input -> text -> output, input -> standalone
    graph.add_component_edge(input_id, ("message", "input_value"), text_id)
    graph.add_component_edge(text_id, ("text", "input_value"), output_id)
    graph.add_component_edge(input_id, ("message", "input_value"), standalone_id)

    # Initialize graph to build successor_map
    graph.initialize()

    # Test get_terminal_nodes
    terminal_nodes = graph.get_terminal_nodes()

    # Should return the two terminal nodes (no outgoing edges)
    expected_terminal_nodes = {output_id, standalone_id}
    actual_terminal_nodes = set(terminal_nodes)

    assert actual_terminal_nodes == expected_terminal_nodes, (
        f"Expected terminal nodes {expected_terminal_nodes}, got {actual_terminal_nodes}"
    )

    # Verify non-terminal nodes are not included
    assert input_id not in terminal_nodes, "Input node should not be terminal (has outgoing edges)"
    assert text_id not in terminal_nodes, "Text node should not be terminal (has outgoing edges)"


def test_get_terminal_nodes_single_node():
    """Test get_terminal_nodes with a single isolated node."""
    chat_input = ChatInput(_id="single_node")

    graph = Graph()
    node_id = graph.add_component(chat_input)
    graph.initialize()

    terminal_nodes = graph.get_terminal_nodes()

    # Single isolated node should be terminal
    assert terminal_nodes == [node_id], f"Expected [{node_id}], got {terminal_nodes}"


def test_get_terminal_nodes_linear_chain():
    """Test get_terminal_nodes with a linear chain of nodes."""
    # Create: A -> B -> C -> D
    # Only D should be terminal

    components = [
        ChatInput(_id="node_a"),
        TextOutputComponent(_id="node_b"),
        TextOutputComponent(_id="node_c"),
        ChatOutput(_id="node_d"),
    ]

    graph = Graph()
    node_ids = [graph.add_component(comp) for comp in components]

    # Set up linear chain connections
    components[1].set(input_value=components[0].message_response)
    components[2].set(input_value=components[1].text_response)
    components[3].set(input_value=components[2].text_response)

    # Add edges: A -> B -> C -> D
    for i in range(len(node_ids) - 1):
        if i == 0:
            output_name, input_name = "message", "input_value"
        else:
            output_name, input_name = "text", "input_value"
        graph.add_component_edge(node_ids[i], (output_name, input_name), node_ids[i + 1])

    graph.initialize()

    terminal_nodes = graph.get_terminal_nodes()

    # Only the last node should be terminal
    assert terminal_nodes == [node_ids[-1]], f"Expected only [{node_ids[-1]}] to be terminal, got {terminal_nodes}"


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
