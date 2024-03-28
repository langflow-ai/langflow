from langflow.graph.vertex import types
from langflow.interface.agents.base import agent_creator
from langflow.interface.chains.base import chain_creator
from langflow.interface.custom.base import custom_component_creator
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
from langflow.interface.wrappers.base import wrapper_creator
from langflow.utils.lazy_load import LazyLoadDictBase


class VertexTypesDict(LazyLoadDictBase):
    def __init__(self):
        self._all_types_dict = None

    @property
    def VERTEX_TYPE_MAP(self):
        return self.all_types_dict

    def _build_dict(self):
        langchain_types_dict = self.get_type_dict()
        return {
            **langchain_types_dict,
        }

    def get_custom_component_vertex_type(self):
        return types.CustomComponentVertex

    def get_type_dict(self):
        return {
            **{t: types.CustomComponentVertex for t in custom_component_creator.to_list()},
        }


lazy_load_vertex_dict = VertexTypesDict()
