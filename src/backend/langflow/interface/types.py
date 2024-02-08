from concurrent.futures import ThreadPoolExecutor

from cachetools import LRUCache, cached

from cachetools import LRUCache, cached
from langflow.interface.agents.base import agent_creator
from langflow.interface.chains.base import chain_creator
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
        # vectorstore_creator,
        documentloader_creator,
        textsplitter_creator,
        utility_creator,
        output_parser_creator,
        retriever_creator,
    ]

    all_types = []
    for creator in creators:
        created_types = creator.to_list_of_dicts()
        all_types.extend(created_types)

    return all_types


def get_all_types_list(settings_service):
    """Get all types list by running two functions in parallel and merging their results."""

    # Define a function that wraps each of the target functions
    def run_in_executor(executor, func, *args):
        return executor.submit(func, *args)

    with ThreadPoolExecutor() as executor:
        # Schedule both functions to run in parallel
        future_native = run_in_executor(executor, build_langchain_types_dict)
        future_custom = run_in_executor(executor, build_custom_components, settings_service)

        # Wait for both futures to complete and retrieve their results
        native_components = future_native.result()
        custom_components_from_file = future_custom.result()

    # Merge the two lists and return
    return native_components + custom_components_from_file
