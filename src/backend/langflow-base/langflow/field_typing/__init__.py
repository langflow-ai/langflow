from typing import Any

from .constants import (
    AgentExecutor,
    BaseChatMemory,
    BaseChatModel,
    BaseLanguageModel,
    BaseLLM,
    BaseLoader,
    BaseMemory,
    BaseOutputParser,
    BasePromptTemplate,
    BaseRetriever,
    Callable,
    Chain,
    ChatPromptTemplate,
    Code,
    Data,
    Document,
    Embeddings,
    NestedDict,
    Object,
    PromptTemplate,
    Retriever,
    Text,
    TextSplitter,
    Tool,
    VectorStore,
    LanguageModel,
)
from .range_spec import RangeSpec


def _import_input_class():
    from langflow.template.field.base import Input

    return Input


def _import_output_class():
    from langflow.template.field.base import Output

    return Output


def __getattr__(name: str) -> Any:
    # This is to avoid circular imports
    if name == "Input":
        return _import_input_class()
        return RangeSpec
    elif name == "Output":
        return _import_output_class()
    # The other names should work as if they were imported from constants
    # Import the constants module langflow.field_typing.constants
    from . import constants

    return getattr(constants, name)


__all__ = [
    "AgentExecutor",
    "BaseChatMemory",
    "BaseLanguageModel",
    "BaseLLM",
    "BaseLoader",
    "BaseMemory",
    "BaseOutputParser",
    "BasePromptTemplate",
    "BaseRetriever",
    "Callable",
    "Chain",
    "ChatPromptTemplate",
    "Code",
    "Data",
    "Document",
    "Embeddings",
    "Input",
    "NestedDict",
    "Object",
    "PromptTemplate",
    "RangeSpec",
    "TextSplitter",
    "Tool",
    "VectorStore",
    "BaseChatModel",
    "Retriever",
    "Text",
    "LanguageModel",
]
