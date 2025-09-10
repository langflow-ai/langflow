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


# TODO: Move to Langflow tests
@pytest.mark.skip(reason="Temporarily disabled")
def test_graph_set_with_valid_component():
    from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
    from lfx.components.tools.yahoo_finance import YfinanceToolComponent

    tool = YfinanceToolComponent()
    tool_calling_agent = ToolCallingAgentComponent()
    tool_calling_agent.set(tools=[tool])


def test_graph_dump_dynamic_aliases_for_duplicates():
    """Test that graph.dump assigns aliases to duplicate components."""
    from lfx.components.input_output import ChatInput

    # Create graph with duplicate ChatInput components
    graph = Graph()
    input1_id = graph.add_component(ChatInput())
    input2_id = graph.add_component(ChatInput())
    input3_id = graph.add_component(ChatInput())

    # Dump the graph
    graph_data = graph.dump()

    # Verify aliases were assigned
    nodes = graph_data["data"]["nodes"]
    assert len(nodes) == 3

    # Find nodes by ID and check aliases
    node1 = next(n for n in nodes if n["id"] == input1_id)
    node2 = next(n for n in nodes if n["id"] == input2_id)
    node3 = next(n for n in nodes if n["id"] == input3_id)

    assert node1["data"]["node"]["alias"] == "Chat Input#1"
    assert node2["data"]["node"]["alias"] == "Chat Input#2"
    assert node3["data"]["node"]["alias"] == "Chat Input#3"


def test_graph_dump_no_alias_for_single_component():
    """Test that single components don't get aliases."""
    from lfx.components.input_output import ChatInput, ChatOutput

    # Create graph with different component types (no duplicates)
    graph = Graph()
    input_id = graph.add_component(ChatInput())
    output_id = graph.add_component(ChatOutput())

    # Dump the graph
    graph_data = graph.dump()

    # Verify no aliases assigned for single components
    nodes = graph_data["data"]["nodes"]
    assert len(nodes) == 2

    # Find nodes by ID and check no aliases
    input_node = next(n for n in nodes if n["id"] == input_id)
    output_node = next(n for n in nodes if n["id"] == output_id)

    assert input_node["data"]["node"].get("alias") is None
    assert output_node["data"]["node"].get("alias") is None


def test_graph_dump_preserves_existing_aliases():
    """Test that existing aliases are preserved during dump."""
    from lfx.components.input_output import ChatInput

    graph = Graph()
    input1_id = graph.add_component(ChatInput())
    input2_id = graph.add_component(ChatInput())

    # Manually set aliases in the graph data before dump
    graph.raw_graph_data = {
        "nodes": [
            {
                "id": input1_id,
                "data": {
                    "node": {
                        "display_name": "Chat Input",
                        "alias": "MyCustomInput",  # Existing alias
                    }
                },
            },
            {
                "id": input2_id,
                "data": {
                    "node": {
                        "display_name": "Chat Input",
                        "alias": "Chat Input#5",  # Existing numbered alias
                    }
                },
            },
        ],
        "edges": [],
    }

    # Dump should preserve existing aliases
    graph_data = graph.dump()

    nodes = graph_data["data"]["nodes"]
    node1 = next(n for n in nodes if n["id"] == input1_id)
    node2 = next(n for n in nodes if n["id"] == input2_id)

    assert node1["data"]["node"]["alias"] == "MyCustomInput"  # Preserved
    assert node2["data"]["node"]["alias"] == "Chat Input#5"  # Preserved


def test_graph_dump_handles_mixed_scenarios():
    """Test dynamic alias assignment with mixed existing/missing aliases."""
    from lfx.components.input_output import ChatInput

    graph = Graph()
    input1_id = graph.add_component(ChatInput())
    input2_id = graph.add_component(ChatInput())
    input3_id = graph.add_component(ChatInput())

    # Set up mixed scenario: some have aliases, some don't
    graph.raw_graph_data = {
        "nodes": [
            {
                "id": input1_id,
                "data": {
                    "node": {
                        "display_name": "Chat Input",
                        "alias": "Chat Input#1",  # Existing valid alias
                    }
                },
            },
            {
                "id": input2_id,
                "data": {
                    "node": {
                        "display_name": "Chat Input",
                        "alias": None,  # No alias
                    }
                },
            },
            {
                "id": input3_id,
                "data": {
                    "node": {
                        "display_name": "Chat Input",
                        "alias": "OldAlias#7",  # Outdated alias (wrong display name)
                    }
                },
            },
        ],
        "edges": [],
    }

    # Dump should fix missing/incorrect aliases while preserving valid ones
    graph_data = graph.dump()

    nodes = graph_data["data"]["nodes"]
    node1 = next(n for n in nodes if n["id"] == input1_id)
    node2 = next(n for n in nodes if n["id"] == input2_id)
    node3 = next(n for n in nodes if n["id"] == input3_id)

    assert node1["data"]["node"]["alias"] == "Chat Input#1"  # Preserved (valid)
    assert node2["data"]["node"]["alias"] == "Chat Input#2"  # Assigned (was missing)
    assert node3["data"]["node"]["alias"] == "Chat Input#3"  # Updated (was incorrect)


def test_graph_dump_removes_unnecessary_numbered_aliases():
    """Test that single components have #1 aliases removed."""
    from lfx.components.input_output import ChatInput

    graph = Graph()
    input_id = graph.add_component(ChatInput())

    # Set up single component with #1 alias (unnecessary)
    graph.raw_graph_data = {
        "nodes": [
            {
                "id": input_id,
                "data": {
                    "node": {
                        "display_name": "Chat Input",
                        "alias": "Chat Input#1",  # Should be removed (only component)
                    }
                },
            }
        ],
        "edges": [],
    }

    # Dump should remove unnecessary #1 alias
    graph_data = graph.dump()

    node = graph_data["data"]["nodes"][0]
    assert node["data"]["node"].get("alias") is None  # Removed #1


def test_graph_dump_preserves_custom_single_aliases():
    """Test that non-numbered single aliases are preserved."""
    from lfx.components.input_output import ChatInput

    graph = Graph()
    input_id = graph.add_component(ChatInput())

    # Set up single component with custom alias
    graph.raw_graph_data = {
        "nodes": [
            {
                "id": input_id,
                "data": {
                    "node": {
                        "display_name": "Chat Input",
                        "alias": "MyCustomInput",  # Should be preserved
                    }
                },
            }
        ],
        "edges": [],
    }

    # Dump should preserve custom alias
    graph_data = graph.dump()

    node = graph_data["data"]["nodes"][0]
    assert node["data"]["node"]["alias"] == "MyCustomInput"  # Preserved
