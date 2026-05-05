"""Pure-string registry of public field-typing names.

This module is the **cold-path** half of the split:

- It only carries names (strings) and resolution metadata (module paths).
- It imports nothing from langchain, pandas, or any other heavy dependency.
- Importing it does not transitively pull in ``lfx.field_typing.constants``.

Consumers that only need to *check whether a name appears in source code*
(e.g. ``lfx.custom.validate.find_names_in_code``) should import from here so
that the warm-path module ``lfx.field_typing.constants`` is not loaded —
which in turn avoids triggering its lazy-resolution machinery.

Consumers that need the actual class object (annotations, isinstance checks,
exec'd component code) should keep importing from ``lfx.field_typing``.
"""

from __future__ import annotations

# Resolution table: public symbol name -> (submodule_path, attribute_name).
# Used by ``lfx.field_typing.constants._resolve_langchain_symbol`` for the
# real import. Lives here so the table is reachable without paying the cost
# of importing the warm-path module.
LANGCHAIN_SYMBOLS: dict[str, tuple[str, str]] = {
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


# TypeVar specs: name -> (kind, value). ``kind`` is "constraints" (value is a
# tuple of langchain symbol names) or "bound" (value is a single name).
TYPEVAR_SPECS: dict[str, tuple[str, tuple[str, ...] | str]] = {
    "LanguageModel": ("constraints", ("BaseLanguageModel", "BaseLLM", "BaseChatModel")),
    "ToolEnabledLanguageModel": ("constraints", ("BaseLanguageModel", "BaseLLM", "BaseChatModel")),
    "Memory": ("bound", "BaseChatMessageHistory"),
    "Retriever": ("constraints", ("BaseRetriever", "VectorStoreRetriever")),
    "OutputParser": ("constraints", ("BaseOutputParser", "BaseLLMOutputParser")),
}


# Ordered keys of the ``LANGCHAIN_BASE_TYPES`` dict. The "Memory" entry is
# materialized via the TypeVar (see ``TYPEVAR_SPECS``); all others resolve
# to langchain classes via ``LANGCHAIN_SYMBOLS``.
LANGCHAIN_BASE_TYPE_KEYS: tuple[str, ...] = (
    "Chain",
    "AgentExecutor",
    "BaseTool",
    "Tool",
    "BaseLLM",
    "BaseLanguageModel",
    "PromptTemplate",
    "ChatPromptTemplate",
    "BasePromptTemplate",
    "BaseLoader",
    "Document",
    "TextSplitter",
    "VectorStore",
    "Embeddings",
    "BaseRetriever",
    "BaseOutputParser",
    "BaseMemory",
    "BaseChatMemory",
    "BaseChatModel",
    "Memory",
    "BaseDocumentCompressor",
)


# Public string-keyed view of ``CUSTOM_COMPONENT_SUPPORTED_TYPES``. This is
# the set ``lfx.custom.validate.find_names_in_code`` consults to decide which
# names appear in user code; only the names matter, never the class objects.
SUPPORTED_TYPE_NAMES: frozenset[str] = frozenset(
    {
        *LANGCHAIN_BASE_TYPE_KEYS,
        "NestedDict",
        "Data",
        "JSON",
        "Text",
        "Object",
        "Callable",
        "LanguageModel",
        "Retriever",
        "DataFrame",
        "Table",
    }
)
