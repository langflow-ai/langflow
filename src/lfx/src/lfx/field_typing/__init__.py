from typing import Any

# Lazy imports - nothing imported at module level except __all__

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
    "Output",
    "PromptTemplate",
    "RangeSpec",
    "Retriever",
    "Text",
    "TextSplitter",
    "Tool",
    "VectorStore",
]

# Names that come from constants module
_CONSTANTS_NAMES = {
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
    "LanguageModel",
    "NestedDict",
    "Object",
    "PromptTemplate",
    "Retriever",
    "Text",
    "TextSplitter",
    "Tool",
    "VectorStore",
}


def __getattr__(name: str) -> Any:
    """Lazy import for all field typing constants."""
    if name == "Input":
        from lfx.template.field.base import Input

        return Input
    if name == "Output":
        from lfx.template.field.base import Output

        return Output
    if name == "RangeSpec":
        from .range_spec import RangeSpec

        return RangeSpec
    if name in _CONSTANTS_NAMES:
        from . import constants

        return getattr(constants, name)

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
