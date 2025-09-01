from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.knowledge_bases.ingestion import KnowledgeIngestionComponent
    from lfx.components.knowledge_bases.retrieval import KnowledgeRetrievalComponent

_dynamic_imports = {
    "KnowledgeIngestionComponent": "ingestion",
    "KnowledgeRetrievalComponent": "retrieval",
    # Aliases for the shorter names expected by data module
    "KBIngestionComponent": "ingestion",
    "KBRetrievalComponent": "retrieval",
}

__all__ = [
    "KBIngestionComponent",
    "KBRetrievalComponent",
    "KnowledgeIngestionComponent",
    "KnowledgeRetrievalComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import knowledge base components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        module_name = _dynamic_imports[attr_name]
        class_name = "KnowledgeIngestionComponent" if "Ingestion" in attr_name else "KnowledgeRetrievalComponent"
        result = import_mod(class_name, module_name, __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    else:
        globals()[attr_name] = result
        return result


def __dir__() -> list[str]:
    return list(__all__)
