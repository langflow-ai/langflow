"""Tests for adapt_graph_events_to_executor_shape — re-shape LangGraph events.

`langchain.agents.create_agent` returns a `CompiledStateGraph` whose `astream_events`
emits the outermost chain start with `data.input = {"messages": [...]}` and the chain
end with `data.output = {"messages": [..., AIMessage]}`.

The existing `process_agent_events` in `lfx.base.agents.events` was written for the legacy
`AgentExecutor` event shape (`{"input": str, "chat_history": [...]}` / `AgentFinish`).
This adapter translates ONLY the outermost graph events into that shape so the existing
event processor can be reused unchanged. Tool events, streaming events, and nested chain
events from inner graph nodes pass through untouched.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from langchain_core.agents import AgentFinish
from langchain_core.messages import AIMessage, HumanMessage
from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import (
    adapt_graph_events_to_executor_shape,
)


async def _stream(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for event in events:
        yield event


async def _collect(stream: AsyncIterator[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event async for event in stream]


@pytest.mark.asyncio
async def test_should_reshape_outermost_on_chain_start_to_executor_input_dict_shape() -> None:
    """Graph emits `data.input = {"messages": [...]}`; adapter must produce executor shape."""
    history = [
        HumanMessage(content="hello earlier"),
        AIMessage(content="hi back"),
    ]
    user_msg = HumanMessage(content="what's the weather?")
    graph_event = {
        "event": "on_chain_start",
        "name": "LangGraph",
        "run_id": "outer-1",
        "data": {"input": {"messages": [*history, user_msg]}},
    }

    result = await _collect(adapt_graph_events_to_executor_shape(_stream([graph_event])))

    assert len(result) == 1
    assert result[0]["event"] == "on_chain_start"
    assert result[0]["run_id"] == "outer-1"
    reshaped_input = result[0]["data"]["input"]
    assert isinstance(reshaped_input, dict)
    assert reshaped_input["input"] == "what's the weather?"
    assert reshaped_input["chat_history"] == history


@pytest.mark.asyncio
async def test_should_pass_tool_events_through_unchanged() -> None:
    """Tool events have the same shape from both AgentExecutor and CompiledStateGraph."""
    tool_start = {
        "event": "on_tool_start",
        "name": "calculator",
        "run_id": "tool-run-1",
        "data": {"input": {"expression": "2+2"}},
    }
    tool_end = {
        "event": "on_tool_end",
        "name": "calculator",
        "run_id": "tool-run-1",
        "data": {"output": "4"},
    }

    result = await _collect(adapt_graph_events_to_executor_shape(_stream([tool_start, tool_end])))

    assert result == [tool_start, tool_end]


@pytest.mark.asyncio
async def test_should_pass_chat_model_stream_events_through_unchanged() -> None:
    """Streaming chunks from the LLM must reach handle_on_chain_stream untouched."""
    chunk_event = {
        "event": "on_chat_model_stream",
        "name": "ChatAnthropic",
        "run_id": "model-run-1",
        "data": {"chunk": "anything"},
    }

    result = await _collect(adapt_graph_events_to_executor_shape(_stream([chunk_event])))

    assert result == [chunk_event]


@pytest.mark.asyncio
async def test_should_pass_nested_chain_events_through_unchanged() -> None:
    """Inner graph nodes / retrievers emit `on_chain_start`/`on_chain_end` with different run_ids.

    Only the OUTERMOST chain (first run_id seen) gets re-shaped — inner ones must pass
    through verbatim or process_agent_events will receive double-translated nonsense.
    """
    outer_start = {
        "event": "on_chain_start",
        "name": "LangGraph",
        "run_id": "outer-1",
        "data": {"input": {"messages": [HumanMessage(content="hi")]}},
    }
    inner_start = {
        "event": "on_chain_start",
        "name": "agent_node",  # an inner LangGraph node
        "run_id": "inner-1",
        "data": {"input": {"some": "nested-shape"}},
    }
    inner_end = {
        "event": "on_chain_end",
        "name": "agent_node",
        "run_id": "inner-1",
        "data": {"output": {"messages": [AIMessage(content="inner")]}},
    }

    result = await _collect(adapt_graph_events_to_executor_shape(_stream([outer_start, inner_start, inner_end])))

    assert len(result) == 3
    # Outer was reshaped (input is now executor shape, not the raw graph input).
    assert isinstance(result[0]["data"]["input"], dict)
    assert "input" in result[0]["data"]["input"]
    # Inner events are byte-for-byte identical to what came in.
    assert result[1] == inner_start
    assert result[2] == inner_end


@pytest.mark.asyncio
async def test_should_reshape_outermost_on_chain_end_to_agent_finish() -> None:
    """Graph emits `data.output = {"messages": [..., AIMessage]}`; adapter must wrap in AgentFinish."""
    final_text = "The weather is sunny."
    final_state = {
        "messages": [
            HumanMessage(content="what's the weather?"),
            AIMessage(content=final_text),
        ]
    }
    start_event = {
        "event": "on_chain_start",
        "name": "LangGraph",
        "run_id": "outer-1",
        "data": {"input": {"messages": [HumanMessage(content="what's the weather?")]}},
    }
    end_event = {
        "event": "on_chain_end",
        "name": "LangGraph",
        "run_id": "outer-1",
        "data": {"output": final_state},
    }

    result = await _collect(adapt_graph_events_to_executor_shape(_stream([start_event, end_event])))

    assert len(result) == 2
    end = result[1]
    assert end["event"] == "on_chain_end"
    assert end["run_id"] == "outer-1"
    output = end["data"]["output"]
    assert isinstance(output, AgentFinish)
    assert output.return_values == {"output": final_text}
