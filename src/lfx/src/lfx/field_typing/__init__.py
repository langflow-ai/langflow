"""Field typing module for lfx package."""

from typing import Text

try:
    from langchain_core.tools import Tool
except ImportError:

    class Tool:
        pass


from lfx.field_typing.constants import (
    AgentExecutor,
    BaseChatMemory,
    BaseDocumentCompressor,
    Embeddings,
    LanguageModel,
    VectorStore,
)
from lfx.field_typing.range_spec import RangeSpec
from lfx.schema.message import Message

__all__ = [
    "AgentExecutor",
    "BaseChatMemory",
    "BaseDocumentCompressor",
    "Embeddings",
    "LanguageModel",
    "Message",
    "RangeSpec",
    "Text",
    "Tool",
    "VectorStore",
]
