"""Regression tests for the agent event-loop handlers in lfx.base.agents.events.

These pin two interleaving-preservation behaviors:
- handle_on_chain_stream must not run the Message.text setter (which collapses
  interleaved text + tool_use blocks); it stashes the extracted answer in
  data["text"] instead.
- handle_on_tool_start must not clobber a model-end tool_input snapshot with an
  empty on_tool_start payload.

The async ``send_message_callback`` here is a passthrough test harness for the
handler's callback boundary, not a behavior mock; the code paths under test
return before invoking it.
"""

from time import perf_counter

from lfx.base.agents.events import handle_on_chain_stream, handle_on_tool_start
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
