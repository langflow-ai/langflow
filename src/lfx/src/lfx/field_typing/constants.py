"""Constants for field typing used throughout lfx package."""

import importlib.util
from collections.abc import Callable
from typing import Text, TypeAlias, TypeVar

# Safe imports that don't create circular dependencies
try:
    from langchain_classic.agents import AgentExecutor
    from langchain_classic.base_memory import BaseMemory
    from langchain_classic.chains.base import Chain
    from langchain_classic.memory.chat_memory import BaseChatMemory
    from langchain_core.chat_history import BaseChatMessageHistory
    from langchain_core.document_loaders import BaseLoader
    from langchain_core.documents import Document
    from langchain_core.documents.compressor import BaseDocumentCompressor
    from langchain_core.embeddings import Embeddings
    from langchain_core.language_models import BaseLanguageModel, BaseLLM
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.output_parsers import BaseLLMOutputParser, BaseOutputParser
    from langchain_core.prompts import BasePromptTemplate, ChatPromptTemplate, PromptTemplate
    from langchain_core.retrievers import BaseRetriever
    from langchain_core.tools import BaseTool, Tool
    from langchain_core.vectorstores import VectorStore, VectorStoreRetriever
    from langchain_text_splitters import TextSplitter
except (ImportError, OSError):
    # Create stub types if langchain is not available, or if a transitive native
    # dependency (e.g. PyTorch's c10.dll on a Windows machine without the Microsoft
    # Visual C++ Redistributable) raises OSError: [WinError 126] while loading.
    # Without the OSError catch, this propagated up through transformers → torch
    # and crashed `langflow --version` on fresh Windows installs.
    class AgentExecutor:
        pass

    class Chain:
        pass

    class BaseChatMemory:
        pass

    class BaseChatMessageHistory:
        pass

    class BaseLoader:
        pass

    class Document:
        pass

    class BaseDocumentCompressor:
        pass

    class Embeddings:
        pass

    class BaseLanguageModel:
        pass

    class BaseLLM:
        pass

    class BaseChatModel:
        pass

    class BaseMemory:
        pass

    class BaseLLMOutputParser:
        pass

    class BaseOutputParser:
        pass

    class BasePromptTemplate:
        pass

    class ChatPromptTemplate:
        pass

    class PromptTemplate:
        pass

    class BaseRetriever:
        pass

    class BaseTool:
        pass

    class Tool:
        pass

    class VectorStore:
        pass

    class VectorStoreRetriever:
        pass

    class TextSplitter:
        pass


# Import lfx schema types (avoid circular deps)
from lfx.schema.data import JSON, Data

# Note: DataFrame and Table are deferred to avoid eager pandas load at module import time.
# They are resolved lazily via the module-level __getattr__ at the bottom of this file,
# which keeps `from lfx.field_typing.constants import DataFrame` working for callers.
# This is a partial IMP-07 pattern (PEP 562) applied early to unblock IMP-02's
# measurable-delta requirement per CONTEXT.md D-10.

# Type aliases
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
    """Generic object type for custom components."""


class Code:
    """Code type for custom components."""


# Langchain base types mapping
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

# Langchain base types plus Python base types.
# DataFrame and Table are intentionally omitted here to avoid eager pandas load;
# callers that need their runtime classes go through the module-level __getattr__
# below (or import them directly from lfx.schema.dataframe). The upstream caller
# lfx/custom/validate.py only reads .keys() from this dict, so DataFrame/Table
# are re-injected as keys with sentinel values via _add_deferred_types below.
CUSTOM_COMPONENT_SUPPORTED_TYPES = {
    **LANGCHAIN_BASE_TYPES,
    "NestedDict": NestedDict,
    "Data": Data,
    "JSON": JSON,
    "Text": Text,  # noqa: UP019
    "Object": Object,
    "Callable": Callable,
    "LanguageModel": LanguageModel,
    "Retriever": Retriever,
}

# Record DataFrame and Table as supported-type names without materializing their
# classes (and therefore without loading pandas). The langflow backend extension
# at langflow/field_typing/constants.py re-binds these to the real classes when
# langflow is installed; lfx-only callers resolve them via __getattr__.
_DEFERRED_SUPPORTED_TYPE_NAMES: tuple[str, ...] = ("DataFrame", "Table")
for _name in _DEFERRED_SUPPORTED_TYPE_NAMES:
    CUSTOM_COMPONENT_SUPPORTED_TYPES[_name] = None

# Default import string for component code generation
LANGCHAIN_IMPORT_STRING = """from langchain_classic.agents import AgentExecutor
from langchain_classic.base_memory import BaseMemory
from langchain_classic.chains.base import Chain
from langchain_classic.memory.chat_memory import BaseChatMemory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseLanguageModel, BaseLLM
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import BaseLLMOutputParser, BaseOutputParser
from langchain_core.prompts import BasePromptTemplate, ChatPromptTemplate, PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents.compressor import BaseDocumentCompressor
from langchain_core.tools import BaseTool, Tool
from langchain_core.vectorstores import VectorStore, VectorStoreRetriever
from langchain_text_splitters import TextSplitter
"""


DEFAULT_IMPORT_STRING = """

from lfx.io import (
    BoolInput,
    CodeInput,
    DataInput,
    DictInput,
    DropdownInput,
    FileInput,
    FloatInput,
    HandleInput,
    IntInput,
    JSONInput,
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
from lfx.schema.data import JSON, Data
from lfx.schema.dataframe import DataFrame, Table
"""

if importlib.util.find_spec("langchain") is not None:
    DEFAULT_IMPORT_STRING = LANGCHAIN_IMPORT_STRING + DEFAULT_IMPORT_STRING


def __getattr__(name: str):
    """Lazy resolution for deferred supported types.

    Keeps `from lfx.field_typing.constants import DataFrame` (and Table) working
    without paying the pandas import cost at module load. This is a partial
    application of the PEP 562 pattern IMP-07 will fully adopt for all 11
    langchain_core symbols; applied here only for DataFrame/Table so IMP-02
    can reach GREEN on its targeted modules.
    """
    if name in _DEFERRED_SUPPORTED_TYPE_NAMES:
        from lfx.schema.dataframe import DataFrame as _DataFrame
        from lfx.schema.dataframe import Table as _Table

        resolved = {"DataFrame": _DataFrame, "Table": _Table}[name]
        # Also backfill the dict so downstream callers that use the values
        # (not just keys) get the real class after first access.
        CUSTOM_COMPONENT_SUPPORTED_TYPES[name] = resolved
        return resolved
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
