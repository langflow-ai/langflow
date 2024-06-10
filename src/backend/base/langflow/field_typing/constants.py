from typing import Callable, Dict, Text, Union

from langchain.agents.agent import AgentExecutor
from langchain.chains.base import Chain
from langchain.memory.chat_memory import BaseChatMemory
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseLanguageModel, BaseLLM
from langchain_core.memory import BaseMemory
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import BasePromptTemplate, ChatPromptTemplate, PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import Tool
from langchain_core.vectorstores import VectorStore
from langchain_text_splitters import TextSplitter

from langflow.field_typing.prompt import Prompt

# Type alias for more complex dicts
NestedDict = Dict[str, Union[str, Dict]]


class Object:
    pass


class Data:
    pass


class Code:
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
    "NestedDict": NestedDict,
    "Data": Data,
    "Text": Text,
    "Object": Object,
    "Callable": Callable,
    "Prompt": Prompt,
}
