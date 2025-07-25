from typing import Any

from .constants import (
    AgentExecutor,
    BaseChatMemory,
    BaseChatModel,
    BaseDocumentCompressor,
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
    LanguageModel,
    NestedDict,
    Object,
    PromptTemplate,
    Retriever,
    Text,
    TextSplitter,
    Tool,
    VectorStore,
)
from .range_spec import RangeSpec


def _import_input_class():
    from lfx.template.field.base import Input

    return Input


def _import_output_class():
    from lfx.template.field.base import Output

    return Output


def __getattr__(name: str) -> Any:
    # This is to avoid circular imports
    if name == "Input":
        return _import_input_class()
        return RangeSpec
    if name == "Output":
        return _import_output_class()
    # The other names should work as if they were imported from constants
    # Import the constants module langflow.field_typing.constants
    from . import constants

    return getattr(constants, name)


__all__ = [
    "AgentExecutor",
    "BaseChatMemory",
    "BaseChatModel",
    "BaseDocumentCompressor",
    "BaseLLM",
    "BaseLanguageModel",
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
    "LanguageModel",
    "NestedDict",
    "Object",
    "PromptTemplate",
    "RangeSpec",
    "Retriever",
    "Text",
    "TextSplitter",
    "Tool",
    "VectorStore",
]
