from langflow.interface.listing import list_type
from langflow.interface.signature import get_signature


def get_type_list():
    """Get a list of all langchain types"""
    all_types = build_langchain_types_dict()

    all_types.pop("tools")

    for key, value in all_types.items():
        all_types[key] = [item["template"]["_type"] for item in value.values()]

    return all_types


def build_langchain_types_dict():
    """Build a dictionary of all langchain types"""

    return {
        "chains": {
            chain: get_signature(chain, "chains") for chain in list_type("chains")
        },
        "agents": {
            agent: get_signature(agent, "agents") for agent in list_type("agents")
        },
        "prompts": {
            prompt: get_signature(prompt, "prompts") for prompt in list_type("prompts")
        },
        "llms": {llm: get_signature(llm, "llms") for llm in list_type("llms")},
        "memories": {
            memory: get_signature(memory, "memories")
            for memory in list_type("memories")
        },
        "tools": {tool: get_signature(tool, "tools") for tool in list_type("tools")},
    }
