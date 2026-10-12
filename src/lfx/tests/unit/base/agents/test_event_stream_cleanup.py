"""Event consumers own the lifetime of the real LangChain producer stream."""

import asyncio
from uuid import uuid4

import anyio
import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import StructuredTool
from lfx.base.agents.events import ExceptionWithMessageError, process_agent_events
from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import (
    adapt_graph_events_to_executor_shape,
)
from lfx.schema.message import Message


class ToolCallingChatModel(FakeMessagesListChatModel):
    def bind_tools(self, _tools, **_kwargs):
        return self


@pytest.mark.parametrize("adapted", [False, True], ids=["executor", "graph"])
async def test_token_delivery_failure_closes_running_producer(adapted):
    started = asyncio.Event()
    closed = asyncio.Event()
    release = asyncio.Event()

    async def model(_input):
        try:
            yield AIMessageChunk(content="first token")
            started.set()
            await release.wait()
        finally:
            closed.set()

    async def send(*, message, **_kwargs):
        return message

    def send_token(**_kwargs):
        msg = "token delivery failed"
        raise RuntimeError(msg)

    source = RunnableLambda(model).astream_events("hello", version="v2")
    stream = adapt_graph_events_to_executor_shape(source) if adapted else source
    try:
        with pytest.raises(ExceptionWithMessageError, match="token delivery failed"):
            await asyncio.wait_for(
                process_agent_events(stream, Message(text="", id=str(uuid4())), send, send_token),
                timeout=2,
            )
        assert started.is_set()
        assert closed.is_set(), "the model producer must stop before the consumer exits"
    finally:
        await stream.aclose()
        await source.aclose()
        release.set()


@pytest.mark.parametrize("engine", ["executor", "adapter", "agent"])
@pytest.mark.parametrize("cancelled", [False, True], ids=["send-error", "consumer-cancel"])
async def test_message_callback_exit_closes_running_tool(engine, cancelled):
    started = asyncio.Event()
    closed = asyncio.Event()
    publishing = asyncio.Event()
    release = asyncio.Event()

    async def lookup(query: str) -> str:
        """Wait for an external tool response."""
        started.set()
        try:
            await release.wait()
            return query
        finally:
            closed.set()

    async def send(*, message, **kwargs):
        if kwargs.get("skip_db_update"):
            await started.wait()
            publishing.set()
            if cancelled:
                await release.wait()
            msg = "message delivery failed"
            raise RuntimeError(msg)
        return message

    tool = StructuredTool.from_function(coroutine=lookup)
    if engine == "agent":
        model = ToolCallingChatModel(
            responses=[
                AIMessage(content="", tool_calls=[{"name": "lookup", "args": {"query": "hello"}, "id": "call-1"}]),
                AIMessage(content="done"),
            ]
        )
        source = create_agent(model, tools=[tool]).astream_events(
            {"messages": [HumanMessage(content="hello")]}, version="v2"
        )
    else:
        source = tool.astream_events({"query": "hello"}, version="v2")
    stream = source if engine == "executor" else adapt_graph_events_to_executor_shape(source)
    task = asyncio.create_task(process_agent_events(stream, Message(text=""), send))
    try:
        await asyncio.wait_for(publishing.wait(), timeout=2)
        if cancelled:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=2)
        else:
            with pytest.raises(ExceptionWithMessageError, match="message delivery failed"):
                await asyncio.wait_for(task, timeout=2)
        assert closed.is_set(), "the tool must stop before the consumer exits"
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await stream.aclose()
        await source.aclose()
        release.set()


async def test_closing_graph_adapter_closes_its_source():
    closed = asyncio.Event()

    async def source():
        try:
            yield {"event": "on_chain_start", "run_id": "run", "data": {"input": {"messages": []}}}
            await asyncio.Event().wait()
        finally:
            closed.set()

    inner = source()
    stream = adapt_graph_events_to_executor_shape(inner)
    try:
        await anext(stream)
        await stream.aclose()
        assert closed.is_set()
    finally:
        await inner.aclose()


@pytest.mark.parametrize("adapted", [False, True], ids=["executor", "graph"])
async def test_cancel_scope_allows_tool_cleanup_to_await(adapted):
    started = asyncio.Event()
    closed = asyncio.Event()
    release = asyncio.Event()

    async def lookup(query: str) -> str:
        """Wait for an external response and close it asynchronously."""
        started.set()
        try:
            await release.wait()
            return query
        finally:
            await asyncio.sleep(0)
            closed.set()

    async def send(*, message, **kwargs):
        if kwargs.get("skip_db_update"):
            await started.wait()
            scope.cancel()
            await anyio.lowlevel.checkpoint()
        return message

    source = StructuredTool.from_function(coroutine=lookup).astream_events({"query": "hello"}, version="v2")
    stream = adapt_graph_events_to_executor_shape(source) if adapted else source
    try:
        with anyio.fail_after(2), anyio.CancelScope() as scope:
            await process_agent_events(stream, Message(text=""), send)
        assert closed.is_set(), "response-scope cancellation must not interrupt tool cleanup"
    finally:
        await stream.aclose()
        await source.aclose()
        release.set()


@pytest.mark.parametrize("adapted", [False, True], ids=["executor", "graph"])
@pytest.mark.parametrize("failed", [False, True], ids=["success", "source-error"])
async def test_tool_completion_and_errors_are_preserved(adapted, failed):
    closed = asyncio.Event()

    async def lookup(query: str) -> str:
        """Return a tool result or raise its original error."""
        try:
            if failed:
                msg = "tool failed"
                raise RuntimeError(msg)
            return query
        finally:
            closed.set()

    async def send(*, message, **_kwargs):
        return message

    source = StructuredTool.from_function(coroutine=lookup).astream_events({"query": "hello"}, version="v2")
    stream = adapt_graph_events_to_executor_shape(source) if adapted else source
    if failed:
        with pytest.raises(ExceptionWithMessageError, match="tool failed"):
            await process_agent_events(stream, Message(text=""), send)
    else:
        result = await process_agent_events(stream, Message(text=""), send)
        assert result.properties.state == "complete"
        assert len(result.content_blocks) == 1
        assert result.content_blocks[0].output == "hello"
    assert closed.is_set()


@pytest.mark.parametrize("adapted", [False, True], ids=["executor", "graph"])
async def test_non_closeable_event_iterator_still_completes(adapted):
    class Events:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    async def send(*, message, **_kwargs):
        return message

    source = Events()
    stream = adapt_graph_events_to_executor_shape(source) if adapted else source
    result = await process_agent_events(stream, Message(text="answer"), send)
    assert result.text == "answer"
    assert result.properties.state == "complete"
