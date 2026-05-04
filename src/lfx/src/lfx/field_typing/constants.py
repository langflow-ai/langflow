"""Constants for field typing used throughout lfx package.

This module uses PEP 562 module ``__getattr__`` to lazily resolve langchain
classes and type-var-derived symbols. Loading this module used to pull
``langchain_classic`` and ~130 ``langchain_core`` submodules even when the
caller only needed a type name for an annotation. Now these imports happen
on first attribute access, with private stub-class fallback on
``ImportError`` or ``OSError`` (the latter covers Windows c10.dll failures
when torch native deps are absent; see
``tests/unit/field_typing/test_lazy_imports.py``).

The stub classes are deliberately given *private* names (``_AgentExecutorStub``,
etc.) so that ``globals()[public_name]`` is undefined until ``__getattr__``
populates it — which is what makes the lazy resolution actually fire.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
from collections.abc import Callable
from typing import Any, TypeAlias, TypeVar

# ``Text`` is re-exported as a public name because downstream modules (notably
# ``lfx.template.field.base``) import it as ``from lfx.field_typing import Text``.
# In Python 3.x ``typing.Text`` is ``str``; the alias keeps existing callers
# working without changes.
Text = str

from lfx.schema.data import JSON, Data  # noqa: E402

# -- Stub classes (private; used on ImportError/OSError fallback) ------------
# These stubs are a compatibility escape hatch for symbolic/type-oriented paths
# that only need "some class object" in scope, such as annotation support,
# dynamic class compilation, and validation helpers. They are NOT runtime-
# compatible replacements for the real LangChain classes: if downstream code
# relies on real methods, constructors, or inheritance checks, it may still
# fail later when it touches the stub. That tradeoff is intentional here:
# ``lfx.field_typing.constants`` prefers to preserve cold-start behavior and
# lightweight validation paths, while logging a warning when it has to degrade.
#
# Names are intentionally underscore-prefixed so they do not shadow the public
# langchain symbols in module globals. The PEP 562 ``__getattr__`` below only
# fires when the public name is absent from ``globals()``. If these stubs used
# public names like ``Tool`` or ``BaseTool``, Python would resolve them
# immediately and never attempt the lazy import of the real symbol.


class _AgentExecutorStub:  # pragma: no cover - fallback stub
    pass


class _ChainStub:  # pragma: no cover - fallback stub
    pass


class _BaseChatMemoryStub:  # pragma: no cover - fallback stub
    pass


class _BaseChatMessageHistoryStub:  # pragma: no cover - fallback stub
    pass


class _BaseLoaderStub:  # pragma: no cover - fallback stub
    pass


class _DocumentStub:  # pragma: no cover - fallback stub
    pass


class _BaseDocumentCompressorStub:  # pragma: no cover - fallback stub
    pass


class _EmbeddingsStub:  # pragma: no cover - fallback stub
    pass


class _BaseLanguageModelStub:  # pragma: no cover - fallback stub
    pass


class _BaseLLMStub:  # pragma: no cover - fallback stub
    pass


class _BaseChatModelStub:  # pragma: no cover - fallback stub
    pass


class _BaseMemoryStub:  # pragma: no cover - fallback stub
    pass


class _BaseLLMOutputParserStub:  # pragma: no cover - fallback stub
    pass


class _BaseOutputParserStub:  # pragma: no cover - fallback stub
    pass


class _BasePromptTemplateStub:  # pragma: no cover - fallback stub
    pass


class _ChatPromptTemplateStub:  # pragma: no cover - fallback stub
    pass


class _PromptTemplateStub:  # pragma: no cover - fallback stub
    pass


class _BaseRetrieverStub:  # pragma: no cover - fallback stub
    pass


class _BaseToolStub:  # pragma: no cover - fallback stub
    pass


class _ToolStub:  # pragma: no cover - fallback stub
    pass


class _VectorStoreStub:  # pragma: no cover - fallback stub
    pass


class _VectorStoreRetrieverStub:  # pragma: no cover - fallback stub
    pass


class _TextSplitterStub:  # pragma: no cover - fallback stub
    pass


# -- Local non-langchain types (always eager) --------------------------------


class Object:
    """Generic object type for custom components."""


class Code:
    """Code type for custom components."""


NestedDict: TypeAlias = dict[str, str | dict]


# Maps public langchain symbol name -> private stub class. Used by
# ``_resolve_langchain_symbol`` when the real import fails.
_STUBS: dict[str, type] = {
    "AgentExecutor": _AgentExecutorStub,
    "Chain": _ChainStub,
    "BaseChatMemory": _BaseChatMemoryStub,
    "BaseChatMessageHistory": _BaseChatMessageHistoryStub,
    "BaseLoader": _BaseLoaderStub,
    "Document": _DocumentStub,
    "BaseDocumentCompressor": _BaseDocumentCompressorStub,
    "Embeddings": _EmbeddingsStub,
    "BaseLanguageModel": _BaseLanguageModelStub,
    "BaseLLM": _BaseLLMStub,
    "BaseChatModel": _BaseChatModelStub,
    "BaseMemory": _BaseMemoryStub,
    "BaseLLMOutputParser": _BaseLLMOutputParserStub,
    "BaseOutputParser": _BaseOutputParserStub,
    "BasePromptTemplate": _BasePromptTemplateStub,
    "ChatPromptTemplate": _ChatPromptTemplateStub,
    "PromptTemplate": _PromptTemplateStub,
    "BaseRetriever": _BaseRetrieverStub,
    "BaseTool": _BaseToolStub,
    "Tool": _ToolStub,
    "VectorStore": _VectorStoreStub,
    "VectorStoreRetriever": _VectorStoreRetrieverStub,
    "TextSplitter": _TextSplitterStub,
}
_STUB_TYPES: tuple[type, ...] = tuple(_STUBS.values())

# Tracks symbols whose import has already failed once, so the warning fires
# at most once per process per symbol.
_STUB_WARNED: set[str] = set()


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


def _contains_stub(value: Any, *, _seen: set[int] | None = None) -> bool:
    """Return True when ``value`` is or contains any stub-backed fallback."""
    if _seen is None:
        _seen = set()
    obj_id = id(value)
    if obj_id in _seen:
        return False
    _seen.add(obj_id)

    if any(value is stub for stub in _STUB_TYPES):
        return True
    if isinstance(value, dict):
        return any(_contains_stub(item, _seen=_seen) for item in value.values())
    if isinstance(value, tuple | list | set | frozenset):
        return any(_contains_stub(item, _seen=_seen) for item in value)

    constraints = getattr(value, "__constraints__", ())
    if constraints and any(_contains_stub(item, _seen=_seen) for item in constraints):
        return True

    bound = getattr(value, "__bound__", None)
    return bound is not None and _contains_stub(bound, _seen=_seen)


def _cache_if_concrete(name: str, value: Any) -> Any:
    """Cache only fully-resolved values; degraded stub-backed values stay transient.

    This matters for transient import failures and for prefork servers such as
    Gunicorn with ``preload_app=True``: if the parent process cached a stub-
    backed symbol, TypeVar, or dict, every worker would inherit that degraded
    state after fork even when the real import would succeed in the child.
    """
    if _contains_stub(value):
        globals().pop(name, None)
        return value

    globals()[name] = value
    return value


def _clear_degraded_caches_after_fork() -> None:
    """Drop degraded caches inherited from a prefork parent process."""
    _STUB_WARNED.clear()
    for name in (
        *tuple(_LANGCHAIN_SYMBOLS),
        *_TYPEVARS,
        "LANGCHAIN_BASE_TYPES",
        "CUSTOM_COMPONENT_SUPPORTED_TYPES",
    ):
        cached = globals().get(name)
        if cached is not None and _contains_stub(cached):
            globals().pop(name, None)


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_clear_degraded_caches_after_fork)


def _resolve_langchain_symbol(name: str) -> Any:
    """Return the real langchain class if importable, else the private stub."""
    module_path, attr = _LANGCHAIN_SYMBOLS[name]
    try:
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    except (ImportError, OSError) as exc:
        # Import failed (langchain not installed, or a transitive native dep
        # like torch's c10.dll failed with ``OSError: [WinError 126]`` on
        # Windows without the MSVC redistributable). Fall back to the stub
        # so that simple type annotations still resolve, but warn once per
        # symbol so a broken install is not invisible to support engineers.
        if name not in _STUB_WARNED:
            _STUB_WARNED.add(name)
            from lfx.log.logger import logger

            logger.warning(
                f"lfx.field_typing.constants: {module_path}.{attr} unavailable "
                f"({type(exc).__name__}: {exc}); falling back to stub. Downstream "
                "isinstance/issubclass checks against this name will not match real "
                "langchain objects."
            )
        return _STUBS[name]


def _get_langchain(name: str) -> Any:
    """Return the cached or freshly-resolved langchain class for ``name``."""
    cached = globals().get(name)
    if cached is not None and not _contains_stub(cached):
        return cached
    # Either uncached, or previously cached as the stub. Re-attempt the
    # real import: a transient earlier failure should not poison the
    # process for life.
    resolved = _resolve_langchain_symbol(name)
    return _cache_if_concrete(name, resolved)


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
    return _cache_if_concrete(name, built)


def _get_typevar(name: str) -> TypeVar:
    """Return the cached TypeVar for ``name`` or build it now."""
    cached = globals().get(name)
    if cached is not None and not _contains_stub(cached):
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
    non-langchain names. ``DataFrame`` and ``Table`` start as ``None``
    placeholders so that consumers on the cold-start path (notably
    ``lfx.custom.validate`` which imports this dict for ``.keys()``) do
    not pay the cost of importing ``lfx.schema.dataframe`` (and pandas).
    The placeholders are patched in-place when a caller actually reads
    ``constants.DataFrame`` / ``constants.Table`` via ``__getattr__``.
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
        # Reuse the already-resolved class if a prior attribute access has
        # populated globals; otherwise leave a None placeholder that gets
        # patched by ``__getattr__`` on first access.
        merged[key] = globals().get(key)
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
        return _get_langchain(name)
    if name in _TYPEVARS:
        return _build_typevar(name)
    if name == "LANGCHAIN_BASE_TYPES":
        value = _build_LANGCHAIN_BASE_TYPES()
        return _cache_if_concrete("LANGCHAIN_BASE_TYPES", value)
    if name == "CUSTOM_COMPONENT_SUPPORTED_TYPES":
        value = _build_CUSTOM_COMPONENT_SUPPORTED_TYPES()
        return _cache_if_concrete("CUSTOM_COMPONENT_SUPPORTED_TYPES", value)
    if name in _DEFERRED_SUPPORTED_TYPE_NAMES:
        from lfx.schema.dataframe import DataFrame as _DataFrame
        from lfx.schema.dataframe import Table as _Table

        resolved = {"DataFrame": _DataFrame, "Table": _Table}[name]
        # Patch the cached dict so by-key access matches attribute access.
        dict_cache = globals().get("CUSTOM_COMPONENT_SUPPORTED_TYPES")
        if isinstance(dict_cache, dict):
            dict_cache[name] = resolved
        globals()[name] = resolved
        return resolved

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
