"""Static metadata for field-typing resolution.

Holds the tables ``lfx.field_typing.constants`` reads to lazy-resolve
langchain classes and TypeVars: module paths, TypeVar specs, and the
ordered keys of ``LANGCHAIN_BASE_TYPES``. Imports nothing from langchain,
pandas, or any other heavy dependency, so a future cold-path consumer
that only needs names (not class objects) can read from here without
triggering ``constants`` lazy-resolution.

Consumers that need the actual class object (annotations, isinstance
checks, exec'd component code) should keep importing from
``lfx.field_typing``.
"""

from __future__ import annotations

# Resolution table: public symbol name -> (submodule_path, attribute_name).
# Read by ``lfx.field_typing.constants._resolve_langchain_symbol``.
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
