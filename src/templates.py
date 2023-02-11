from fastapi import APIRouter

from langchain import chains
from langchain import agents
from langchain import prompts
from langchain import llms
from langchain import utilities
from langchain.chains.conversation import memory


# build router
router = APIRouter(
    prefix="/templates",
    tags=["templates"],
)


@router.get("/chain")
def chain(name: str):
    # Raise error if name is not in chains
    if name not in chains.__all__:
        raise Exception(f"Prompt {name} not found.")
    _class = getattr(chains, name)
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__dict__["__fields__"].items()
    }


@router.get("/agent")
def agent(name: str):
    # Raise error if name is not in agents
    if name not in agents.__all__:
        raise Exception(f"Prompt {name} not found.")
    _class = getattr(agents, name)
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__dict__["__fields__"].items()
    }


@router.get("/prompt")
def prompt(name: str):
    # Raise error if name is not in prompts
    if name not in prompts.__all__:
        raise Exception(f"Prompt {name} not found.")
    _class = getattr(prompts, name)
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__dict__["__fields__"].items()
    }


@router.get("/llm")
def llm(name: str):
    # Raise error if name is not in llms
    if name not in llms.__all__:
        raise Exception(f"Prompt {name} not found.")
    _class = getattr(llms, name)
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__dict__["__fields__"].items()
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
    if name not in memory.__all__:
        raise Exception(f"Prompt {name} not found.")
    _class = getattr(memory, name)
    return {
        name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
        for name, value in _class.__dict__["__fields__"].items()
    }
