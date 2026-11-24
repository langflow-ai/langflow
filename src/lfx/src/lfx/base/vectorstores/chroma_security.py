"""Safe defaults for Langflow-created Chroma collections.

Chroma collection configuration can persist server-side embedding functions.
Some embedding functions accept model-loading kwargs such as trust_remote_code.
Langflow embeds client-side, so built-in collection creation should not register
server-side embedding code.
"""

from __future__ import annotations

from typing import Any


def chroma_langchain_collection_kwargs() -> dict[str, Any]:
    """Return LangChain Chroma kwargs that disable Chroma server-side embedding code."""
    return {"collection_configuration": _chroma_collection_configuration_without_embedding_function()}


def chroma_client_create_collection_kwargs() -> dict[str, Any]:
    """Return chromadb client kwargs that create collections without server-side embedding code."""
    return {
        "configuration": _chroma_collection_configuration_without_embedding_function(),
        "embedding_function": None,
    }


def _chroma_collection_configuration_without_embedding_function() -> dict[str, Any]:
    return {"embedding_function": None}
