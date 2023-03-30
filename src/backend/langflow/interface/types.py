from langflow.interface.agents import AgentCreator
from langflow.interface.listing import list_type
from langflow.interface.llms import LLMCreator
from langflow.interface.memories.base import MemoryCreator
from langflow.interface.prompts import PromptCreator
from langflow.interface.signature import get_signature
from langchain import chains
from langflow.interface.chains import ChainCreator
from langflow.interface.tools import ToolCreator


def get_type_list():
    """Get a list of all langchain types"""
    all_types = build_langchain_types_dict()

    # all_types.pop("tools")

    for key, value in all_types.items():
        all_types[key] = [item["template"]["_type"] for item in value.values()]

    return all_types


def build_langchain_types_dict():
    """Build a dictionary of all langchain types"""
    chain_creator = ChainCreator()
    agent_creator = AgentCreator()
    prompt_creator = PromptCreator()
    tool_creator = ToolCreator()
    llm_creator = LLMCreator()
    memory_creator = MemoryCreator()

    all_types = {}

    creators = [
        chain_creator,
        agent_creator,
        prompt_creator,
        llm_creator,
        memory_creator,
        tool_creator,
    ]

    all_types = {}
    for creator in creators:
        all_types.update(creator.to_dict())
    return all_types
