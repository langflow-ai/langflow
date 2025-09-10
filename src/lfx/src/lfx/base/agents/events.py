# Add helper functions for each event type
import json
import re
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any, Protocol

from langchain_core.agents import AgentFinish
from langchain_core.messages import AIMessageChunk, BaseMessage
from typing_extensions import TypedDict

from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import TextContent, ToolContent
from lfx.schema.log import SendMessageFunctionType
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


# Global state for AWS Anthropic function call processing
_aws_anthropic_state = {
    "processed_text": "",
    "last_sent_text": "",
    "in_function_call": False
}


class InputDict(TypedDict):
    input: str
    chat_history: list[BaseMessage]


def _build_agent_input_text_content(agent_input_dict: InputDict) -> str:
    final_input = agent_input_dict.get("input", "")
    return f"**Input**: {final_input}"


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


def _clean_text_for_aws_anthropic_streaming(text: str) -> str:
    """Clean text by removing function call markup for streaming display."""
    # Remove function call markup but keep the result text
    cleaned = re.sub(r"<function_calls>.*?</function_calls>", "", text, flags=re.DOTALL)
    # Remove any remaining function call tags
    cleaned = re.sub(r"<[^>]*>", "", cleaned)
    # Restore processed result text
    cleaned = re.sub(r"__RESULT_PROCESSED__(.+?)__(.+?)__", r"The result of \1 is \2.", cleaned)
    # Clean up extra whitespace
    return re.sub(r"\s+", " ", cleaned).strip()


def _reset_aws_anthropic_state():
    """Reset the AWS Anthropic processing state."""
    global _aws_anthropic_state  # noqa: PLW0603
    _aws_anthropic_state = {
        "processed_text": "",
        "last_sent_text": "",
        "in_function_call": False
    }


def _is_aws_anthropic_text(text: str) -> bool:
    """Check if the text contains AWS Anthropic function call patterns."""
    return "<function_calls>" in text or "The result of" in text


def _process_aws_anthropic_function_calls(text: str = "") -> tuple[str, bool]:
    """Process AWS Anthropic function calls in the accumulated text.

    Args:
        text: Additional text to add (optional, defaults to empty string)

    Returns:
        tuple: (cleaned_text, has_function_call)
    """
    # Add to processed text if provided
    if text:
        _aws_anthropic_state["processed_text"] += text

    # Check for function calls
    function_call_pattern = r"<function_calls>\s*<tool_name>([^<]+)</tool_name>\s*([^<]+)</function_calls>"
    function_call_match = re.search(function_call_pattern, _aws_anthropic_state["processed_text"], re.DOTALL)

    has_function_call = False
    if function_call_match and not _aws_anthropic_state["in_function_call"]:
        _aws_anthropic_state["in_function_call"] = True
        has_function_call = True
        # Extract tool name and params for potential future use
        _tool_name = function_call_match.group(1).strip()
        params_text = function_call_match.group(2).strip()

        try:
            if params_text.startswith("{") and params_text.endswith("}"):
                _params = json.loads(params_text)
            else:
                _params = {"input": params_text}
        except json.JSONDecodeError:
            _params = {"input": params_text}

        # Remove the function call from processed text to avoid reprocessing
        _aws_anthropic_state["processed_text"] = re.sub(
            function_call_pattern, "", _aws_anthropic_state["processed_text"], flags=re.DOTALL
        )

    # Check for function results
    result_pattern = r"The result of (.+?) is (.+?)\."
    result_match = re.search(result_pattern, _aws_anthropic_state["processed_text"])

    if result_match:
        operation = result_match.group(1).strip()
        result = result_match.group(2).strip()

        # Mark as processed by replacing with a placeholder to avoid reprocessing
        # but keep the original text for streaming
        placeholder = f"__RESULT_PROCESSED__{operation}__{result}__"
        _aws_anthropic_state["processed_text"] = re.sub(
            result_pattern, placeholder, _aws_anthropic_state["processed_text"]
        )

    # Clean the text for streaming
    cleaned_text = _clean_text_for_aws_anthropic_streaming(_aws_anthropic_state["processed_text"])

    return cleaned_text, has_function_call


async def handle_on_chain_start(
    event: dict[str, Any], agent_message: Message, send_message_method: SendMessageFunctionType, start_time: float
) -> tuple[Message, float]:
    # Reset AWS Anthropic state for new conversation
    _reset_aws_anthropic_state()

    # Create content blocks if they don't exist
    if not agent_message.content_blocks:
        agent_message.content_blocks = [ContentBlock(title="Agent Steps", contents=[])]

    if event["data"].get("input"):
        input_data = event["data"].get("input")
        if isinstance(input_data, dict) and "input" in input_data:
            # Cast the input_data to InputDict
            input_message = input_data.get("input", "")
            if isinstance(input_message, BaseMessage):
                input_message = input_message.text()
            elif not isinstance(input_message, str):
                input_message = str(input_message)

            input_dict: InputDict = {
                "input": input_message,
                "chat_history": input_data.get("chat_history", []),
            }
            text_content = TextContent(
                type="text",
                text=_build_agent_input_text_content(input_dict),
                duration=_calculate_duration(start_time),
                header={"title": "Input", "icon": "MessageSquare"},
            )
            agent_message.content_blocks[0].contents.append(text_content)
            agent_message = await send_message_method(message=agent_message)
            start_time = perf_counter()
    return agent_message, start_time


def _extract_output_text(output: str | list) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and len(output) == 0:
        return ""
    if not isinstance(output, list) or len(output) != 1:
        msg = f"Output is not a string or list of dictionaries with 'text' key: {output}"
        raise TypeError(msg)

    item = output[0]
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        if "text" in item:
            return item["text"]
        # If the item's type is "tool_use", return an empty string.
        # This likely indicates that "tool_use" outputs are not meant to be displayed as text.
        if item.get("type") == "tool_use":
            return ""
    if isinstance(item, dict):
        if "text" in item:
            return item["text"]
        # If the item's type is "tool_use", return an empty string.
        # This likely indicates that "tool_use" outputs are not meant to be displayed as text.
        if item.get("type") == "tool_use":
            return ""
        # This is a workaround to deal with function calling by Anthropic
        # since the same data comes in the tool_output we don't need to stream it here
        # although it would be nice to
        if "partial_json" in item:
            return ""
    msg = f"Output is not a string or list of dictionaries with 'text' key: {output}"
    raise TypeError(msg)


async def handle_on_chain_end(
    event: dict[str, Any], agent_message: Message, send_message_method: SendMessageFunctionType, start_time: float
) -> tuple[Message, float]:
    data_output = event["data"].get("output")
    if data_output and isinstance(data_output, AgentFinish) and data_output.return_values.get("output"):
        output = data_output.return_values.get("output")

        agent_message.text = _extract_output_text(output)
        agent_message.properties.state = "complete"
        # Add duration to the last content if it exists
        if agent_message.content_blocks:
            duration = _calculate_duration(start_time)
            text_content = TextContent(
                type="text",
                text=agent_message.text,
                duration=duration,
                header={"title": "Output", "icon": "MessageSquare"},
            )
            agent_message.content_blocks[0].contents.append(text_content)
        agent_message = await send_message_method(message=agent_message)
        start_time = perf_counter()
    elif _aws_anthropic_state["processed_text"] and _is_aws_anthropic_text(_aws_anthropic_state["processed_text"]):
        # Handle final AWS Anthropic processing for streaming
        # Process any remaining accumulated text
        cleaned_text, _ = _process_aws_anthropic_function_calls("")

        # Replace the agent message text with the final cleaned text
        if cleaned_text:
            agent_message.text = cleaned_text
            _aws_anthropic_state["last_sent_text"] = cleaned_text
            agent_message.properties.state = "complete"
            agent_message = await send_message_method(message=agent_message)
            start_time = perf_counter()
    return agent_message, start_time


async def handle_on_tool_start(
    event: dict[str, Any],
    agent_message: Message,
    tool_blocks_map: dict[str, ToolContent],
    send_message_method: SendMessageFunctionType,
    start_time: float,
) -> tuple[Message, float]:
    tool_name = event["name"]
    tool_input = event["data"].get("input")
    run_id = event.get("run_id", "")
    tool_key = f"{tool_name}_{run_id}"

    # Create content blocks if they don't exist
    if not agent_message.content_blocks:
        agent_message.content_blocks = [ContentBlock(title="Agent Steps", contents=[])]

    duration = _calculate_duration(start_time)
    new_start_time = perf_counter()  # Get new start time for next operation

    # Create new tool content with the input exactly as received
    tool_content = ToolContent(
        type="tool_use",
        name=tool_name,
        tool_input=tool_input,
        output=None,
        error=None,
        header={"title": f"Accessing **{tool_name}**", "icon": "Hammer"},
        duration=duration,  # Store the actual duration
    )

    # Store in map and append to message
    tool_blocks_map[tool_key] = tool_content
    agent_message.content_blocks[0].contents.append(tool_content)

    agent_message = await send_message_method(message=agent_message)
    if agent_message.content_blocks and agent_message.content_blocks[0].contents:
        tool_blocks_map[tool_key] = agent_message.content_blocks[0].contents[-1]
    return agent_message, new_start_time


async def handle_on_tool_end(
    event: dict[str, Any],
    agent_message: Message,
    tool_blocks_map: dict[str, ToolContent],
    send_message_method: SendMessageFunctionType,
    start_time: float,
) -> tuple[Message, float]:
    run_id = event.get("run_id", "")
    tool_name = event.get("name", "")
    tool_key = f"{tool_name}_{run_id}"
    tool_content = tool_blocks_map.get(tool_key)

    if tool_content and isinstance(tool_content, ToolContent):
        # Call send_message_method first to get the updated message structure
        agent_message = await send_message_method(message=agent_message)
        new_start_time = perf_counter()

        # Now find and update the tool content in the current message
        duration = _calculate_duration(start_time)
        tool_key = f"{tool_name}_{run_id}"

        # Find the corresponding tool content in the updated message
        updated_tool_content = None
        if agent_message.content_blocks and agent_message.content_blocks[0].contents:
            for content in agent_message.content_blocks[0].contents:
                if (
                    isinstance(content, ToolContent)
                    and content.name == tool_name
                    and content.tool_input == tool_content.tool_input
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
    send_message_method: SendMessageFunctionType,
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
        agent_message = await send_message_method(message=agent_message)
        start_time = perf_counter()
    return agent_message, start_time


async def handle_on_chain_stream(
    event: dict[str, Any],
    agent_message: Message,
    send_message_method: SendMessageFunctionType,
    start_time: float,
) -> tuple[Message, float]:
    data_chunk = event["data"].get("chunk", {})
    if isinstance(data_chunk, dict) and data_chunk.get("output"):
        output = data_chunk.get("output")
        if output and isinstance(output, str | list):
            agent_message.text = _extract_output_text(output)
        agent_message.properties.state = "complete"
        agent_message = await send_message_method(message=agent_message)
        start_time = perf_counter()
    elif isinstance(data_chunk, AIMessageChunk):
        output_text = _extract_output_text(data_chunk.content)
        if output_text and isinstance(agent_message.text, str):
            # Always accumulate text for AWS Anthropic processing
            _aws_anthropic_state["processed_text"] += output_text

            # Check if we have AWS Anthropic patterns in the accumulated text
            if _is_aws_anthropic_text(_aws_anthropic_state["processed_text"]):
                # Process AWS Anthropic function calls on accumulated text
                cleaned_text, _ = _process_aws_anthropic_function_calls("")

                # Only add the new cleaned text that hasn't been sent yet
                if "last_sent_text" in _aws_anthropic_state:
                    new_text = cleaned_text[len(_aws_anthropic_state["last_sent_text"]):]
                else:
                    new_text = cleaned_text
                    _aws_anthropic_state["last_sent_text"] = ""

                if new_text:
                    agent_message.text += new_text
                    _aws_anthropic_state["last_sent_text"] = cleaned_text
            else:
                # Regular text processing - add the new chunk directly
                agent_message.text += output_text

            agent_message.properties.state = "partial"
            agent_message = await send_message_method(message=agent_message)
        if not agent_message.text:
            start_time = perf_counter()
    return agent_message, start_time


class ToolEventHandler(Protocol):
    async def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
        tool_blocks_map: dict[str, ContentBlock],
        send_message_method: SendMessageFunctionType,
        start_time: float,
    ) -> tuple[Message, float]: ...


class ChainEventHandler(Protocol):
    async def __call__(
        self,
        event: dict[str, Any],
        agent_message: Message,
        send_message_method: SendMessageFunctionType,
        start_time: float,
    ) -> tuple[Message, float]: ...


EventHandler = ToolEventHandler | ChainEventHandler

# Define separate mappings of event types to their respective handler functions
CHAIN_EVENT_HANDLERS: dict[str, ChainEventHandler] = {
    "on_chain_start": handle_on_chain_start,
    "on_chain_end": handle_on_chain_end,
    "on_chain_stream": handle_on_chain_stream,
    "on_chat_model_stream": handle_on_chain_stream,
}

TOOL_EVENT_HANDLERS: dict[str, ToolEventHandler] = {
    "on_tool_start": handle_on_tool_start,
    "on_tool_end": handle_on_tool_end,
    "on_tool_error": handle_on_tool_error,
}


async def process_agent_events(
    agent_executor: AsyncIterator[dict[str, Any]],
    agent_message: Message,
    send_message_method: SendMessageFunctionType,
) -> Message:
    """Process agent events and return the final output."""
    if isinstance(agent_message.properties, dict):
        agent_message.properties.update({"icon": "Bot", "state": "partial"})
    else:
        agent_message.properties.icon = "Bot"
        agent_message.properties.state = "partial"
    # Store the initial message
    agent_message = await send_message_method(message=agent_message)
    try:
        # Create a mapping of run_ids to tool contents
        tool_blocks_map: dict[str, ToolContent] = {}
        start_time = perf_counter()
        async for event in agent_executor:
            if event["event"] in TOOL_EVENT_HANDLERS:
                tool_handler = TOOL_EVENT_HANDLERS[event["event"]]
                agent_message, start_time = await tool_handler(
                    event, agent_message, tool_blocks_map, send_message_method, start_time
                )
            elif event["event"] in CHAIN_EVENT_HANDLERS:
                chain_handler = CHAIN_EVENT_HANDLERS[event["event"]]
                agent_message, start_time = await chain_handler(event, agent_message, send_message_method, start_time)
        agent_message.properties.state = "complete"
    except Exception as e:
        raise ExceptionWithMessageError(agent_message, str(e)) from e
    return await Message.create(**agent_message.model_dump())
