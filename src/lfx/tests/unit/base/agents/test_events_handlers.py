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
- handle_on_chat_model_end must keep the plain-string items of a list content,
  which a stream that mixes string and text-dict chunks aggregates into.

The async callbacks are small in-memory harnesses. The timing regression test
advances a deterministic clock while each callback runs.
"""

from time import perf_counter

import lfx.base.agents.events as agent_events
import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from lfx.base.agents.events import (
    handle_on_chain_stream,
    handle_on_chat_model_end,
    handle_on_tool_end,
    handle_on_tool_error,
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


@pytest.mark.parametrize(
    "chunks",
    [
        [[{"type": "text", "text": "Echo: hello m", "extras": {"signature": "SIG"}}], "cp (probe-0-1)"],
        ["Echo: hello m", "cp (probe-0-1)", [{"type": "text", "text": "", "extras": {"signature": "SIG"}}]],
    ],
    ids=["dict-then-string", "string-then-signed-empty-dict"],
)
async def test_chat_model_end_keeps_string_chunks_of_mixed_content(chunks):
    """A stream mixing string and text-dict chunks aggregates into a mixed list; no part of the answer may be lost."""
    aggregated = AIMessageChunk(content=chunks[0])
    for chunk in chunks[1:]:
        aggregated += AIMessageChunk(content=chunk)
    assert any(isinstance(item, str) for item in aggregated.content)

    message = Message(text="", content_blocks=[], sender="Machine")
    result, _ = await handle_on_chat_model_end({"data": {"output": aggregated}}, message, _passthrough, None, 0.0)

    assert result.text == "Echo: hello mcp (probe-0-1)"
    # One block, not one per chunk: interleaved rendering paints each TextContent on its own.
    assert [block.text for block in result.content_blocks] == ["Echo: hello mcp (probe-0-1)"]


async def test_chat_model_end_does_not_merge_text_across_tool_use():
    """String items join the text next to them, but a tool_use still separates the narration around it."""
    output = AIMessage(
        content=[
            {"type": "text", "text": "Let me "},
            "check",
            {"type": "tool_use", "name": "search", "input": {}, "id": "tool-1"},
            "Done",
        ]
    )
    message = Message(text="", content_blocks=[], sender="Machine")
    result, _ = await handle_on_chat_model_end({"data": {"output": output}}, message, _passthrough, None, 0.0)

    assert [(block.type, getattr(block, "text", None)) for block in result.content_blocks] == [
        ("text", "Let me check"),
        ("tool_use", None),
        ("text", "Done"),
    ]


async def _rehydrating_send(*, message: Message, **_kwargs) -> Message:
    """Mimic Component.send_message: every publication hands back a fresh Message built from the dump."""
    return Message(**message.model_dump())


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (
            ValueError("Tool 'flow_tool' execution failed: inner flow blew up"),
            "Tool 'flow_tool' execution failed: inner flow blew up",
        ),
        (RuntimeError(), "RuntimeError"),
    ],
)
async def test_tool_error_exception_is_kept_as_text(raised, expected):
    """astream_events hands on_tool_error the raw exception; the block must carry its text, not ``{}``.

    ``ToolContent.error`` is re-serialized on every publication. An exception object has no
    JSON form and degraded to ``{}`` through ``jsonable_encoder``'s ``vars()`` fallback, so the
    chat history and the OpenAI Responses stream showed an "Error using" step with no reason.
    """
    tool_blocks_map: dict[str, ToolContent] = {}
    message = Message(sender="Machine", sender_name="AI", text="", content_blocks=[])

    start_event = {"event": "on_tool_start", "name": "flow_tool", "run_id": "r1", "data": {"input": {"q": "x"}}}
    message, _ = await handle_on_tool_start(start_event, message, tool_blocks_map, _rehydrating_send, perf_counter())

    error_event = {"event": "on_tool_error", "name": "flow_tool", "run_id": "r1", "data": {"error": raised}}
    message, _ = await handle_on_tool_error(error_event, message, tool_blocks_map, _rehydrating_send, perf_counter())

    block = message.content_blocks[-1]
    assert isinstance(block, ToolContent)
    assert block.error == expected
    assert block.output is None
    assert block.header["title"] == "Error using **flow_tool**"
    # The wire form (what the event stream and the DB row carry) keeps the text too.
    assert message.model_dump()["content_blocks"][-1]["error"] == expected


async def test_tool_error_string_payload_passes_through():
    """Handlers fed a plain string (tests, non-LangChain producers) keep it verbatim."""
    tool_blocks_map: dict[str, ToolContent] = {}
    message = Message(sender="Machine", sender_name="AI", text="", content_blocks=[])
    start_event = {"event": "on_tool_start", "name": "t", "run_id": "r1", "data": {"input": {"q": "x"}}}
    message, _ = await handle_on_tool_start(start_event, message, tool_blocks_map, _passthrough, perf_counter())
    error_event = {"event": "on_tool_error", "name": "t", "run_id": "r1", "data": {"error": "tool failed"}}
    message, _ = await handle_on_tool_error(error_event, message, tool_blocks_map, _passthrough, perf_counter())
    assert message.content_blocks[-1].error == "tool failed"


async def _rehydrate(*, message: Message, **_kwargs) -> Message:
    """Rehydrate like Component.send_message does, rebuilding all blocks.

    This invalidates object references in tool_blocks_map and makes value-based
    lookups ambiguous for parallel same-argument calls.
    """
    return await Message.create(**message.model_dump())


async def test_parallel_same_args_keep_own_outputs_rehydrated():
    """Issue #15380: parallel calls to the same tool with identical arguments.

    Two model-declared ToolContent blocks (declared in start order a, b); the
    terminal events arrive out of order (b finishes first). Each block must
    keep its own run's output, not the first unbound block in the message.
    """
    msg = Message(
        content_blocks=[
            ToolContent(name="search", tool_input={"q": "same"}, output=None),
            ToolContent(name="search", tool_input={"q": "same"}, output=None),
        ],
        sender="Machine",
        sender_name="AI",
    )
    start_a = {"name": "search", "run_id": "a", "data": {"input": {"q": "same"}}}
    start_b = {"name": "search", "run_id": "b", "data": {"input": {"q": "same"}}}
    end_b = {"name": "search", "run_id": "b", "data": {"output": "result-b"}}
    end_a = {"name": "search", "run_id": "a", "data": {"output": "result-a"}}

    tool_blocks_map = {}
    msg, _ = await handle_on_tool_start(start_a, msg, tool_blocks_map, _rehydrate, perf_counter())
    msg, _ = await handle_on_tool_start(start_b, msg, tool_blocks_map, _rehydrate, perf_counter())
    msg, _ = await handle_on_tool_end(end_b, msg, tool_blocks_map, _rehydrate, perf_counter())
    msg, _ = await handle_on_tool_end(end_a, msg, tool_blocks_map, _rehydrate, perf_counter())

    outputs = [b.output for b in msg.content_blocks if isinstance(b, ToolContent)]
    assert outputs == ["result-a", "result-b"], f"got {outputs}"


async def test_parallel_same_args_fallback_created_blocks():
    """Issue #15380 variant: fallback-created blocks (no on_chat_model_end).

    Both blocks are appended by handle_on_tool_start itself; terminal events
    arriving out of order must still land on the matching run's block.
    """
    msg = Message(content_blocks=[], sender="Machine", sender_name="AI")
    start_a = {"name": "search", "run_id": "a", "data": {"input": {"q": "same"}}}
    start_b = {"name": "search", "run_id": "b", "data": {"input": {"q": "same"}}}
    end_b = {"name": "search", "run_id": "b", "data": {"output": "result-b"}}
    end_a = {"name": "search", "run_id": "a", "data": {"output": "result-a"}}

    tool_blocks_map = {}
    msg, _ = await handle_on_tool_start(start_a, msg, tool_blocks_map, _rehydrate, perf_counter())
    msg, _ = await handle_on_tool_start(start_b, msg, tool_blocks_map, _rehydrate, perf_counter())
    msg, _ = await handle_on_tool_end(end_b, msg, tool_blocks_map, _rehydrate, perf_counter())
    msg, _ = await handle_on_tool_end(end_a, msg, tool_blocks_map, _rehydrate, perf_counter())

    outputs = [b.output for b in msg.content_blocks if isinstance(b, ToolContent)]
    assert outputs == ["result-a", "result-b"], f"got {outputs}"


async def test_parallel_tool_error_kept_on_matching_block():
    """Issue #15380: on_tool_error must surface on the live block.

    The error handler used to mutate the stale reference directly; after a
    publication rehydrated the message the error vanished. With b erroring
    before a finishes, b's block must carry the error and a's block must still
    accept its own output.
    """
    msg = Message(
        content_blocks=[
            ToolContent(name="search", tool_input={"q": "same"}, output=None),
            ToolContent(name="search", tool_input={"q": "same"}, output=None),
        ],
        sender="Machine",
        sender_name="AI",
    )
    start_a = {"name": "search", "run_id": "a", "data": {"input": {"q": "same"}}}
    start_b = {"name": "search", "run_id": "b", "data": {"input": {"q": "same"}}}
    err_b = {"name": "search", "run_id": "b", "data": {"error": RuntimeError("boom")}}
    end_a = {"name": "search", "run_id": "a", "data": {"output": "result-a"}}

    tool_blocks_map = {}
    msg, _ = await handle_on_tool_start(start_a, msg, tool_blocks_map, _rehydrate, perf_counter())
    msg, _ = await handle_on_tool_start(start_b, msg, tool_blocks_map, _rehydrate, perf_counter())
    msg, _ = await handle_on_tool_error(err_b, msg, tool_blocks_map, _rehydrate, perf_counter())
    msg, _ = await handle_on_tool_end(end_a, msg, tool_blocks_map, _rehydrate, perf_counter())

    pairs = [(b.output, b.error) for b in (msg.content_blocks or []) if isinstance(b, ToolContent)]
    assert pairs == [("result-a", None), (None, "boom")], f"got {pairs}"


async def test_terminal_event_after_nested_model_end_keeps_binding():
    """Issue #15380: nested model-end must not invalidate run->block binding.

    A nested model-end event rehydrates the message again; the pending
    terminal event for run b must still find b's block by its recorded index.
    """
    msg = Message(
        content_blocks=[
            ToolContent(name="search", tool_input={"q": "same"}, output=None),
            ToolContent(name="search", tool_input={"q": "same"}, output=None),
        ],
        sender="Machine",
        sender_name="AI",
    )
    start_a = {"name": "search", "run_id": "a", "data": {"input": {"q": "same"}}}
    start_b = {"name": "search", "run_id": "b", "data": {"input": {"q": "same"}}}
    _ = {"name": "search", "run_id": "ignored"}  # nested model-end event
    end_b = {"name": "search", "run_id": "b", "data": {"output": "result-b"}}

    tool_blocks_map = {}
    msg, _ = await handle_on_tool_start(start_a, msg, tool_blocks_map, _rehydrate, perf_counter())
    msg, _ = await handle_on_tool_start(start_b, msg, tool_blocks_map, _rehydrate, perf_counter())
    # Nested publication: rehydrate once more without touching tool blocks.
    msg = await _rehydrate(message=msg)
    msg, _ = await handle_on_tool_end(end_b, msg, tool_blocks_map, _rehydrate, perf_counter())

    outputs = [b.output for b in msg.content_blocks if isinstance(b, ToolContent)]
    assert outputs[1] == "result-b", f"got {outputs}"
