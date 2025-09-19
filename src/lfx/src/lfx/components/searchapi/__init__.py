from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
<<<<<<<< HEAD:src/backend/base/langflow/components/knowledge_bases/__init__.py
    from langflow.components.knowledge_bases.ingestion import KnowledgeIngestionComponent
    from langflow.components.knowledge_bases.retrieval import KnowledgeRetrievalComponent

_dynamic_imports = {
    "KnowledgeIngestionComponent": "ingestion",
    "KnowledgeRetrievalComponent": "retrieval",
}

__all__ = ["KnowledgeIngestionComponent", "KnowledgeRetrievalComponent"]


def __getattr__(attr_name: str) -> Any:
    """Lazily import input/output components on attribute access."""
========
    from lfx.components.searchapi.search import SearchComponent

_dynamic_imports = {
    "SearchComponent": "search",
}

__all__ = [
    "SearchComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import searchapi components on attribute access."""
>>>>>>>> main:src/lfx/src/lfx/components/searchapi/__init__.py
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
