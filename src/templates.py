from fastapi import APIRouter

from langchain import chains
from langchain import agents
from langchain import prompts
from langchain import llms
from langchain import utilities
from langchain.chains.conversation import memory as memories
from langchain import document_loaders
from langchain.agents.load_tools import (
    get_all_tool_names,
    _BASE_TOOLS,
    _LLM_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
)
import util

# build router
router = APIRouter(
    prefix="/templates",
    tags=["templates"],
)


@router.get("/chain")
def chain(name: str):
    # Raise error if name is not in chains
    if name not in chains.loading.type_to_loader_dict.keys():
        raise Exception(f"Prompt {name} not found.")
    _class = chains.loading.type_to_loader_dict[name].__annotations__["return"]
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__fields__.items()
    }


@router.get("/agent")
def agent(name: str):
    # Raise error if name is not in agents
    if name not in agents.loading.AGENT_TO_CLASS.keys():
        raise Exception(f"Prompt {name} not found.")
    _class = agents.loading.AGENT_TO_CLASS[name]
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__fields__.items()
    }


@router.get("/prompt")
def prompt(name: str):
    # Raise error if name is not in prompts
    if name not in prompts.loading.type_to_loader_dict.keys():
        raise Exception(f"Prompt {name} not found.")
    _class = prompts.loading.type_to_loader_dict[name].__annotations__["return"]
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__fields__.items()
    }


@router.get("/llm")
def llm(name: str):
    # Raise error if name is not in llms
    if name not in llms.type_to_cls_dict.keys():
        raise Exception(f"Prompt {name} not found.")
    _class = llms.type_to_cls_dict[name]
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__fields__.items()
    }


@router.get("/utility")
def utility(name: str):
    # Raise error if name is not in utilities
    if name not in utilities.__all__:
        raise Exception(f"Prompt {name} not found.")
    _class = getattr(utilities, name)
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__dict__["__fields__"].items()
    }


@router.get("/memory")
def memory(name: str):
    # Raise error if name is not in memory
    if name not in memories.type_to_cls_dict.keys():
        raise Exception(f"Prompt {name} not found.")
    _class = memories.type_to_cls_dict[name]
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__dict__["__fields__"].items()
    }


@router.get("/document_loader")
def document_loader(name: str):
    # Raise error if name is not in document_loader
    if name not in document_loaders.__all__:
        raise Exception(f"Prompt {name} not found.")
    _class = getattr(document_loaders, name)
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__fields__.items()
    }


@router.get("/tool")
def tool(name: str):
    # Raise error if name is not in tools
    if name not in get_all_tool_names():
        raise Exception(f"Tool {name} not found.")

    if name in _BASE_TOOLS:
        return {"parameters": []}
    elif name in _LLM_TOOLS:
        return {"parameters": ["llm"]}
    elif name in _EXTRA_LLM_TOOLS:
        _, extra_keys = _EXTRA_LLM_TOOLS[name]
        return {"parameters": ["llm"] + extra_keys}
    elif name in _EXTRA_OPTIONAL_TOOLS:
        _, extra_keys = _EXTRA_OPTIONAL_TOOLS[name]
        return {"parameters": extra_keys}
