from cachetools import LRUCache, cached
from langflow.interface.agents.base import agent_creator
from langflow.interface.chains.base import chain_creator
from langflow.interface.custom.directory_reader.utils import merge_nested_dicts_with_renaming
from langflow.interface.custom.utils import build_custom_components
from langflow.interface.document_loaders.base import documentloader_creator
from langflow.interface.embeddings.base import embedding_creator
from langflow.interface.llms.base import llm_creator
from langflow.interface.memories.base import memory_creator
from langflow.interface.output_parsers.base import output_parser_creator
from langflow.interface.prompts.base import prompt_creator
from langflow.interface.retrievers.base import retriever_creator
from langflow.interface.text_splitters.base import textsplitter_creator
from langflow.interface.toolkits.base import toolkits_creator
from langflow.interface.tools.base import tool_creator
from langflow.interface.utilities.base import utility_creator
from langflow.interface.vector_store.base import vectorstore_creator
from langflow.interface.wrappers.base import wrapper_creator


# Used to get the base_classes list
def get_type_list():
    """Get a list of all langchain types"""
    all_types = build_langchain_types_dict()

    # all_types.pop("tools")

    for key, value in all_types.items():
        all_types[key] = [item["template"]["_type"] for item in value.values()]

    return all_types


@cached(LRUCache(maxsize=1))
def build_langchain_types_dict():  # sourcery skip: dict-assign-update-to-union
    """Build a dictionary of all langchain types"""
    all_types = {}

    creators = [
        chain_creator,
        agent_creator,
        prompt_creator,
        llm_creator,
        memory_creator,
        tool_creator,
        toolkits_creator,
        wrapper_creator,
        embedding_creator,
        vectorstore_creator,
        documentloader_creator,
        textsplitter_creator,
        utility_creator,
        output_parser_creator,
        retriever_creator,
    ]

    all_types = {}
    for creator in creators:
        created_types = creator.to_dict()
        if created_types[creator.type_name].values():
            all_types.update(created_types)

    return all_types


def get_all_types_dict(settings_service):
    """Get all types dictionary combining native and custom components."""
    native_components = build_langchain_types_dict()
    custom_components_from_file = build_custom_components(settings_service)
    return merge_nested_dicts_with_renaming(native_components, custom_components_from_file)
