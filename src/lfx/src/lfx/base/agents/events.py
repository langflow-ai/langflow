# Add helper functions for each event type
import asyncio
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any, Protocol

from langchain_core.agents import AgentFinish
from langchain_core.messages import AIMessageChunk

from lfx.schema.content_types import TextContent, ToolContent
from lfx.schema.log import OnTokenFunctionType, SendMessageFunctionType
from lfx.schema.message import Message


class ExceptionWithMessageError(Exception):
    def __init__(self, agent_message: Message, message: str):
        self.agent_message = agent_message
        super().__init__(message)
        self.message = message

    def __str__(self):
        return (
            f"Agent message: {self.agent_message.text} \nError: {self.message}."
            if self.agent_message.error or self.agent_message.text
            else f"{self.message}."
        )


def _calculate_duration(start_time: float) -> int:
    """Calculate duration in milliseconds from start time to now."""
    # Handle the calculation
    current_time = perf_counter()
    if isinstance(start_time, int):
        # If we got an integer, treat it as milliseconds
        duration = current_time - (start_time / 1000)
        result = int(duration * 1000)
    else:
        # If we got a float, treat it as perf_counter time
        result = int((current_time - start_time) * 1000)

    return result


async def handle_on_chain_start(
    event: dict[str, Any],  # noqa: ARG001
    agent_message: Message,
    send_message_callback: SendMessageFunctionType,  # noqa: ARG001
    send_token_callback: OnTokenFunctionType | None,  # noqa: ARG001
    start_time: float,
    *,
    had_streaming: bool = False,  # noqa: ARG001
    message_id: str | None = None,  # noqa: ARG001
) -> tuple[Message, float]:
    # No-op. The synthetic "Input" TextContent that used to live inside the
    # "Agent Steps" group is gone in the flat content_blocks design — the
    # user message is already rendered above the agent's reply, so echoing
    # it back as a content block was duplicative. content_blocks is now a
    # chronological event log, populated by the tool / chain handlers below.
    return agent_message, start_time


def _extract_output_text(output: str | list) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and len(output) == 0:
        return ""

    # Handle lists of various lengths and formats
    if isinstance(output, list):
        # Handle single item lists
        if len(output) == 1:
            item = output[0]
            if isinstance(item, str):
                return item
            if isinstance(item, dict):
                if "text" in item:
                    return item["text"] or ""
                if "content" in item:
                    return str(item["content"])
                if "message" in item:
                    return str(item["message"])

                # Special case handling for non-text-like dicts
                if (
                    item.get("type") == "tool_use"  # Handle tool use items
                    or ("index" in item and len(item) == 1)  # Handle index-only items
                    or "partial_json" in item  # Handle partial json items
                    # Handle index-only items
                    or ("index" in item and not any(k in item for k in ("text", "content", "message")))
                    # Handle other metadata-only chunks that don't contain meaningful text
                    or not any(key in item for key in ["text", "content", "message"])
                ):
                    return ""

                # For any other dict format, return empty string
                return ""
            # For any other single item type (not str or dict), return empty string
            return ""

        # Handle multiple items - extract text from all text-type items
        text_parts = []
        for item in output:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                if "text" in item and item["text"] is not None:
                    text_parts.append(item["text"])
                # Skip tool_use, index-only, and partial_json items
                elif item.get("type") == "tool_use" or "partial_json" in item or ("index" in item and len(item) == 1):
                    continue
        return "".join(text_parts)

    # If we get here, the format is unexpected but try to be graceful
    return ""


async def handle_on_chain_end(
    event: dict[str, Any],
    agent_message: Message,
    send_message_callback: SendMessageFunctionType,
    send_token_callback: OnTokenFunctionType | None,  # noqa: ARG001
    start_time: float,
    *,
    had_streaming: bool = False,
    message_id: str | None = None,  # noqa: ARG001
) -> tuple[Message, float]:
    data_output = event["data"].get("output")
    if data_output and isinstance(data_output, AgentFinish) and data_output.return_values.get("output"):
        output = data_output.return_values.get("output")

        # Don't reassign agent_message.text here. The setter drops every
        # existing TextContent and appends a single one at the end, which
        # would collapse the interleaved text + tool_use blocks the
        # on_chat_model_end handler appends in producer order. The text
        # for the final round is already in content_blocks, and Message.text
        # is a computed_field over those TextContent entries — getting
        # the answer back out is automatic. Stash the extracted string in
        # data["text"] so legacy consumers reading message.data["text"]
        # still see the final answer.
        agent_message.data[agent_message.text_key] = _extract_output_text(output) or ""
        agent_message.properties.state = "complete"

        # Only send final message if we didn't have streaming chunks
        # If we had streaming, frontend already accumulated the chunks
        if not had_streaming:
            agent_message = await send_message_callback(message=agent_message)
        start_time = perf_counter()
    return agent_message, start_time


def _coerce_ai_message_blocks(content: Any) -> list[dict[str, Any]]:
    """Normalise an AIMessage.content into a list[dict] of typed blocks.

    Anthropic emits ``content`` as ``list[dict]`` where each dict has a
    ``type`` of ``"text"`` / ``"tool_use"`` / ``"input_json_delta"`` /
    etc. OpenAI-style providers emit ``content`` as a plain string for
    text-only turns and surface tool calls separately on ``.tool_calls``.

    Return shape is always ``list[{"type": ..., ...}]`` so the caller
    walks one structure. Text-only strings turn into a single
    ``{"type": "text", "text": str}``. Anything we don't recognise is
    skipped — the on_tool_start fallback in handle_on_tool_start will
    still pick up tool calls if a provider routes them outside .content.
    """
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, dict) and item.get("type") in {"text", "tool_use"}]


async def handle_on_chat_model_end(
    event: dict[str, Any],
    agent_message: Message,
    send_message_callback: SendMessageFunctionType,
    send_token_callback: OnTokenFunctionType | None,  # noqa: ARG001
    start_time: float,
    *,
    had_streaming: bool = False,  # noqa: ARG001
    message_id: str | None = None,  # noqa: ARG001
) -> tuple[Message, float]:
    """Append the just-completed AIMessage's text + tool_use blocks in order.

    Claude's tool-calling pattern is to emit a single AIMessage per agent
    turn with mixed content: ``[text "Let me check", tool_use A, text
    "Now compute", tool_use B]``. The model has already decided the
    interleaving order. Walk the content list and append each piece to
    ``content_blocks`` chronologically so the renderer can show the
    narration before each tool call instead of one summary paragraph at
    the end.

    Tool calls land here with ``output=None``; handle_on_tool_end fills
    them in once the tool actually returns. handle_on_tool_start sees the
    pre-populated ToolContent and skips its own append (dedup by name +
    tool_input + output is None), so providers that don't fire
    on_chat_model_end (or route tool calls outside .content) still get
    their ToolContent appended via the fallback.
    """
    output = event["data"].get("output")
    if not output or not hasattr(output, "content"):
        return agent_message, start_time

    blocks = _coerce_ai_message_blocks(output.content)
    if not blocks:
        return agent_message, start_time

    if agent_message.content_blocks is None:
        agent_message.content_blocks = []

    duration = _calculate_duration(start_time)
    appended = False
    for item in blocks:
        item_type = item.get("type")
        if item_type == "text":
            text = item.get("text") or ""
            if not text:
                continue
            agent_message.content_blocks.append(TextContent(type="text", text=text, duration=duration))
            appended = True
        elif item_type == "tool_use":
            agent_message.content_blocks.append(
                ToolContent(
                    type="tool_use",
                    name=item.get("name"),
                    tool_input=item.get("input") or {},
                    output=None,
                    error=None,
                    header={"title": f"Accessing **{item.get('name')}**", "icon": "Hammer"},
                    duration=duration,
                )
            )
            appended = True

    if appended:
        agent_message = await send_message_callback(message=agent_message, skip_db_update=True)
    return agent_message, perf_counter()


async def handle_on_tool_start(
    event: dict[str, Any],
    agent_message: Message,
    tool_blocks_map: dict[str, ToolContent],
    send_message_callback: SendMessageFunctionType,
    start_time: float,
) -> tuple[Message, float]:
    """Bind the run_id to the ToolContent the model already emitted.

    handle_on_chat_model_end has typically already appended a ToolContent
    for this tool_use (with output=None) in the right interleaved
    position. We just need to find it and key it in tool_blocks_map so
    handle_on_tool_end can locate it via run_id.

    Match by ``name`` + ``output is None`` + "not yet bound". The
    tool_use block emitted by on_chat_model_end has an empty
    ``tool_input`` because the model streams the JSON args separately
    (as ``input_json_delta`` chunks accumulated by the runtime, not
    captured in our handler's snapshot); the real input only arrives
    here via on_tool_start. So match by name + unbound + waiting, then
    overwrite tool_input with what we receive now.

    Fallback: if no matching ToolContent is found (provider routed tool
    calls outside .content, or on_chat_model_end never fired), append
    one ourselves so the tool still has a block — order will be best-
    effort but the call won't be dropped.
    """
    tool_name = event["name"]
    tool_input = event["data"].get("input") or {}
    run_id = event.get("run_id", "")
    tool_key = f"{tool_name}_{run_id}"

    if agent_message.content_blocks is None:
        agent_message.content_blocks = []

    # Look for the ToolContent the model-end handler should have placed.
    # Skip any that handle_on_tool_start has already bound for an earlier
    # parallel call to the same tool, so each on_tool_start picks the
    # next unbound block in declaration order.
    bound_block_ids = {id(v) for v in tool_blocks_map.values()}
    existing = None
    for block in agent_message.content_blocks:
        if (
            isinstance(block, ToolContent)
            and block.name == tool_name
            and block.output is None
            and id(block) not in bound_block_ids
        ):
            existing = block
            break

    if existing is not None:
        # Overwrite tool_input with the real, accumulated args (the
        # model-end snapshot had {} because JSON-delta chunks land
        # later). But only when on_tool_start actually carries input —
        # providers that already populated the model-end block's
        # tool_input (non-streaming Anthropic) fire on_tool_start with an
        # empty payload, and clobbering with {} would lose the real args.
        existing.tool_input = tool_input or existing.tool_input
        tool_blocks_map[tool_key] = existing
        return agent_message, perf_counter()

    # Fallback path — append the ToolContent ourselves.
    duration = _calculate_duration(start_time)
    new_start_time = perf_counter()
    tool_content = ToolContent(
        type="tool_use",
        name=tool_name,
        tool_input=tool_input,
        output=None,
        error=None,
        header={"title": f"Accessing **{tool_name}**", "icon": "Hammer"},
        duration=duration,
    )
    tool_blocks_map[tool_key] = tool_content
    agent_message.content_blocks.append(tool_content)
    agent_message = await send_message_callback(message=agent_message, skip_db_update=True)
    if agent_message.content_blocks and isinstance(agent_message.content_blocks[-1], ToolContent):
        tool_blocks_map[tool_key] = agent_message.content_blocks[-1]
    return agent_message, new_start_time


async def handle_on_tool_end(
    event: dict[str, Any],
    agent_message: Message,
    tool_blocks_map: dict[str, ToolContent],
    send_message_callback: SendMessageFunctionType,
    start_time: float,
) -> tuple[Message, float]:
    run_id = event.get("run_id", "")
    tool_name = event.get("name", "")
    tool_key = f"{tool_name}_{run_id}"
    tool_content = tool_blocks_map.get(tool_key)

    if tool_content and isinstance(tool_content, ToolContent):
        # Call send_message_callback first to get the updated message structure
        agent_message = await send_message_callback(message=agent_message, skip_db_update=True)
        new_start_time = perf_counter()

        # Now find and update the tool content in the current message. With
        # flat content_blocks we walk the list directly instead of indexing
        # into a single group's .contents.
        duration = _calculate_duration(start_time)

        updated_tool_content = None
        for content in agent_message.content_blocks or []:
            if (
                isinstance(content, ToolContent)
                and content.name == tool_name
                and content.tool_input == tool_content.tool_input
                and content.output is None
            ):
                updated_tool_content = content
                break

        # Update the tool content that's actually in the message
        if updated_tool_content:
            updated_tool_content.duration = duration
            updated_tool_content.header = {"title": f"Executed **{updated_tool_content.name}**", "icon": "Hammer"}
            updated_tool_content.output = event["data"].get("output")

            # Update the map reference
            tool_blocks_map[tool_key] = updated_tool_content

        return agent_message, new_start_time
    return agent_message, start_time


async def handle_on_tool_error(
    event: dict[str, Any],
    agent_message: Message,
    tool_blocks_map: dict[str, ToolContent],
    send_message_callback: SendMessageFunctionType,
    start_time: float,
) -> tuple[Message, float]:
    run_id = event.get("run_id", "")
    tool_name = event.get("name", "")
    tool_key = f"{tool_name}_{run_id}"
    tool_content = tool_blocks_map.get(tool_key)

    if tool_content and isinstance(tool_content, ToolContent):
        tool_content.error = event["data"].get("error", "Unknown error")
        tool_content.duration = _calculate_duration(start_time)
        tool_content.header = {"title": f"Error using **{tool_content.name}**", "icon": "Hammer"}
        agent_message = await send_message_callback(message=agent_message, skip_db_update=True)
        start_time = perf_counter()
    return agent_message, start_time


async def handle_on_chain_stream(
    event: dict[str, Any],
    agent_message: Message,
    send_message_callback: SendMessageFunctionType,  # noqa: ARG001
    send_token_callback: OnTokenFunctionType | None,
    start_time: float,
    *,
    had_streaming: bool = False,  # noqa: ARG001
    message_id: str | None = None,
) -> tuple[Message, float]:
    data_chunk = event["data"].get("chunk", {})
    if isinstance(data_chunk, dict) and data_chunk.get("output"):
        output = data_chunk.get("output")
        if output and isinstance(output, str | list):
            # Don't use the Message.text setter here. Like handle_on_chain_end,
            # the setter drops every existing TextContent and appends one at the
            # end, which collapses the interleaved text + tool_use blocks
            # on_chat_model_end appended in producer order. ALTK / legacy
            # AgentExecutor paths reach this branch via on_chain_stream. Stash
            # the extracted string in data[text_key] so legacy consumers still
            # read it while content_blocks stays the source of truth.
            agent_message.data[agent_message.text_key] = _extract_output_text(output) or ""
        agent_message.properties.state = "complete"
        # Don't call send_message_callback here - we must update in place
        # in order to keep the message id consistent throughout the stream.
        # The final message will be sent after the loop completes
        start_time = perf_counter()
    elif isinstance(data_chunk, AIMessageChunk):
        output_text = _extract_output_text(data_chunk.content)
        # For streaming, send token event if callback is available
        # Note: we should expect the callback, but we keep it optional for backwards compatibility
        # as of v1.6.5
        if output_text is not None and output_text != "" and send_token_callback and message_id:
            await asyncio.to_thread(
                send_token_callback,
                data={
                    "chunk": output_text,
                    "id": str(message_id),
                },
            )

        if not agent_message.text:
            # Starts the timer when the first message is starting to be generated
            start_time = perf_counter()
    return agent_message, start_time


class ToolEventHandler(Protocol):
    async def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
        tool_blocks_map: dict[str, ToolContent],
        send_message_callback: SendMessageFunctionType,
        start_time: float,
    ) -> tuple[Message, float]: ...


class ChainEventHandler(Protocol):
    async def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
        send_message_callback: SendMessageFunctionType,
        send_token_callback: OnTokenFunctionType | None,
        start_time: float,
        *,
        had_streaming: bool = False,
        message_id: str | None = None,
    ) -> tuple[Message, float]: ...


EventHandler = ToolEventHandler | ChainEventHandler

# Define separate mappings of event types to their respective handler functions
CHAIN_EVENT_HANDLERS: dict[str, ChainEventHandler] = {
    "on_chain_start": handle_on_chain_start,
    "on_chain_end": handle_on_chain_end,
    "on_chain_stream": handle_on_chain_stream,
    "on_chat_model_stream": handle_on_chain_stream,
    # Per-round AIMessage. Fires after each on_chat_model_stream burst
    # and before the matching on_tool_start. Walks .content for the
    # interleaved text + tool_use the model emitted and appends them
    # to content_blocks in producer order.
    "on_chat_model_end": handle_on_chat_model_end,
}

TOOL_EVENT_HANDLERS: dict[str, ToolEventHandler] = {
    "on_tool_start": handle_on_tool_start,
    "on_tool_end": handle_on_tool_end,
    "on_tool_error": handle_on_tool_error,
}


async def process_agent_events(
    agent_executor: AsyncIterator[dict[str, Any]],
    agent_message: Message,
    send_message_callback: SendMessageFunctionType,
    send_token_callback: OnTokenFunctionType | None = None,
) -> Message:
    """Process agent events and return the final output."""
    if isinstance(agent_message.properties, dict):
        agent_message.properties.update({"icon": "Bot", "state": "partial"})
    else:
        agent_message.properties.icon = "Bot"
        agent_message.properties.state = "partial"
    # Store the initial message and capture the message id
    agent_message = await send_message_callback(message=agent_message)
    # Capture the original message id - this must stay consistent throughout if streaming
    # Message may not contain id if the Agent is not connected to a Chat Output (_should_skip_message is True)
    initial_message_id = agent_message.get_id()
    try:
        # Create a mapping of run_ids to tool contents
        tool_blocks_map: dict[str, ToolContent] = {}
        had_streaming = False
        start_time = perf_counter()

        async for event in agent_executor:
            if event["event"] in TOOL_EVENT_HANDLERS:
                tool_handler = TOOL_EVENT_HANDLERS[event["event"]]
                # Use skip_db_update=True during streaming to avoid DB round-trips
                agent_message, start_time = await tool_handler(
                    event, agent_message, tool_blocks_map, send_message_callback, start_time
                )
            elif event["event"] in CHAIN_EVENT_HANDLERS:
                chain_handler = CHAIN_EVENT_HANDLERS[event["event"]]

                # Check if this is a streaming event
                if event["event"] in ("on_chain_stream", "on_chat_model_stream"):
                    had_streaming = True
                    agent_message, start_time = await chain_handler(
                        event,
                        agent_message,
                        send_message_callback,
                        send_token_callback,
                        start_time,
                        had_streaming=had_streaming,
                        message_id=initial_message_id,
                    )
                else:
                    agent_message, start_time = await chain_handler(
                        event, agent_message, send_message_callback, None, start_time, had_streaming=had_streaming
                    )

        agent_message.properties.state = "complete"
        # Final DB update with the complete message (skip_db_update=False by default)
        agent_message = await send_message_callback(message=agent_message)
    except Exception as e:
        raise ExceptionWithMessageError(agent_message, str(e)) from e
    return await Message.create(**agent_message.model_dump())
