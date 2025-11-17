import re
from collections.abc import Callable, Sequence
from typing import Any

from langchain.agents import (
    create_json_chat_agent,
    create_openai_tools_agent,
    create_tool_calling_agent,
    create_xml_agent,
)
from langchain.agents.xml.base import render_text_description
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import BasePromptTemplate, ChatPromptTemplate
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.services.cache.base import CacheService
from lfx.services.cache.utils import CacheMiss

from .default_prompts import XML_AGENT_PROMPT


class AgentSpec(BaseModel):
    func: Callable[
        [
            BaseLanguageModel,
            Sequence[BaseTool],
            BasePromptTemplate | ChatPromptTemplate,
            Callable[[list[BaseTool]], str] | None,
            bool | list[str] | None,
        ],
        Any,
    ]
    prompt: Any | None = None
    fields: list[str]
    hub_repo: str | None = None


def data_to_messages(data: list[Data | Message]) -> list[BaseMessage]:
    """Convert a list of data to a list of messages.

    Args:
        data (List[Data | Message]): The data to convert.

    Returns:
        List[BaseMessage]: The data as messages, filtering out any with empty content.
    """
    messages = []
    for value in data:
        try:
            lc_message = value.to_lc_message()
            # Only add messages with non-empty content (prevents Anthropic API errors)
            content = lc_message.content
            if content and ((isinstance(content, str) and content.strip()) or (isinstance(content, list) and content)):
                messages.append(lc_message)
            else:
                logger.warning("Skipping message with empty content in chat history")
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to convert message to BaseMessage: {e}")
            continue
    return messages


def validate_and_create_xml_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: BasePromptTemplate,
    tools_renderer: Callable[[list[BaseTool]], str] = render_text_description,
    *,
    stop_sequence: bool | list[str] = True,
):
    return create_xml_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
        tools_renderer=tools_renderer,
        stop_sequence=stop_sequence,
    )


def validate_and_create_openai_tools_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: ChatPromptTemplate,
    _tools_renderer: Callable[[list[BaseTool]], str] = render_text_description,
    *,
    _stop_sequence: bool | list[str] = True,
):
    return create_openai_tools_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
    )


def validate_and_create_tool_calling_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: ChatPromptTemplate,
    _tools_renderer: Callable[[list[BaseTool]], str] = render_text_description,
    *,
    _stop_sequence: bool | list[str] = True,
):
    return create_tool_calling_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
    )


def validate_and_create_json_chat_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: ChatPromptTemplate,
    tools_renderer: Callable[[list[BaseTool]], str] = render_text_description,
    *,
    stop_sequence: bool | list[str] = True,
):
    return create_json_chat_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
        tools_renderer=tools_renderer,
        stop_sequence=stop_sequence,
    )


AGENTS: dict[str, AgentSpec] = {
    "Tool Calling Agent": AgentSpec(
        func=validate_and_create_tool_calling_agent,
        prompt=None,
        fields=["llm", "tools", "prompt"],
        hub_repo=None,
    ),
    "XML Agent": AgentSpec(
        func=validate_and_create_xml_agent,
        prompt=XML_AGENT_PROMPT,  # Ensure XML_AGENT_PROMPT is properly defined and typed.
        fields=["llm", "tools", "prompt", "tools_renderer", "stop_sequence"],
        hub_repo="hwchase17/xml-agent-convo",
    ),
    "OpenAI Tools Agent": AgentSpec(
        func=validate_and_create_openai_tools_agent,
        prompt=None,
        fields=["llm", "tools", "prompt"],
        hub_repo=None,
    ),
    "JSON Chat Agent": AgentSpec(
        func=validate_and_create_json_chat_agent,
        prompt=None,
        fields=["llm", "tools", "prompt", "tools_renderer", "stop_sequence"],
        hub_repo="hwchase17/react-chat-json",
    ),
}


def get_agents_list():
    return list(AGENTS.keys())


def safe_cache_get(cache: CacheService, key, default=None):
    """Safely get a value from cache, handling CacheMiss objects."""
    try:
        value = cache.get(key)
        if isinstance(value, CacheMiss):
            return default
    except (AttributeError, KeyError, TypeError):
        return default
    else:
        return value


def safe_cache_set(cache: CacheService, key, value):
    """Safely set a value in cache, handling potential errors."""
    try:
        cache.set(key, value)
    except (AttributeError, TypeError) as e:
        logger.warning(f"Failed to set cache key '{key}': {e}")


def maybe_unflatten_dict(flat: dict[str, Any]) -> dict[str, Any]:
    """If any key looks nested (contains a dot or "[index]"), rebuild the.

    full nested structure; otherwise return flat as is.
    """
    # Quick check: do we have any nested keys?
    if not any(re.search(r"\.|\[\d+\]", key) for key in flat):
        return flat

    # Otherwise, unflatten into dicts/lists
    nested: dict[str, Any] = {}
    array_re = re.compile(r"^(.+)\[(\d+)\]$")

    for key, val in flat.items():
        parts = key.split(".")
        cur = nested
        for i, part in enumerate(parts):
            m = array_re.match(part)
            # Array segment?
            if m:
                name, idx = m.group(1), int(m.group(2))
                lst = cur.setdefault(name, [])
                # Ensure list is big enough
                while len(lst) <= idx:
                    lst.append({})
                if i == len(parts) - 1:
                    lst[idx] = val
                else:
                    cur = lst[idx]
            # Normal object key
            elif i == len(parts) - 1:
                cur[part] = val
            else:
                cur = cur.setdefault(part, {})

    return nested


def get_chat_output_sender_name(self) -> str | None:
    """Get sender_name from ChatOutput component."""
    if not hasattr(self, "graph") or not self.graph:
        return None

    for vertex in self.graph.vertices:
        # Safely check if vertex has data attribute, correct type, and raw_params
        if (
            hasattr(vertex, "data")
            and vertex.data.get("type") == "ChatOutput"
            and hasattr(vertex, "raw_params")
            and vertex.raw_params
        ):
            return vertex.raw_params.get("sender_name")

    return None
