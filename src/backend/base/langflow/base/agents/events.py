# Add helper functions for each event type
from collections.abc import AsyncIterator
from typing import Any, Protocol

from langchain_core.agents import AgentFinish
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

from langflow.schema.content_block import ContentBlock
from langflow.schema.content_types import TextContent, ToolContent
from langflow.schema.log import SendMessageFunctionType
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_AI


class InputDict(TypedDict):
    input: str
    chat_history: list[BaseMessage]


def _build_agent_input_text_content(agent_input_dict: InputDict) -> ContentBlock:
    chat_history = agent_input_dict.get("chat_history", [])
    messages = [
        f"**{message.type.upper()}**: {message.content}"
        for message in chat_history
        if isinstance(message, BaseMessage) and message.content
    ]
    final_input = agent_input_dict.get("input", "")
    if final_input not in messages[-1]:
        messages.append(f"**HUMAN**: {final_input}")
    return "\n\n".join(messages)


async def handle_on_chain_start(
    event: dict[str, Any], agent_message: Message, send_message_method: SendMessageFunctionType
) -> Message:
    if event["data"].get("input"):
        agent_message.content_blocks.append(
            ContentBlock(
                title="Agent Input",
                contents=[
                    TextContent(
                        type="text",
                        text=_build_agent_input_text_content(event["data"].get("input")),
                    )
                ],
                allow_markdown=True,
            )
        )
        agent_message.properties.icon = "🚀"
        agent_message = send_message_method(message=agent_message)
    return agent_message


async def handle_on_chain_end(
    event: dict[str, Any], agent_message: Message, send_message_method: SendMessageFunctionType
) -> Message:
    data_output = event["data"].get("output", {})
    if data_output:
        if isinstance(data_output, AgentFinish) and data_output.return_values.get("output"):
            agent_message.text = data_output.return_values.get("output")
            agent_message.properties.icon = "🤖"
        else:
            agent_message.properties.icon = "🔍"
        agent_message = send_message_method(message=agent_message)
    return agent_message


def _find_or_create_tool_content_block(
    tool_blocks_map: dict[str, ContentBlock],
    run_id: str,
    tool_name: str,
    tool_input: Any | None = None,
    tool_output: Any | None = None,
    tool_error: Any | None = None,
) -> tuple[ContentBlock, bool]:
    """Find an existing tool content block or create a new one using run_id.

    Returns:
        Tuple of (ContentBlock, bool) where bool indicates if block was created
    """
    # Check if we have a block for this run_id
    if run_id in tool_blocks_map:
        return tool_blocks_map[run_id], False

    # Create new block
    new_block = ContentBlock(
        title=f"{tool_name} Execution",
        contents=[
            ToolContent(
                type="tool_use",
                name=tool_name,
                tool_input=tool_input,
                output=tool_output,
                error=tool_error,
            )
        ],
    )
    tool_blocks_map[run_id] = new_block
    return new_block, True


async def handle_on_tool_start(
    event: dict[str, Any],
    agent_message: Message,
    send_message_method: SendMessageFunctionType,
    tool_blocks_map: dict[str, ContentBlock],
) -> Message:
    tool_name = event["name"]
    tool_input = event["data"].get("input")
    run_id = event.get("run_id", "")

    block, is_new = _find_or_create_tool_content_block(tool_blocks_map, run_id, tool_name, tool_input=tool_input)

    if isinstance(block.contents, ToolContent):
        block.title = f"Accessing **{tool_name}**..."
        block.contents.tool_input = tool_input

    if is_new:
        agent_message.content_blocks.append(block)

    agent_message.properties.icon = "🔨"
    return send_message_method(message=agent_message)


async def handle_on_tool_end(
    event: dict[str, Any],
    agent_message: Message,
    send_message_method: SendMessageFunctionType,
    tool_blocks_map: dict[str, ContentBlock],
) -> Message:
    tool_name = event["name"]
    tool_output = event["data"].get("output")
    run_id = event.get("run_id", "")

    block, is_new = _find_or_create_tool_content_block(tool_blocks_map, run_id, tool_name, tool_output=tool_output)

    if isinstance(block.contents, ToolContent):
        block.title = f"**{tool_name}** Executed Successfully"
        block.contents.output = tool_output

    if is_new:  # Shouldn't happen but handle just in case
        agent_message.content_blocks.append(block)

    return send_message_method(message=agent_message)


async def handle_on_tool_error(
    event: dict[str, Any],
    agent_message: Message,
    send_message_method: SendMessageFunctionType,
    tool_blocks_map: dict[str, ContentBlock],
) -> Message:
    tool_name = event.get("name", "Unknown tool")
    error_message = event["data"].get("error", "Unknown error")
    run_id = event.get("run_id", "")

    block, is_new = _find_or_create_tool_content_block(tool_blocks_map, run_id, tool_name, tool_error=error_message)

    if isinstance(block.contents, ToolContent):
        block.title = f"**{tool_name}** Execution Failed"
        block.contents.error = error_message

    if is_new:  # Shouldn't happen but handle just in case
        agent_message.content_blocks.append(block)

    agent_message.properties.icon = "⚠️"
    return send_message_method(message=agent_message)


async def handle_on_chain_stream(
    event: dict[str, Any], agent_message: Message, send_message_method: SendMessageFunctionType
) -> Message:
    data_chunk = event["data"].get("chunk", {})
    if isinstance(data_chunk, dict) and data_chunk.get("output"):
        agent_message.text = data_chunk.get("output")
        agent_message.properties.state = "complete"
        agent_message = send_message_method(message=agent_message)
    return agent_message


class ToolEventHandler(Protocol):
    async def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
        send_message_method: SendMessageFunctionType,
        tool_blocks_map: dict[str, ContentBlock],
    ) -> Message: ...


class ChainEventHandler(Protocol):
    async def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
        send_message_method: SendMessageFunctionType,
    ) -> Message: ...


EventHandler = ToolEventHandler | ChainEventHandler

# Define separate mappings of event types to their respective handler functions
CHAIN_EVENT_HANDLERS: dict[str, ChainEventHandler] = {
    "on_chain_start": handle_on_chain_start,
    "on_chain_end": handle_on_chain_end,
    "on_chain_stream": handle_on_chain_stream,
}

TOOL_EVENT_HANDLERS: dict[str, ToolEventHandler] = {
    "on_tool_start": handle_on_tool_start,
    "on_tool_end": handle_on_tool_end,
    "on_tool_error": handle_on_tool_error,
}


async def process_agent_events(
    agent_executor: AsyncIterator[dict[str, Any]],
    send_message_method: SendMessageFunctionType,
) -> Message:
    """Process agent events and return the final output."""
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )
    # Store the initial message
    agent_message = send_message_method(message=agent_message)

    # Create a mapping of run_ids to tool content blocks
    tool_blocks_map: dict[str, ContentBlock] = {}

    async for event in agent_executor:
        if event["event"] in TOOL_EVENT_HANDLERS:
            tool_handler = TOOL_EVENT_HANDLERS[event["event"]]
            agent_message = await tool_handler(event, agent_message, send_message_method, tool_blocks_map)
        elif event["event"] in CHAIN_EVENT_HANDLERS:
            chain_handler = CHAIN_EVENT_HANDLERS[event["event"]]
            agent_message = await chain_handler(event, agent_message, send_message_method)
        else:
            # Handle any other event types or ignore them
            pass

    agent_message.properties.state = "complete"
    return Message(**agent_message.model_dump())
