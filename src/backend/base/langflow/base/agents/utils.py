from typing import Any, Callable, Dict, List, Sequence, Union

from langchain.agents import (
    create_json_chat_agent,
    create_openai_tools_agent,
    create_tool_calling_agent,
    create_xml_agent,
)
from langchain.agents.xml.base import render_text_description
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import BasePromptTemplate
from langchain_core.tools import BaseTool

from langflow.schema.schema import Record

from .default_prompts import XML_AGENT_PROMPT


def records_to_messages(records: List[Record]) -> List[BaseMessage]:
    """
    Convert a list of records to a list of messages.

    Args:
        records (List[Record]): The records to convert.

    Returns:
        List[Message]: The records as messages.
    """
    return [record.to_lc_message() for record in records]


def validate_and_create_xml_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: BasePromptTemplate,
    tools_renderer: Callable[[List[BaseTool]], str] = render_text_description,
    *,
    stop_sequence: Union[bool, List[str]] = True,
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
    prompt: BasePromptTemplate,
    tools_renderer: Callable[[List[BaseTool]], str] = render_text_description,
    *,
    stop_sequence: Union[bool, List[str]] = True,
):
    return create_openai_tools_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
    )


def validate_and_create_tool_calling_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: BasePromptTemplate,
    tools_renderer: Callable[[List[BaseTool]], str] = render_text_description,
    *,
    stop_sequence: Union[bool, List[str]] = True,
):
    return create_tool_calling_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
    )


def validate_and_create_json_chat_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: BasePromptTemplate,
    tools_renderer: Callable[[List[BaseTool]], str] = render_text_description,
    *,
    stop_sequence: Union[bool, List[str]] = True,
):
    return create_json_chat_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
        tools_renderer=tools_renderer,
        stop_sequence=stop_sequence,
    )


AGENTS: Dict[
    str,
    Dict[
        str,
        Union[
            Callable[[BaseLanguageModel, Sequence[BaseTool], BasePromptTemplate, Callable[[List[BaseTool]], str]], Any],
            BasePromptTemplate,
        ],
    ],
] = {
    "Tool Calling Agent": {
        "func": validate_and_create_tool_calling_agent,
        "prompt": "",
        "fields": ["llm", "tools", "prompt"],
        "hub_repo": None,
    },
    "XML Agent": {
        "func": validate_and_create_xml_agent,
        "prompt": XML_AGENT_PROMPT,
        "fields": ["llm", "tools", "prompt", "tools_renderer", "stop_sequence"],
        "hub_repo": "hwchase17/xml-agent-convo",
    },
    "OpenAI Tools Agent": {
        "func": validate_and_create_openai_tools_agent,
        "prompt": "",
        "fields": ["llm", "tools", "prompt"],
        "hub_repo": None,
    },
    "JSON Chat Agent": {
        "func": validate_and_create_json_chat_agent,
        "prompt": "",
        "fields": ["llm", "tools", "prompt", "tools_renderer", "stop_sequence"],
        "hub_repo": "hwchase17/react-chat-json",
    },
}


def get_agents_list():
    return list(AGENTS.keys())
