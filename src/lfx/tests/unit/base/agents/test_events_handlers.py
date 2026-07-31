"""Regression tests for the agent event-loop handlers in lfx.base.agents.events.

These pin focused event-loop behaviors:
- handle_on_chain_stream must not run the Message.text setter (which collapses
  interleaved text + tool_use blocks); it stashes the extracted answer in
  data["text"] instead.
- handle_on_tool_start must not clobber a model-end tool_input snapshot with an
  empty on_tool_start payload.
- tool timing must exclude message-publication latency at both the start and
  end boundaries.
- parallel tools must be timed from the matching run's own start event.

The async callbacks are small in-memory harnesses. The timing regression test
advances a deterministic clock while each callback runs.
"""

from time import perf_counter

import lfx.base.agents.events as agent_events
import pytest
from langchain_core.messages import AIMessage
from lfx.base.agents.events import (
    handle_on_chain_stream,
    handle_on_tool_end,
    handle_on_tool_start,
    process_agent_events,
)
from lfx.schema.content_types import TextContent, ToolContent
from lfx.schema.message import Message


async def _passthrough(*, message: Message, **_kwargs) -> Message:
    return message


async def test_chain_stream_preserves_interleaved_blocks():
    """A chunk.output event must not collapse interleaved content_blocks.

    The Message.text setter drops every TextContent and appends one at the end,
    which would fuse ``[text, tool, text]`` into ``[tool, text]``. The handler
    must instead stash the extracted answer in data["text"] and leave
    content_blocks (the source of truth) untouched.
    """
    msg = Message(
        content_blocks=[
            TextContent(text="Let me check"),
            ToolContent(name="search", tool_input={"q": "x"}),
            TextContent(text="Now compute"),
        ],
        sender="Machine",
        sender_name="AI",
    )
    event = {"data": {"chunk": {"output": "Final answer"}}}

    result, _ = await handle_on_chain_stream(event, msg, _passthrough, None, perf_counter())

    block_types = [type(b).__name__ for b in result.content_blocks]
    assert block_types == ["TextContent", "ToolContent", "TextContent"]
    # The extracted answer is stashed for legacy consumers, not folded into a
    # single collapsing TextContent.
    assert result.data[result.text_key] == "Final answer"


async def test_tool_start_does_not_clobber_existing_tool_input():
    """An empty on_tool_start payload must not wipe a real model-end snapshot.

    Providers that already populated the model-end ToolContent.tool_input
    (non-streaming Anthropic) fire on_tool_start with no input. Overwriting
    unconditionally would lose the real args.
    """
    existing = ToolContent(name="search", tool_input={"q": "real query"}, output=None)
    msg = Message(content_blocks=[existing], sender="Machine", sender_name="AI")
    tool_blocks_map: dict = {}
    event = {"name": "search", "data": {"input": None}, "run_id": "r1"}

    result, _ = await handle_on_tool_start(event, msg, tool_blocks_map, _passthrough, perf_counter())

    bound = next(b for b in result.content_blocks if isinstance(b, ToolContent))
    assert bound.tool_input == {"q": "real query"}


async def test_tool_start_overwrites_with_real_input_when_present():
    """When on_tool_start carries the real args, they win over the empty model-end snapshot."""
    existing = ToolContent(name="search", tool_input={}, output=None)
    msg = Message(content_blocks=[existing], sender="Machine", sender_name="AI")
    tool_blocks_map: dict = {}
    event = {"name": "search", "data": {"input": {"q": "streamed"}}, "run_id": "r1"}

    result, _ = await handle_on_tool_start(event, msg, tool_blocks_map, _passthrough, perf_counter())

    bound = next(b for b in result.content_blocks if isinstance(b, ToolContent))
    assert bound.tool_input == {"q": "streamed"}


async def test_tool_duration_excludes_message_callback_latency(monkeypatch):
    """Tool timing must start after and stop before message publication."""
    now = [100.0]
    monkeypatch.setattr(agent_events, "perf_counter", lambda: now[0])

    msg = Message(content_blocks=[], sender="Machine", sender_name="AI")
    tool_blocks_map = {}

    async def _slow_message_callback(*, message: Message, **_kwargs) -> Message:
        now[0] += 5
        return message

    start_event = {
        "name": "search",
        "run_id": "run-1",
        "data": {"input": {"q": "latency"}},
    }
    end_event = {
        "name": "search",
        "run_id": "run-1",
        "data": {"output": "result"},
    }

    msg, tool_start = await handle_on_tool_start(
        start_event,
        msg,
        tool_blocks_map,
        _slow_message_callback,
        100.0,
    )
    assert tool_start == 105.0

    now[0] += 0.025
    result, new_start = await handle_on_tool_end(
        end_event,
        msg,
        tool_blocks_map,
        _slow_message_callback,
        tool_start,
    )

    completed_tool = next(block for block in result.content_blocks if isinstance(block, ToolContent))
    assert completed_tool.duration == 25
    assert new_start == 110.025


@pytest.mark.parametrize(
    ("terminal_events", "expected_durations"),
    [
        ((("run-a", "on_tool_end"), ("run-b", "on_tool_end")), {"a": 3000, "b": 3000}),
        ((("run-b", "on_tool_end"), ("run-a", "on_tool_end")), {"a": 4000, "b": 2000}),
        ((("run-a", "on_tool_error"), ("run-b", "on_tool_end")), {"a": 3000, "b": 3000}),
    ],
)
async def test_parallel_tool_durations_use_matching_run_start(monkeypatch, terminal_events, expected_durations):
    """Each parallel tool must be timed from its own on_tool_start event."""
    now = [0.0]
    monkeypatch.setattr(agent_events, "perf_counter", lambda: now[0])

    start_events = {
        "run-a": {
            "event": "on_tool_start",
            "name": "search",
            "run_id": "run-a",
            "data": {"input": {"q": "a"}},
        },
        "run-b": {
            "event": "on_tool_start",
            "name": "search",
            "run_id": "run-b",
            "data": {"input": {"q": "b"}},
        },
    }

    def _terminal_event(run_id, event_type):
        data = {"error": f"error {run_id}"} if event_type == "on_tool_error" else {"output": f"result {run_id}"}
        return {
            "event": event_type,
            "name": "search",
            "run_id": run_id,
            "data": data,
        }

    timed_events = [
        (1.0, start_events["run-a"]),
        (2.0, start_events["run-b"]),
        (4.0, _terminal_event(*terminal_events[0])),
        (5.0, _terminal_event(*terminal_events[1])),
    ]

    async def _event_iterator():
        for event_time, event in timed_events:
            now[0] = event_time
            yield event

    message = Message(content_blocks=[], sender="Machine", sender_name="AI")
    result = await process_agent_events(_event_iterator(), message, _passthrough)

    durations = {block.tool_input["q"]: block.duration for block in result.content_blocks}
    assert durations == expected_durations


@pytest.mark.parametrize("terminal_event", ["on_tool_end", "on_tool_error"])
@pytest.mark.parametrize("has_tool_start", [True, False], ids=["bound", "unbound"])
async def test_terminal_tool_event_restarts_narration_timer(monkeypatch, terminal_event, has_tool_start):
    """A later model response must not include the preceding tool's execution time."""
    now = [0.0]
    monkeypatch.setattr(agent_events, "perf_counter", lambda: now[0])

    terminal_data = {"error": "tool failed"} if terminal_event == "on_tool_error" else {"output": "result"}
    timed_events = [
        (
            10.0,
            {
                "event": "on_chat_model_end",
                "data": {
                    "output": AIMessage(
                        content=[
                            {"type": "text", "text": "First round"},
                            {"type": "tool_use", "name": "search", "input": {}, "id": "tool-1"},
                        ]
                    )
                },
            },
        ),
    ]
    if has_tool_start:
        timed_events.append(
            (
                10.0,
                {
                    "event": "on_tool_start",
                    "name": "search",
                    "run_id": "run-1",
                    "data": {"input": {"q": "timing"}},
                },
            )
        )
    timed_events.extend(
        [
            (
                20.0,
                {
                    "event": terminal_event,
                    "name": "search",
                    "run_id": "run-1",
                    "data": terminal_data,
                },
            ),
            (
                25.0,
                {
                    "event": "on_chat_model_end",
                    "data": {"output": AIMessage(content=[{"type": "text", "text": "Second round"}])},
                },
            ),
        ]
    )

    async def _event_iterator():
        for event_time, event in timed_events:
            now[0] = event_time
            yield event

    message = Message(content_blocks=[], sender="Machine", sender_name="AI")
    result = await process_agent_events(_event_iterator(), message, _passthrough)

    text_durations = [block.duration for block in result.content_blocks if isinstance(block, TextContent)]
    assert text_durations == [10000, 5000]
