from langflow.interface.agents.base import agent_creator
from langflow.interface.chains.base import chain_creator
from langflow.interface.document_loaders.base import documentloader_creator
from langflow.interface.embeddings.base import embedding_creator
from langflow.interface.llms.base import llm_creator
from langflow.interface.memories.base import memory_creator
from langflow.interface.prompts.base import prompt_creator
from langflow.interface.text_splitters.base import textsplitter_creator
from langflow.interface.toolkits.base import toolkits_creator
from langflow.interface.tools.base import tool_creator
from langflow.interface.utilities.base import utility_creator
from langflow.interface.vector_store.base import vectorstore_creator
from langflow.interface.wrappers.base import wrapper_creator


def get_type_dict():
    return {
        "agents": agent_creator.to_list(),
        "prompts": prompt_creator.to_list(),
        "llms": llm_creator.to_list(),
        "tools": tool_creator.to_list(),
        "chains": chain_creator.to_list(),
        "memory": memory_creator.to_list(),
        "toolkits": toolkits_creator.to_list(),
        "wrappers": wrapper_creator.to_list(),
        "documentLoaders": documentloader_creator.to_list(),
        "vectorStore": vectorstore_creator.to_list(),
        "embeddings": embedding_creator.to_list(),
        "textSplitters": textsplitter_creator.to_list(),
        "utilities": utility_creator.to_list(),
    }


LANGCHAIN_TYPES_DICT = get_type_dict()

# Now we'll build a dict with Langchain types and ours

ALL_TYPES_DICT = {
    **LANGCHAIN_TYPES_DICT,
    "Custom": ["Custom Tool", "Python Function"],
}
