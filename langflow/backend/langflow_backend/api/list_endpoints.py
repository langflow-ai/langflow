from fastapi import APIRouter

from langchain import chains
from langchain import agents
from langchain import prompts
from langchain import llms
from langchain.chains.conversation import memory as memories
from langchain.agents.load_tools import get_all_tool_names
from langflow_backend.utils import util, allowed_components
from langflow_backend.custom import customs


# build router
router = APIRouter(
    prefix="/list",
    tags=["list"],
)


@router.get("/")
def read_items():
    """List all components"""
    return [
        "chains",
        "agents",
        "prompts",
        "llms",
        "tools",
    ]


@router.get("/chains")
def list_chains():
    """List all chain types"""
    return [
        chain.__annotations__["return"].__name__
        for chain in chains.loading.type_to_loader_dict.values()
        if chain.__annotations__["return"].__name__ in allowed_components.CHAINS
    ]


@router.get("/agents")
def list_agents():
    """List all agent types"""
    # return list(agents.loading.AGENT_TO_CLASS.keys())
    return [
        agent.__name__
        for agent in agents.loading.AGENT_TO_CLASS.values()
        if agent.__name__ in allowed_components.AGENTS
    ]


@router.get("/prompts")
def list_prompts():
    """List all prompt types"""
    custom_prompts = customs.get_custom_prompts()
    library_prompts = [
        prompt.__annotations__["return"].__name__
        for prompt in prompts.loading.type_to_loader_dict.values()
        if prompt.__annotations__["return"].__name__ in allowed_components.PROMPTS
    ]
    return library_prompts + list(custom_prompts.keys())


@router.get("/llms")
def list_llms():
    """List all llm types"""
    return [
        llm.__name__
        for llm in llms.type_to_cls_dict.values()
        if llm.__name__ in allowed_components.LLMS
    ]


@router.get("/memories")
def list_memories():
    """List all memory types"""
    return [memory.__name__ for memory in memories.type_to_cls_dict.values()]


@router.get("/tools")
def list_tools():
    """List all load tools"""

    tools = []

    for tool in get_all_tool_names():
        tool_params = util.get_tool_params(util.get_tools_dict(tool))
        if tool_params and tool_params["name"] in allowed_components.TOOLS:
            tools.append(tool_params["name"])

    return tools
