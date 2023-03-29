from langchain import agents, chains, prompts
from langchain.agents import agent_toolkits
from langchain import requests
from langflow.custom import customs
from langflow.interface.custom_lists import (
    llm_type_to_cls_dict,
    memory_type_to_cls_dict,
)
from langflow.settings import settings
from langflow.utils import util
from langchain.agents.load_tools import get_all_tool_names
from langchain.agents import Tool
from langflow.interface.custom_types import PythonFunction
from langchain.tools.json.tool import JsonSpec

OTHER_TOOLS = {"JsonSpec": JsonSpec}
CUSTOM_TOOLS = {"Tool": Tool, "PythonFunction": PythonFunction}
TOOLS_DICT = util.get_tools_dict()
ALL_TOOLS_NAMES = set(
    get_all_tool_names() + list(CUSTOM_TOOLS.keys()) + list(OTHER_TOOLS.keys())
)


def get_type_dict():
    return {
        "chains": list_chain_types,
        "agents": list_agents,
        "prompts": list_prompts,
        "llms": list_llms,
        "tools": list_tools,
        "memories": list_memories,
        "toolkits": list_toolkis,
        "wrappers": list_wrappers,
    }


def list_type(object_type: str):
    """List all components"""
    return get_type_dict().get(object_type, lambda: None)()


def list_wrappers():
    """List all wrapper types"""
    return [requests.RequestsWrapper.__name__]


def list_agents():
    """List all agent types"""
    return [
        agent.__name__
        for agent in agents.loading.AGENT_TO_CLASS.values()
        if agent.__name__ in settings.agents or settings.dev
    ]


def list_toolkis():
    """List all toolkit types"""
    return agent_toolkits.__all__


def list_prompts():
    """List all prompt types"""
    custom_prompts = customs.get_custom_nodes("prompts")
    library_prompts = [
        prompt.__annotations__["return"].__name__
        for prompt in prompts.loading.type_to_loader_dict.values()
        if prompt.__annotations__["return"].__name__ in settings.prompts or settings.dev
    ]
    return library_prompts + list(custom_prompts.keys())


def list_tools():
    """List all load tools"""

    tools = []

    for tool in ALL_TOOLS_NAMES:
        tool_params = util.get_tool_params(util.get_tool_by_name(tool))

        if "name" not in tool_params:
            tool_params["name"] = tool

        if tool_params and (
            tool_params.get("name") in settings.tools
            or (tool_params.get("name") and settings.dev)
        ):
            tools.append(tool_params["name"])

    # Add Tool
    custom_tools = customs.get_custom_nodes("tools")
    return tools + list(custom_tools.keys())


def list_llms():
    """List all llm types"""
    return [
        llm.__name__
        for llm in llm_type_to_cls_dict.values()
        if llm.__name__ in settings.llms or settings.dev
    ]


def list_chain_types():
    """List all chain types"""
    return [
        chain.__annotations__["return"].__name__
        for chain in chains.loading.type_to_loader_dict.values()
        if chain.__annotations__["return"].__name__ in settings.chains or settings.dev
    ]


def list_memories():
    """List all memory types"""
    return [
        memory.__name__
        for memory in memory_type_to_cls_dict.values()
        if memory.__name__ in settings.memories or settings.dev
    ]


LANGCHAIN_TYPES_DICT = {
    k: list_function() for k, list_function in get_type_dict().items()
}

# Now we'll build a dict with Langchain types and ours

ALL_TYPES_DICT = {
    **LANGCHAIN_TYPES_DICT,
    "Custom": ["Custom Tool", "Python Function"],
}
