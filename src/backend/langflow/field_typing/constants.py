from typing import Callable, Dict, Text, Union

from langchain.agents.agent import AgentExecutor
from langchain.chains.base import Chain
from langchain.document_loaders.base import BaseLoader
from langchain.llms.base import BaseLLM
from langchain.memory.chat_memory import BaseChatMemory
from langchain.prompts import BasePromptTemplate, ChatPromptTemplate, PromptTemplate
from langchain.schema import BaseOutputParser, BaseRetriever, Document
from langchain.schema.embeddings import Embeddings
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.memory import BaseMemory
from langchain.text_splitter import TextSplitter
from langchain.tools import Tool
from langchain_community.vectorstores import VectorStore

# Type alias for more complex dicts
NestedDict = Dict[str, Union[str, Dict]]


class Object:
    pass


class Data:
    pass


class Prompt:
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
