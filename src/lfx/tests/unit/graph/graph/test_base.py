from collections import deque

import pytest
from lfx.components.input_output import ChatInput, ChatOutput, TextOutputComponent
from lfx.graph import Graph
from lfx.graph.graph.constants import Finish
from ag_ui.core import RunStartedEvent, RunFinishedEvent


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
