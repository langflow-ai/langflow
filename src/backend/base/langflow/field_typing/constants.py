from typing import Callable, Dict, Text, TypeAlias, TypeVar, Union

from langchain.agents.agent import AgentExecutor
from langchain.chains.base import Chain
from langchain.memory.chat_memory import BaseChatMemory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseLanguageModel, BaseLLM
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.memory import BaseMemory
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import BasePromptTemplate, ChatPromptTemplate, PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import BaseTool, Tool
from langchain_core.vectorstores import VectorStore, VectorStoreRetriever
from langchain_text_splitters import TextSplitter

from langflow.schema.data import Data
from langflow.schema.message import Message

NestedDict: TypeAlias = Dict[str, Union[str, Dict]]
LanguageModel = TypeVar("LanguageModel", BaseLanguageModel, BaseLLM, BaseChatModel)
ToolEnabledLanguageModel = TypeVar("ToolEnabledLanguageModel", BaseLanguageModel, BaseLLM, BaseChatModel)
Retriever = TypeVar(
    "Retriever",
    BaseRetriever,
    VectorStoreRetriever,
)


class Object:
    pass


class Code:
    pass


LANGCHAIN_BASE_TYPES = {
    "Chain": Chain,
    "AgentExecutor": AgentExecutor,
    "BaseTool": BaseTool,
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
    "BaseChatModel": BaseChatModel,
    "BaseChatMessageHistory": BaseChatMessageHistory,
}
# Langchain base types plus Python base types
CUSTOM_COMPONENT_SUPPORTED_TYPES = {
    **LANGCHAIN_BASE_TYPES,
    "NestedDict": NestedDict,
    "Data": Data,
    "Message": Message,
    "Text": Text,
    "Object": Object,
    "Callable": Callable,
    "LanguageModel": LanguageModel,
    "Retriever": Retriever,
}
