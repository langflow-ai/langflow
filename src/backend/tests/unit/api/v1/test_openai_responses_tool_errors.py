"""Failed agent tool calls must reach OpenAI Responses API consumers.

The stream converter used to emit a ``function_call`` item only once a tool step carried an
``output``. A failed tool never gets one (only ``error``), so the call was dropped from the
stream and only ever showed up in the persisted chat history. These tests drive the real
event pipeline (event manager -> v1 projection -> converter) with the agent's live
``Message`` shape and pin the contract:

- an output-less error is a failure: emitted once, ``status="failed"``, ``error`` text;
- an output wins over a stale error (a retried call that eventually succeeded);
- the error text follows the endpoint's ownership policy: owners see the tool's message,
  delegated callers a safe one;
- the ``tool_call.results`` form and the non-streaming path share the contract.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.utils.execution_errors import SAFE_TOOL_ERROR_MESSAGE
from langflow.api.v1 import openai_responses
from langflow.schema import OpenAIResponsesRequest
from lfx.schema.content_types import TextContent, ToolContent
from lfx.schema.message import Message

TOOL_NAME = "run_other_flow"
TOOL_INPUT = {"query": "components in openrag"}
TOOL_ERROR = "Tool 'run_other_flow' execution failed: MCP tool 'run_other_flow' failed: inner flow raised"
TOOL_OUTPUT = "3 documents"


def _flow(owner_id):
    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        workspace_id=None,
        folder_id=None,
        data={"nodes": [{"data": {"type": "ChatInput"}}, {"data": {"type": "ChatOutput"}}]},
    )


def _agent_message(tool_block: ToolContent, *, state: str, text: str = "") -> Message:
    blocks: list = [tool_block]
    if text:
        blocks.append(TextContent(text=text))
    return Message(
        sender="Machine",
        sender_name="AI",
        text="",
        content_blocks=blocks,
        properties={"icon": "Bot", "state": state},
        session_id="session-1",
        id=str(uuid4()),
    )


def _failed_tool_block() -> ToolContent:
    return ToolContent(
        name=TOOL_NAME,
        tool_input=TOOL_INPUT,
        output=None,
        error=TOOL_ERROR,
        header={"title": f"Error using **{TOOL_NAME}**", "icon": "Hammer"},
        duration=12,
    )


def _retried_then_succeeded_block() -> ToolContent:
    """The shape ToolRetryMiddleware leaves behind: attempt 1 errored, attempt 2 succeeded.

    handle_on_tool_start rebinds the same output-less block for the retry and
    handle_on_tool_end then fills ``output`` without clearing the earlier ``error``.
    """
    return ToolContent(
        name=TOOL_NAME,
        tool_input=TOOL_INPUT,
        output=TOOL_OUTPUT,
        error="Tool 'run_other_flow' execution failed: transient upstream timeout",
        header={"title": f"Executed **{TOOL_NAME}**", "icon": "Hammer"},
        duration=40,
    )


def _fake_run_flow_generator(frames: list[Message]):
    """Stand in for run_flow_generator: publish the agent frames through the real event manager."""

    async def run(**kwargs):
        event_manager = kwargs["event_manager"]
        for frame in frames:
            event_manager.on_message(data=frame.model_dump())
        await event_manager.queue.put((None, None, time.time()))

    return run


def _parse_sse(wire: str) -> list[dict]:
    events = []
    for chunk in wire.split("\n\n"):
        lines = [line for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        event_name = None
        data = None
        for line in lines:
            if line.startswith("event: "):
                event_name = line[len("event: ") :]
            elif line.startswith("data: "):
                payload = line[len("data: ") :]
                if payload != "[DONE]":
                    data = json.loads(payload)
        events.append({"event": event_name, "data": data})
    return events


async def _stream(
    monkeypatch: pytest.MonkeyPatch,
    frames: list[Message],
    *,
    include: list[str] | None = None,
    caller: str = "owner",
) -> list[dict]:
    owner_id = uuid4()
    flow = _flow(owner_id)
    monkeypatch.setattr(openai_responses, "run_flow_generator", _fake_run_flow_generator(frames))
    request = OpenAIResponsesRequest(model=str(flow.id), input="run the flow", stream=True, include=include)
    response = await openai_responses.run_flow_for_openai_responses(
        flow=flow,
        request=request,
        api_key_user=SimpleNamespace(id=owner_id if caller == "owner" else uuid4()),
        stream=True,
    )
    wire = "".join([chunk async for chunk in response.body_iterator])
    return _parse_sse(wire)


def _tool_events(events: list[dict]) -> tuple[list[dict], list[dict]]:
    added = [e["data"] for e in events if e["event"] == "response.output_item.added"]
    done = [e["data"] for e in events if e["event"] == "response.output_item.done"]
    return added, done


async def test_stream_emits_failed_tool_call_as_function_call(monkeypatch: pytest.MonkeyPatch) -> None:
    block = _failed_tool_block()
    frames = [
        _agent_message(block, state="partial"),
        _agent_message(block, state="complete", text="The flow failed, so I could not answer."),
    ]

    events = await _stream(monkeypatch, frames)
    added, done = _tool_events(events)

    # Emitted exactly once even though the same step is published in every frame.
    assert len(added) == 1
    assert added[0]["item"]["type"] == "function_call"
    assert added[0]["item"]["name"] == TOOL_NAME
    assert added[0]["item"]["status"] == "in_progress"

    arg_events = [e["data"] for e in events if e["event"] == "response.function_call_arguments.done"]
    assert len(arg_events) == 1
    assert json.loads(arg_events[0]["arguments"]) == TOOL_INPUT

    assert len(done) == 1
    item = done[0]["item"]
    assert item["type"] == "function_call"
    assert item["name"] == TOOL_NAME
    assert item["status"] == "failed"
    assert item["error"] == TOOL_ERROR
    assert item["call_id"] == added[0]["item"]["call_id"]

    # The stream still terminates normally.
    assert any(e["event"] == "response.completed" for e in events)


async def test_stream_emits_failed_tool_call_with_results_form(monkeypatch: pytest.MonkeyPatch) -> None:
    block = _failed_tool_block()
    frames = [_agent_message(block, state="complete", text="done")]

    events = await _stream(monkeypatch, frames, include=["tool_call.results"])
    _added, done = _tool_events(events)

    assert len(done) == 1
    item = done[0]["item"]
    assert item["type"] == "tool_call"
    assert item["tool_name"] == TOOL_NAME
    assert item["inputs"] == TOOL_INPUT
    assert item["status"] == "failed"
    assert item["results"] == []
    assert item["error"] == TOOL_ERROR


@pytest.mark.parametrize("include", [None, ["tool_call.results"]])
async def test_stream_retried_tool_call_that_succeeded_is_completed(
    monkeypatch: pytest.MonkeyPatch, include: list[str] | None
) -> None:
    """Output wins over a stale error: the call did complete, so its result must not be hidden."""
    frames = [_agent_message(_retried_then_succeeded_block(), state="complete", text="Found 3 documents.")]

    events = await _stream(monkeypatch, frames, include=include)
    _added, done = _tool_events(events)

    assert len(done) == 1
    item = done[0]["item"]
    assert item["status"] == "completed"
    assert "error" not in item
    if include:
        assert item["type"] == "tool_call"
        assert item["results"] == TOOL_OUTPUT
    else:
        assert item["type"] == "function_call"


async def test_stream_redacts_tool_error_for_delegated_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller who does not own the flow gets the same safe message policy as execution errors."""
    frames = [_agent_message(_failed_tool_block(), state="complete", text="done")]

    events = await _stream(monkeypatch, frames, include=["tool_call.results"], caller="delegate")
    _added, done = _tool_events(events)

    assert len(done) == 1
    item = done[0]["item"]
    assert item["status"] == "failed"
    assert item["error"] == SAFE_TOOL_ERROR_MESSAGE
    assert TOOL_ERROR not in json.dumps(events)


async def test_stream_skips_in_flight_tool_call_until_it_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    """A step with neither output nor error is still running and must not be emitted yet."""
    running = ToolContent(name=TOOL_NAME, tool_input=TOOL_INPUT, output=None, error=None)
    frames = [_agent_message(running, state="partial")]

    events = await _stream(monkeypatch, frames)
    added, done = _tool_events(events)

    assert added == []
    assert done == []


async def test_stream_successful_tool_call_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    succeeded = ToolContent(name=TOOL_NAME, tool_input=TOOL_INPUT, output=TOOL_OUTPUT, error=None, duration=5)
    frames = [_agent_message(succeeded, state="complete", text="Found 3 documents.")]

    events = await _stream(monkeypatch, frames)
    added, done = _tool_events(events)

    assert len(added) == 1
    assert len(done) == 1
    assert done[0]["item"]["status"] == "completed"
    assert "error" not in done[0]["item"]


async def _non_stream(monkeypatch: pytest.MonkeyPatch, block: ToolContent, *, include, caller: str = "owner"):
    owner_id = uuid4()
    flow = _flow(owner_id)
    message = _agent_message(block, state="complete", text="The flow failed.")
    component_output = SimpleNamespace(
        results={"message": message},
        messages=[SimpleNamespace(message="The flow failed.")],
    )
    result = SimpleNamespace(outputs=[SimpleNamespace(outputs=[component_output])])
    monkeypatch.setattr(openai_responses, "simple_run_flow", AsyncMock(return_value=result))

    response = await openai_responses.run_flow_for_openai_responses(
        flow=flow,
        request=OpenAIResponsesRequest(model=str(flow.id), input="run the flow", stream=False, include=include),
        api_key_user=SimpleNamespace(id=owner_id if caller == "owner" else uuid4()),
        stream=False,
    )
    tool_items = [item for item in response.output if item["type"] in {"function_call", "tool_call"}]
    assert response.output[-1]["type"] == "message"
    return tool_items


@pytest.mark.parametrize("include", [None, ["tool_call.results"]])
async def test_non_stream_marks_failed_tool_call(monkeypatch: pytest.MonkeyPatch, include: list[str] | None) -> None:
    tool_items = await _non_stream(monkeypatch, _failed_tool_block(), include=include)

    assert len(tool_items) == 1
    item = tool_items[0]
    assert item["status"] == "failed"
    assert item["error"] == TOOL_ERROR
    if include:
        assert item["type"] == "tool_call"
        assert item["results"] == []
    else:
        assert item["type"] == "function_call"
        assert json.loads(item["arguments"]) == TOOL_INPUT


async def test_non_stream_retried_tool_call_that_succeeded_is_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    tool_items = await _non_stream(monkeypatch, _retried_then_succeeded_block(), include=["tool_call.results"])

    assert len(tool_items) == 1
    assert tool_items[0]["status"] == "completed"
    assert tool_items[0]["results"] == TOOL_OUTPUT
    assert "error" not in tool_items[0]


async def test_non_stream_redacts_tool_error_for_delegated_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    tool_items = await _non_stream(monkeypatch, _failed_tool_block(), include=None, caller="delegate")

    assert len(tool_items) == 1
    assert tool_items[0]["status"] == "failed"
    assert tool_items[0]["error"] == SAFE_TOOL_ERROR_MESSAGE
