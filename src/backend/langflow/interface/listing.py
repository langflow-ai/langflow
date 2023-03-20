from langchain import chains, agents, prompts
from langflow.interface.custom_lists import llm_type_to_cls_dict
from langflow.custom import customs
from langflow.utils import util, allowed_components
from langchain.agents.load_tools import get_all_tool_names
from langchain.chains.conversation import memory as memories


def list_type(object_type: str):
    """List all components"""
    return {
        "chains": list_chain_types,
        "agents": list_agents,
        "prompts": list_prompts,
        "llms": list_llms,
        "tools": list_tools,
        "memories": list_memories,
    }.get(object_type, lambda: "Invalid type")()


def list_agents():
    """List all agent types"""
    # return list(agents.loading.AGENT_TO_CLASS.keys())
    return [
        agent.__name__
        for agent in agents.loading.AGENT_TO_CLASS.values()
        if agent.__name__ in allowed_components.AGENTS
    ]


def list_prompts():
    """List all prompt types"""
    custom_prompts = customs.get_custom_prompts()
    library_prompts = [
        prompt.__annotations__["return"].__name__
        for prompt in prompts.loading.type_to_loader_dict.values()
        if prompt.__annotations__["return"].__name__ in allowed_components.PROMPTS
    ]
    return library_prompts + list(custom_prompts.keys())


def list_tools():
    """List all load tools"""

    tools = []

    for tool in get_all_tool_names():
        tool_params = util.get_tool_params(util.get_tools_dict(tool))
        if tool_params and tool_params["name"] in allowed_components.TOOLS:
            tools.append(tool_params["name"])

    return tools


def list_llms():
    """List all llm types"""
    return [
        llm.__name__
        for llm in llm_type_to_cls_dict.values()
        if llm.__name__ in allowed_components.LLMS
    ]


def list_chain_types():
    """List all chain types"""
    return [
        chain.__annotations__["return"].__name__
        for chain in chains.loading.type_to_loader_dict.values()
        if chain.__annotations__["return"].__name__ in allowed_components.CHAINS
    ]


def list_memories():
    """List all memory types"""
    return [memory.__name__ for memory in memories.type_to_cls_dict.values()]
