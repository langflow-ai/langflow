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

from langflow.logging import logger
from langflow.schema.data import Data
from langflow.services.cache.base import CacheService
from langflow.services.cache.utils import CacheMiss

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


def data_to_messages(data: list[Data]) -> list[BaseMessage]:
    """Convert a list of data to a list of messages.

    Args:
        data (List[Data]): The data to convert.

    Returns:
        List[Message]: The data as messages.
    """
    return [value.to_lc_message() for value in data]


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
    # Optimized: check for '.' or '[' in keys, faster than regex
    if not any(("." in key) or ("[" in key and "]" in key) for key in flat):
        return flat

    nested: dict[str, Any] = {}

    # Precompiled regex replaced by a fast parser
    def parse_array_part(part):
        # Only called if "[" in part and part[-1] == ']'
        lb = part.rfind("[")
        # Only accept if the content within [] is all digits and there is at least one char before [
        if lb > 0 and part[-1] == "]" and part[lb + 1 : -1].isdigit():
            return part[:lb], int(part[lb + 1 : -1])
        return None

    setdefault = dict.setdefault  # Local binding for speed

    for key, val in flat.items():
        parts = key.split(".")
        cur = nested
        last = len(parts) - 1
        for i, part in enumerate(parts):
            # Fast path for array index keys, only parse if likely
            if "[" in part and part[-1] == "]":
                parsed = parse_array_part(part)
                if parsed is not None:
                    name, idx = parsed
                    lst = setdefault(cur, name, [])
                    # Extend list efficiently
                    llen = len(lst)
                    if llen <= idx:
                        lst.extend({} for _ in range(idx + 1 - llen))
                    if i == last:
                        lst[idx] = val
                    else:
                        cur = lst[idx]
                    continue  # Done for this part

            # Normal object key
            if i == last:
                cur[part] = val
            else:
                cur = setdefault(cur, part, {})

    return nested
