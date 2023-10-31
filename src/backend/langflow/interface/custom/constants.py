from langchain.prompts import PromptTemplate
from langchain.chains.base import Chain
from langchain.document_loaders.base import BaseLoader
from langchain.schema.embeddings import Embeddings
from langchain.llms.base import BaseLLM
from langchain.schema import BaseRetriever, Document
from langchain.text_splitter import TextSplitter
from langchain.tools import Tool
from langchain.vectorstores.base import VectorStore
from langchain.schema import BaseOutputParser
from langchain.schema.memory import BaseMemory
from langchain.memory.chat_memory import BaseChatMemory
from langchain.agents.agent import AgentExecutor
from typing import Text

LANGCHAIN_BASE_TYPES = {
    "Chain": Chain,
    "AgentExecutor": AgentExecutor,
    "Tool": Tool,
    "BaseLLM": BaseLLM,
    "PromptTemplate": PromptTemplate,
    "BaseLoader": BaseLoader,
    "Document": Document,
    "TextSplitter": TextSplitter,
    "VectorStore": VectorStore,
    "Embeddings": Embeddings,
    "BaseRetriever": BaseRetriever,
    "BaseOutputParser": BaseOutputParser,
    "BaseMemory": BaseMemory,
    "BaseChatMemory": BaseChatMemory,
}

# Langchain base types plus Python base types
CUSTOM_COMPONENT_SUPPORTED_TYPES = {
    **LANGCHAIN_BASE_TYPES,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "Text": Text,
}


DEFAULT_CUSTOM_COMPONENT_CODE = """from langflow import CustomComponent

from langflow.field_typing import (
    Tool,
    PromptTemplate,
    Chain,
    BaseChatMemory,
    BaseLLM,
    BaseLoader,
    BaseMemory,
    BaseOutputParser,
    BaseRetriever,
    VectorStore,
    Embeddings,
    TextSplitter,
    Document,
    AgentExecutor,
    NestedDict,
    Data,
)


class Component(CustomComponent):
    display_name: str = "Custom Component"
    description: str = "Create any custom component you want!"

    def build_config(self):
        return {"param": {"display_name": "Parameter"}}

    def build(self, param: Data) -> Data:
        return param

"""
