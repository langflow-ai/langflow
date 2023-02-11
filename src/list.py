from fastapi import APIRouter

from langchain import chains
from langchain import agents
from langchain import prompts
from langchain import llms
from langchain import utilities
from langchain.chains.conversation import memory


# build router
router = APIRouter(
    prefix="/list",
    tags=["list"],
)


@router.get("/")
def read_items():
    return ["chains", "agents", "prompts", "llms", "utilities", "memories"]


@router.get("/chains")
def chains():
    return chains.__all__


@router.get("/agents")
def agents():
    return agents.__all__


@router.get("/prompts")
def prompts():
    return prompts.__all__


@router.get("/llms")
def llms():
    return llms.__all__


@router.get("/utilities")
def utilities():
    return utilities.__all__


@router.get("/memories")
def memories():
    return memory.__all__
