from langchain import agents, chains, prompts

# from langchain.agents.load_tools import get_all_tool_names

from langflow.custom import customs
from langflow.interface.custom_lists import (
    llm_type_to_cls_dict,
    memory_type_to_cls_dict,
    get_tools_dict,
    docloaders
)
from langflow.settings import settings
from langflow.utils import util

# from langchain.docstore import docstores


def list_type(object_type: str):
    """List all components"""
    return {
        "chains": list_chain_types,
        "agents": list_agents,
        "prompts": list_prompts,
        "llms": list_llms,
        "memories": list_memories,
        # "docstores": list_docstores,
        "docloaders": list_docloaders,
        "tools": list_tools,
    }.get(object_type, lambda: "Invalid type")()


def list_agents():
    """List all agent types"""
    return [
        agent.__name__
        for agent in agents.loading.AGENT_TO_CLASS.values()
        if agent.__name__ in settings.agents or settings.dev
    ]


def list_prompts():
    """List all prompt types"""
    custom_prompts = customs.get_custom_prompts()
    library_prompts = [
        prompt.__annotations__["return"].__name__
        for prompt in prompts.loading.type_to_loader_dict.values()
        if prompt.__annotations__["return"].__name__ in settings.prompts or settings.dev
    ]
    return library_prompts + list(custom_prompts.keys())


def list_tools():
    """List all load tools"""

    tools = []

    tools_dict = get_tools_dict()

    for tool in tools_dict.keys():
        tool_params = util.get_tool_params(tools_dict[tool])
        if tool_params and (tool_params["name"] in settings.tools or settings.dev):
            tools.append(tool_params["name"])

    return tools

def list_docloaders():
    """List all docloaders tools"""

    tools = []

    for tool in docloaders.keys():
        tool_params = util.get_tool_params(docloaders[tool])
        if tool_params and (tool_params["name"] in settings.tools or settings.dev):
            tools.append(tool_params["name"])

    return tools


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
