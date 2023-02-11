from fastapi import APIRouter, FastAPI
from langchain import OpenAI
from langchain.agents import initialize_agent
from interface import (
    DictableChain,
    DictableConversationalAgent,
    DictableMemory,
    DictableTool,
)

# build router
router = APIRouter()
AGENT_TYPE = "conversational-react-description"
# define endpoints -> /chain, /agent, /memory, /prompt
# return a dict
@router.get("/chain")
def get_chain():
    llm = OpenAI(temperature=0)
    chain = DictableChain(llm=llm)
    return chain.to_dict()


@router.get("/agent")
def get_agent():
    tools = [DictableTool(name="test", description="test", func=lambda x: x)]
    llm = OpenAI(temperature=0)
    return initialize_agent(llm=llm, tools=tools, memory=DictableMemory()).__dict__


@router.get("/memory")
def get_memory():
    return DictableMemory().to_dict()


@router.get("/prompt")
def get_prompt():
    return {"template": "template", "input_variables": "input_variables"}
