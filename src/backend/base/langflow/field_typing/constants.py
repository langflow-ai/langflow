from collections.abc import Callable
from typing import Text, TypeAlias, TypeVar

from langchain.agents.agent import AgentExecutor
from langchain.chains.base import Chain
from langchain.memory.chat_memory import BaseChatMemory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseLanguageModel, BaseLLM
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.memory import BaseMemory
from langchain_core.output_parsers import BaseLLMOutputParser, BaseOutputParser
from langchain_core.prompts import BasePromptTemplate, ChatPromptTemplate, PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import BaseTool, Tool
from langchain_core.vectorstores import VectorStore, VectorStoreRetriever
from langchain_text_splitters import TextSplitter

from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message

NestedDict: TypeAlias = dict[str, str | dict]
LanguageModel = TypeVar("LanguageModel", BaseLanguageModel, BaseLLM, BaseChatModel)
ToolEnabledLanguageModel = TypeVar("ToolEnabledLanguageModel", BaseLanguageModel, BaseLLM, BaseChatModel)
Memory = TypeVar("Memory", bound=BaseChatMessageHistory)

Retriever = TypeVar(
    "Retriever",
    BaseRetriever,
    VectorStoreRetriever,
)
OutputParser = TypeVar(
    "OutputParser",
    BaseOutputParser,
    BaseLLMOutputParser,
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
    "Memory": Memory,
    "BaseDocumentCompressor": BaseDocumentCompressor,
}
# Langchain base types plus Python base types
CUSTOM_COMPONENT_SUPPORTED_TYPES = {
    **LANGCHAIN_BASE_TYPES,
    "NestedDict": NestedDict,
    "Data": Data,
    "Message": Message,
    "Text": Text,  # noqa: UP019
    "Object": Object,
    "Callable": Callable,
    "LanguageModel": LanguageModel,
    "Retriever": Retriever,
    "DataFrame": DataFrame,
}

DEFAULT_IMPORT_STRING = """from langchain.agents.agent import AgentExecutor
from langchain.chains.base import Chain
from langchain.memory.chat_memory import BaseChatMemory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseLanguageModel, BaseLLM
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.memory import BaseMemory
from langchain_core.output_parsers import BaseLLMOutputParser, BaseOutputParser
from langchain_core.prompts import BasePromptTemplate, ChatPromptTemplate, PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents.compressor import BaseDocumentCompressor
from langchain_core.tools import BaseTool, Tool
from langchain_core.vectorstores import VectorStore, VectorStoreRetriever
from langchain_text_splitters import TextSplitter

from langflow.io import (
    BoolInput,
    CodeInput,
    DataFrameInput,
    DataInput,
    DefaultPromptField,
    DictInput,
    DropdownInput,
    FileInput,
    FloatInput,
    HandleInput,
    IntInput,
    LinkInput,
    MessageInput,
    MessageTextInput,
    MultilineInput,
    MultilineSecretInput,
    MultiselectInput,
    NestedDictInput,
    Output,
    PromptInput,
    SecretStrInput,
    SliderInput,
    StrInput,
    TableInput,
)
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
"""
