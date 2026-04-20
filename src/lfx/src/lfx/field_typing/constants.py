"""Constants for field typing used throughout lfx package.

This module uses PEP 562 module ``__getattr__`` to lazily resolve langchain
classes and type-var-derived symbols. The motivation is cold-start: loading
this module used to pull ``langchain_classic`` and ~130 ``langchain_core``
submodules even when the caller only needed a type name for an annotation.
Now these imports happen on first attribute access, with stub-class fallback
on ``ImportError`` or ``OSError`` (the latter covers Windows c10.dll
failures when torch native deps are absent; see
``tests/unit/field_typing/test_lazy_imports.py``).
"""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Callable
from typing import Any, TypeAlias, TypeVar

# ``Text`` is re-exported as a public name because downstream modules (notably
# ``lfx.template.field.base``) import it as ``from lfx.field_typing import Text``.
# In Python 3.x ``typing.Text`` is ``str``; we keep the alias so callers that
# rely on the name continue to work without touching them.
Text = str

from lfx.schema.data import JSON, Data  # noqa: E402

# -- Stub classes (used on ImportError/OSError fallback) ---------------------


class AgentExecutor:  # pragma: no cover - fallback stub
    pass


class Chain:  # pragma: no cover - fallback stub
    pass


class BaseChatMemory:  # pragma: no cover - fallback stub
    pass


class BaseChatMessageHistory:  # pragma: no cover - fallback stub
    pass


class BaseLoader:  # pragma: no cover - fallback stub
    pass


class Document:  # pragma: no cover - fallback stub
    pass


class BaseDocumentCompressor:  # pragma: no cover - fallback stub
    pass


class Embeddings:  # pragma: no cover - fallback stub
    pass


class BaseLanguageModel:  # pragma: no cover - fallback stub
    pass


class BaseLLM:  # pragma: no cover - fallback stub
    pass


class BaseChatModel:  # pragma: no cover - fallback stub
    pass


class BaseMemory:  # pragma: no cover - fallback stub
    pass


class BaseLLMOutputParser:  # pragma: no cover - fallback stub
    pass


class BaseOutputParser:  # pragma: no cover - fallback stub
    pass


class BasePromptTemplate:  # pragma: no cover - fallback stub
    pass


class ChatPromptTemplate:  # pragma: no cover - fallback stub
    pass


class PromptTemplate:  # pragma: no cover - fallback stub
    pass


class BaseRetriever:  # pragma: no cover - fallback stub
    pass


class BaseTool:  # pragma: no cover - fallback stub
    pass


class Tool:  # pragma: no cover - fallback stub
    pass


class VectorStore:  # pragma: no cover - fallback stub
    pass


class VectorStoreRetriever:  # pragma: no cover - fallback stub
    pass


class TextSplitter:  # pragma: no cover - fallback stub
    pass


# -- Local non-langchain types (always eager) --------------------------------


class Object:
    """Generic object type for custom components."""


class Code:
    """Code type for custom components."""


NestedDict: TypeAlias = dict[str, str | dict]


# -- Stub registry (module-level stub class objects indexed by name) ---------
# Captured at import time so ``_resolve_langchain_symbol`` can return the
# stub even after ``globals()[name]`` has been overwritten by a cached real
# resolution (needed when a test reloads the module and monkey-patches the
# import to raise).

_STUBS: dict[str, type] = {
    "AgentExecutor": AgentExecutor,
    "Chain": Chain,
    "BaseChatMemory": BaseChatMemory,
    "BaseChatMessageHistory": BaseChatMessageHistory,
    "BaseLoader": BaseLoader,
    "Document": Document,
    "BaseDocumentCompressor": BaseDocumentCompressor,
    "Embeddings": Embeddings,
    "BaseLanguageModel": BaseLanguageModel,
    "BaseLLM": BaseLLM,
    "BaseChatModel": BaseChatModel,
    "BaseMemory": BaseMemory,
    "BaseLLMOutputParser": BaseLLMOutputParser,
    "BaseOutputParser": BaseOutputParser,
    "BasePromptTemplate": BasePromptTemplate,
    "ChatPromptTemplate": ChatPromptTemplate,
    "PromptTemplate": PromptTemplate,
    "BaseRetriever": BaseRetriever,
    "BaseTool": BaseTool,
    "Tool": Tool,
    "VectorStore": VectorStore,
    "VectorStoreRetriever": VectorStoreRetriever,
    "TextSplitter": TextSplitter,
}


# -- Symbol resolution table -------------------------------------------------
# Maps a public symbol name to (submodule_path, attribute_name). Accessed by
# ``__getattr__`` below. Each entry resolves lazily on first access; failure
# falls back to the stub class of the same name defined above.

_LANGCHAIN_SYMBOLS: dict[str, tuple[str, str]] = {
    "AgentExecutor": ("langchain_classic.agents", "AgentExecutor"),
    "BaseMemory": ("langchain_classic.base_memory", "BaseMemory"),
    "Chain": ("langchain_classic.chains.base", "Chain"),
    "BaseChatMemory": ("langchain_classic.memory.chat_memory", "BaseChatMemory"),
    "BaseChatMessageHistory": ("langchain_core.chat_history", "BaseChatMessageHistory"),
    "BaseLoader": ("langchain_core.document_loaders", "BaseLoader"),
    "Document": ("langchain_core.documents", "Document"),
    "BaseDocumentCompressor": ("langchain_core.documents.compressor", "BaseDocumentCompressor"),
    "Embeddings": ("langchain_core.embeddings", "Embeddings"),
    "BaseLanguageModel": ("langchain_core.language_models", "BaseLanguageModel"),
    "BaseLLM": ("langchain_core.language_models", "BaseLLM"),
    "BaseChatModel": ("langchain_core.language_models.chat_models", "BaseChatModel"),
    "BaseLLMOutputParser": ("langchain_core.output_parsers", "BaseLLMOutputParser"),
    "BaseOutputParser": ("langchain_core.output_parsers", "BaseOutputParser"),
    "BasePromptTemplate": ("langchain_core.prompts", "BasePromptTemplate"),
    "ChatPromptTemplate": ("langchain_core.prompts", "ChatPromptTemplate"),
    "PromptTemplate": ("langchain_core.prompts", "PromptTemplate"),
    "BaseRetriever": ("langchain_core.retrievers", "BaseRetriever"),
    "BaseTool": ("langchain_core.tools", "BaseTool"),
    "Tool": ("langchain_core.tools", "Tool"),
    "VectorStore": ("langchain_core.vectorstores", "VectorStore"),
    "VectorStoreRetriever": ("langchain_core.vectorstores", "VectorStoreRetriever"),
    "TextSplitter": ("langchain_text_splitters", "TextSplitter"),
}


_TYPEVARS: frozenset[str] = frozenset(
    {"LanguageModel", "ToolEnabledLanguageModel", "Memory", "Retriever", "OutputParser"}
)


_DEFERRED_SUPPORTED_TYPE_NAMES: tuple[str, ...] = ("DataFrame", "Table")


def _resolve_langchain_symbol(name: str) -> Any:
    """Return the real langchain class if importable, else the module-level stub."""
    module_path, attr = _LANGCHAIN_SYMBOLS[name]
    try:
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    except (ImportError, OSError):
        # Import failed (langchain not installed, or a transitive native dep
        # like torch's c10.dll failed with ``OSError: [WinError 126]`` on
        # Windows without the MSVC redistributable). Fall back to the stub
        # class of the same name captured in ``_STUBS`` at module load time.
        return _STUBS[name]


def _get_langchain(name: str) -> Any:
    """Return the cached or freshly-resolved langchain class for ``name``."""
    cached = globals().get(name)
    # ``cached`` is either a real class, a stub class, or ``None`` if never
    # resolved. Because both stubs and real classes are truthy and non-None,
    # a simple identity check on ``None`` is enough to decide whether to
    # resolve.
    if cached is None:
        cached = _resolve_langchain_symbol(name)
        globals()[name] = cached
    return cached


def _build_typevar(name: str) -> TypeVar:
    """Construct the requested TypeVar with constraints resolved lazily.

    Each branch binds the result to a variable that matches the TypeVar name
    so ruff's ``PLC0132`` (TypeVar-name-mismatch) stays quiet. The built
    value is cached back into ``globals()`` under ``name`` so subsequent
    lookups are O(1).
    """
    if name == "LanguageModel":
        LanguageModel = TypeVar(
            "LanguageModel",
            _get_langchain("BaseLanguageModel"),
            _get_langchain("BaseLLM"),
            _get_langchain("BaseChatModel"),
        )
        built: TypeVar = LanguageModel
    elif name == "ToolEnabledLanguageModel":
        ToolEnabledLanguageModel = TypeVar(
            "ToolEnabledLanguageModel",
            _get_langchain("BaseLanguageModel"),
            _get_langchain("BaseLLM"),
            _get_langchain("BaseChatModel"),
        )
        built = ToolEnabledLanguageModel
    elif name == "Memory":
        Memory = TypeVar("Memory", bound=_get_langchain("BaseChatMessageHistory"))
        built = Memory
    elif name == "Retriever":
        Retriever = TypeVar(
            "Retriever",
            _get_langchain("BaseRetriever"),
            _get_langchain("VectorStoreRetriever"),
        )
        built = Retriever
    elif name == "OutputParser":
        OutputParser = TypeVar(
            "OutputParser",
            _get_langchain("BaseOutputParser"),
            _get_langchain("BaseLLMOutputParser"),
        )
        built = OutputParser
    else:
        msg = f"unknown typevar: {name}"
        raise AttributeError(msg)
    globals()[name] = built
    return built


def _get_typevar(name: str) -> TypeVar:
    """Return the cached TypeVar for ``name`` or build it now."""
    cached = globals().get(name)
    if cached is not None:
        return cached
    return _build_typevar(name)


def _build_LANGCHAIN_BASE_TYPES() -> dict[str, Any]:  # noqa: N802 - public dict name
    """Materialize the ``LANGCHAIN_BASE_TYPES`` dict lazily."""
    return {
        "Chain": _get_langchain("Chain"),
        "AgentExecutor": _get_langchain("AgentExecutor"),
        "BaseTool": _get_langchain("BaseTool"),
        "Tool": _get_langchain("Tool"),
        "BaseLLM": _get_langchain("BaseLLM"),
        "BaseLanguageModel": _get_langchain("BaseLanguageModel"),
        "PromptTemplate": _get_langchain("PromptTemplate"),
        "ChatPromptTemplate": _get_langchain("ChatPromptTemplate"),
        "BasePromptTemplate": _get_langchain("BasePromptTemplate"),
        "BaseLoader": _get_langchain("BaseLoader"),
        "Document": _get_langchain("Document"),
        "TextSplitter": _get_langchain("TextSplitter"),
        "VectorStore": _get_langchain("VectorStore"),
        "Embeddings": _get_langchain("Embeddings"),
        "BaseRetriever": _get_langchain("BaseRetriever"),
        "BaseOutputParser": _get_langchain("BaseOutputParser"),
        "BaseMemory": _get_langchain("BaseMemory"),
        "BaseChatMemory": _get_langchain("BaseChatMemory"),
        "BaseChatModel": _get_langchain("BaseChatModel"),
        "Memory": _get_typevar("Memory"),
        "BaseDocumentCompressor": _get_langchain("BaseDocumentCompressor"),
    }


def _build_CUSTOM_COMPONENT_SUPPORTED_TYPES() -> dict[str, Any]:  # noqa: N802 - public dict name
    """Materialize the ``CUSTOM_COMPONENT_SUPPORTED_TYPES`` dict lazily.

    Mirrors the pre-PEP-562 layout: langchain base types plus local
    non-langchain names. ``DataFrame`` and ``Table`` are intentionally held
    as ``None`` sentinels here; ``langflow.field_typing.constants`` rebinds
    them to ``lfx.schema.dataframe`` variants at the langflow layer.
    """
    base = _build_LANGCHAIN_BASE_TYPES()
    merged: dict[str, Any] = {
        **base,
        "NestedDict": NestedDict,
        "Data": Data,
        "JSON": JSON,
        "Text": Text,
        "Object": Object,
        "Callable": Callable,
        "LanguageModel": _get_typevar("LanguageModel"),
        "Retriever": _get_typevar("Retriever"),
    }
    for key in _DEFERRED_SUPPORTED_TYPE_NAMES:
        merged.setdefault(key, None)
    return merged


# -- String literals (unchanged; text must match historical output) ----------

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
    # ``find_spec`` is a metadata query and does NOT import langchain; it only
    # checks whether the distribution is discoverable. Safe to call eagerly.
    DEFAULT_IMPORT_STRING = LANGCHAIN_IMPORT_STRING + DEFAULT_IMPORT_STRING


# -- PEP 562 module-level __getattr__ ----------------------------------------


def __getattr__(name: str) -> Any:
    """Lazy resolution for langchain classes, derived TypeVars, and cached dicts."""
    if name in _LANGCHAIN_SYMBOLS:
        resolved = _resolve_langchain_symbol(name)
        globals()[name] = resolved
        return resolved
    if name in _TYPEVARS:
        return _build_typevar(name)
    if name == "LANGCHAIN_BASE_TYPES":
        value = _build_LANGCHAIN_BASE_TYPES()
        globals()["LANGCHAIN_BASE_TYPES"] = value
        return value
    if name == "CUSTOM_COMPONENT_SUPPORTED_TYPES":
        value = _build_CUSTOM_COMPONENT_SUPPORTED_TYPES()
        globals()["CUSTOM_COMPONENT_SUPPORTED_TYPES"] = value
        return value
    if name in _DEFERRED_SUPPORTED_TYPE_NAMES:
        from lfx.schema.dataframe import DataFrame as _DataFrame
        from lfx.schema.dataframe import Table as _Table

        resolved = {"DataFrame": _DataFrame, "Table": _Table}[name]
        dict_cache = globals().get("CUSTOM_COMPONENT_SUPPORTED_TYPES")
        if dict_cache is not None:
            dict_cache[name] = resolved
        globals()[name] = resolved
        return resolved

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
