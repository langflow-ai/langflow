from langchain.agents.agent import AgentExecutor
from langchain.chains.base import Chain
from langchain.document_loaders.base import BaseLoader
from langchain.llms.base import BaseLLM, BaseLanguageModel
from langchain.memory.chat_memory import BaseChatMemory
from langchain.prompts import PromptTemplate, ChatPromptTemplate, BasePromptTemplate
from langchain.schema import BaseOutputParser, BaseRetriever, Document
from langchain.schema.embeddings import Embeddings
from langchain.schema.memory import BaseMemory
from langchain.text_splitter import TextSplitter
from langchain.tools import Tool
from langchain.vectorstores.base import VectorStore
from typing import Union, Dict, Callable

# Type alias for more complex dicts
NestedDict = Dict[str, Union[str, Dict]]


class Data:
    pass


LANGCHAIN_BASE_TYPES = {
    "Chain": Chain,
    "AgentExecutor": AgentExecutor,
    "Tool": Tool,
    "BaseLLM": BaseLLM,
    "BaseLanguageModel": BaseLanguageModel,
    "PromptTemplate": PromptTemplate,
    "ChatPromptTemplate": ChatPromptTemplate,
    "BasePromptTemplate": BasePromptTemplate,
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
    "NestedDict": NestedDict,
    "Data": Data,
    "Callable": Callable,
}
