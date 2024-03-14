from cachetools import LRUCache, cached
from fastapi import HTTPException
from loguru import logger

from langflow_base.api.utils import get_new_key
from langflow_base.interface.agents.base import agent_creator
from langflow_base.interface.chains.base import chain_creator
from langflow_base.interface.custom.base import custom_component_creator
from langflow_base.interface.custom.custom_component import CustomComponent
from langflow_base.interface.custom.directory_reader import DirectoryReader
from langflow_base.interface.custom.utils import extract_inner_type
from langflow_base.interface.document_loaders.base import documentloader_creator
from langflow_base.interface.embeddings.base import embedding_creator
from langflow_base.interface.importing.utils import eval_custom_component_code
from langflow_base.interface.llms.base import llm_creator
from langflow_base.interface.memories.base import memory_creator
from langflow_base.interface.output_parsers.base import output_parser_creator
from langflow_base.interface.prompts.base import prompt_creator
from langflow_base.interface.retrievers.base import retriever_creator
from langflow_base.interface.text_splitters.base import textsplitter_creator
from langflow_base.interface.toolkits.base import toolkits_creator
from langflow_base.interface.tools.base import tool_creator
from langflow_base.interface.utilities.base import utility_creator
from langflow_base.interface.vector_store.base import vectorstore_creator
from langflow_base.interface.wrappers.base import wrapper_creator
from langflow_base.template.field.base import TemplateField
from langflow_base.template.frontend_node.constants import CLASSES_TO_REMOVE
from langflow_base.template.frontend_node.custom_components import CustomComponentFrontendNode
from langflow_base.utils.util import get_base_classes


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
        # prompt_creator,
        llm_creator,
        memory_creator,
        tool_creator,
        toolkits_creator,
        wrapper_creator,
        embedding_creator,
        # vectorstore_creator,
        documentloader_creator,
        textsplitter_creator,
        # utility_creator,
        output_parser_creator,
        retriever_creator,
    ]

    all_types = {}
    for creator in creators:
        created_types = creator.to_dict()
        if created_types[creator.type_name].values():
            all_types.update(created_types)

    return all_types


def get_all_types_dict(components_paths):
    """Get all types dictionary combining native and custom components."""
    native_components = build_langchain_types_dict()
    custom_components_from_file = build_custom_components(components_paths=components_paths)
    return merge_nested_dicts_with_renaming(native_components, custom_components_from_file)


def get_all_components(components_paths, as_dict=False):
    """Get all components names combining native and custom components."""
    all_types_dict = get_all_types_dict(components_paths)
    components = [] if not as_dict else {}
    for category in all_types_dict.values():
        for component in category.values():
            component["name"] = component["display_name"]
            if as_dict:
                components[component["name"]] = component
            else:
                components.append(component)
    return components
