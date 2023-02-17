from fastapi import APIRouter, FastAPI
from langchain import OpenAI
from langchain.agents import initialize_agent
from interface import (
    DictableChain,
    DictableConversationalAgent,
    DictableMemory,
    DictableTool,
)
import signature
import list

# build router
router = APIRouter()
AGENT_TYPE = "conversational-react-description"
# define endpoints -> /chain, /agent, /memory, /prompt
# return a dict


@router.get("/")
def get_all():
    # tools = list.list_tools()
    return {
        "chains": {chain: signature.chain(chain) for chain in list.list_chains()},
        "agents": {agent: signature.agent(agent) for agent in list.list_agents()},
        "prompts": {prompt: signature.prompt(prompt) for prompt in list.list_prompts()},
        "llms": {llm: signature.llm(llm) for llm in list.list_llms()},
        # "utilities": {
        #     "template": {
        #         # utility: templates.utility(utility) for utility in list.list_utilities()
        #     }
        # },
        "memories": {
            memory: signature.memory(memory) for memory in list.list_memories()
        },
        # "document_loaders": {
        #     "template": {
        #         # memory: templates.document_loader(memory)
        #         # for memory in list.list_document_loaders()
        #     }
        # },
        # "vectorstores": {"template": {}},
        # "docstores": {"template": {}},
        # "tools": {
        #     tool: {"template": signature.tool(tool), **values}
        #     for tool, values in tools.items()
        # },
        "tools": {tool: signature.tool(tool) for tool in list.list_tools()},
    }


@router.post("/load")
def get_load(data: dict[str, str]) -> str:
    return "Hello Otávio!"


# @router.get("/chain")
# def get_chain():
#     llm = OpenAI(temperature=0)
#     chain = DictableChain(llm=llm)
#     return chain.to_dict()


# @router.get("/agent")
# def get_agent():
#     tools = [DictableTool(name="test", description="test", func=lambda x: x)]
#     llm = OpenAI(temperature=0)
#     return initialize_agent(llm=llm, tools=tools, memory=DictableMemory()).__dict__


# @router.get("/memory")
# def get_memory():
#     return DictableMemory().to_dict()


# @router.get("/prompt")
# def get_prompt():
#     return {"template": "template", "input_variables": "input_variables"}
