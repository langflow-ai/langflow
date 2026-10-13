"""Event consumers own the lifetime of the real LangChain producer stream."""

import asyncio
import sys
from types import SimpleNamespace
from uuid import uuid4

import anyio
import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import StructuredTool
from lfx.base.agents.events import AgentPausedError, ExceptionWithMessageError, process_agent_events
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


@pytest.mark.parametrize("adapted", [False, True], ids=["executor", "graph"])
@pytest.mark.parametrize("cancelled", [False, True], ids=["send-error", "consumer-cancel"])
async def test_initial_message_failure_closes_prestarted_producer(adapted, cancelled):
    started = asyncio.Event()
    closed = asyncio.Event()
    publishing = asyncio.Event()
    release = asyncio.Event()

    async def lookup(query: str) -> str:
        """Keep a real LangChain tool running until its owner closes it."""
        started.set()
        try:
            await release.wait()
            return query
        finally:
            await asyncio.sleep(0)
            closed.set()

    failure = RuntimeError("initial publication failed")

    async def send(**_kwargs):
        publishing.set()
        if cancelled:
            await release.wait()
        raise failure

    source = StructuredTool.from_function(coroutine=lookup).astream_events({"query": "hello"}, version="v2")
    stream = adapt_graph_events_to_executor_shape(source) if adapted else source
    task = None
    try:
        await asyncio.wait_for(anext(stream), timeout=2)
        await asyncio.wait_for(started.wait(), timeout=2)
        task = asyncio.create_task(process_agent_events(stream, Message(text=""), send))
        await asyncio.wait_for(publishing.wait(), timeout=2)
        if cancelled:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=2)
        else:
            with pytest.raises(RuntimeError) as raised:
                await asyncio.wait_for(task, timeout=2)
            assert raised.value is failure
        assert closed.is_set(), "initial publication must not leave the prestarted producer running"
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await stream.aclose()
        await source.aclose()
        release.set()


class CloseFailureStream:
    """Inject a close failure independently of event consumption."""

    def __init__(self, events, close_error, source_error=None):
        self.events = iter(events)
        self.close_error = close_error
        self.source_error = source_error
        self.close_calls = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        event = next(self.events, None)
        if event is not None:
            return event
        if self.source_error is not None:
            raise self.source_error
        raise StopAsyncIteration

    async def aclose(self):
        self.close_calls += 1
        await asyncio.sleep(0)
        raise self.close_error


@pytest.mark.parametrize("consumer", ["executor", "adapter"])
@pytest.mark.parametrize("failure_kind", ["handler", "source", "cancel", "close-only"])
@pytest.mark.parametrize("close_error_type", [RuntimeError, asyncio.CancelledError])
async def test_close_failure_preserves_primary_error(consumer, failure_kind, close_error_type, monkeypatch):
    primary_error = (
        asyncio.CancelledError("consumer cancelled") if failure_kind == "cancel" else ValueError("source failed")
    )
    close_error = close_error_type("close failed")
    events = []
    source_error = primary_error if failure_kind in {"source", "cancel"} else None
    if failure_kind == "handler":
        if consumer == "executor":
            events = [{"event": "on_tool_start", "name": "lookup", "run_id": "tool", "data": {"input": "hello"}}]
        else:
            events = [{"event": "on_chain_start", "run_id": "graph", "data": {"input": {"messages": 1}}}]
    stream = CloseFailureStream(events, close_error, source_error)
    logged = []

    def log_exception(message):
        logged.append((message, sys.exc_info()[1]))

    module = (
        "lfx.base.agents.events"
        if consumer == "executor"
        else "lfx.components.models_and_agents.agent_helpers.graph_event_adapter"
    )
    monkeypatch.setattr(f"{module}.logger", SimpleNamespace(exception=log_exception), raising=False)

    async def send(*, message, **kwargs):
        if failure_kind == "handler" and kwargs.get("skip_db_update"):
            raise primary_error
        return message

    async def consume():
        if consumer == "executor":
            await process_agent_events(stream, Message(text=""), send)
        else:
            async for _event in adapt_graph_events_to_executor_shape(stream):
                pass

    expected = (
        close_error_type
        if failure_kind == "close-only"
        else (
            asyncio.CancelledError
            if failure_kind == "cancel"
            else ExceptionWithMessageError
            if consumer == "executor"
            else TypeError
            if failure_kind == "handler"
            else ValueError
        )
    )
    with pytest.raises(expected) as raised:
        await consume()
    assert stream.close_calls == 1
    if failure_kind == "close-only":
        assert raised.value is close_error
        assert not logged
    else:
        if consumer == "executor" and failure_kind != "cancel":
            assert raised.value.__cause__ is primary_error
        elif failure_kind != "handler":
            assert raised.value is primary_error
        assert len(logged) == 1
        assert logged[0][1] is close_error


@pytest.mark.parametrize("close_error_type", [RuntimeError, asyncio.CancelledError])
async def test_explicit_adapter_close_does_not_hide_close_failure(close_error_type):
    close_error = close_error_type("close failed")
    source = CloseFailureStream([{"event": "unhandled"}], close_error)
    stream = adapt_graph_events_to_executor_shape(source)
    await anext(stream)
    with pytest.raises(close_error_type) as raised:
        await stream.aclose()
    assert raised.value is close_error
    assert source.close_calls == 1


@pytest.mark.parametrize("close_error_type", [RuntimeError, asyncio.CancelledError])
async def test_source_generator_exit_is_not_replaced_by_consumer_cleanup(close_error_type, monkeypatch):
    primary_error = GeneratorExit()
    stream = CloseFailureStream([], close_error_type("close failed"), primary_error)
    logged = []
    monkeypatch.setattr("lfx.base.agents.events.logger", SimpleNamespace(exception=logged.append), raising=False)

    async def send(*, message, **_kwargs):
        return message

    with pytest.raises(GeneratorExit) as raised:
        await process_agent_events(stream, Message(text=""), send)
    assert raised.value is primary_error
    assert stream.close_calls == 1
    assert len(logged) == 1


@pytest.mark.parametrize("close_error_type", [RuntimeError, asyncio.CancelledError])
async def test_initial_publication_failure_stays_primary_when_close_fails(close_error_type, monkeypatch):
    primary_error = RuntimeError("initial publication failed")
    close_error = close_error_type("close failed")
    stream = CloseFailureStream([], close_error)
    logged = []

    def log_exception(message):
        logged.append((message, sys.exc_info()[1]))

    monkeypatch.setattr("lfx.base.agents.events.logger", SimpleNamespace(exception=log_exception), raising=False)

    async def send(**_kwargs):
        raise primary_error

    with pytest.raises(RuntimeError) as raised:
        await process_agent_events(stream, Message(text=""), send)
    assert raised.value is primary_error
    assert stream.close_calls == 1
    assert len(logged) == 1
    assert logged[0][1] is close_error


async def test_cleanup_failure_preserves_agent_pause(monkeypatch):
    failure = RuntimeError("close failed")
    stream = CloseFailureStream([], failure)
    logged = []
    monkeypatch.setattr("lfx.base.agents.events.logger", SimpleNamespace(exception=logged.append), raising=False)
    request = {"action_requests": [{"name": "lookup"}]}

    async def send(*, message, **_kwargs):
        return message

    async def pending():
        return request

    with pytest.raises(AgentPausedError) as raised:
        await process_agent_events(stream, Message(text=""), send, get_pending_interrupt=pending)
    assert raised.value.request is request
    assert stream.close_calls == 1
    assert len(logged) == 1


@pytest.mark.parametrize("consumer", ["executor", "adapter"])
@pytest.mark.parametrize("close_error_type", [RuntimeError, asyncio.CancelledError])
async def test_close_failure_is_not_hidden_by_callers_handled_exception(consumer, close_error_type):
    close_error = close_error_type("close failed")
    source = CloseFailureStream([], close_error)

    async def send(*, message, **_kwargs):
        return message

    async def consume():
        if consumer == "executor":
            await process_agent_events(source, Message(text=""), send)
        else:
            async for _event in adapt_graph_events_to_executor_shape(source):
                pass

    try:
        msg = "already handled by caller"
        raise ValueError(msg)
    except ValueError:
        with pytest.raises(close_error_type) as raised:
            await consume()
    assert raised.value is close_error
    assert source.close_calls == 1
