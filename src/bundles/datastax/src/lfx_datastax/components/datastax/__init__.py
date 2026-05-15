"""Lazy re-exports for the datastax bundle.

Mirrors the pre-extraction layout of ``lfx.components.datastax`` so saved
flows that referenced the module-level class (e.g.
``lfx.components.datastax.AstraDBVectorStoreComponent``) keep resolving
once the migration table rewrites the import to
``lfx_datastax.components.datastax`` form.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .astradb_chatmemory import AstraDBChatMemory
    from .astradb_cql import AstraDBCQLToolComponent
    from .astradb_data_api import AstraDBDataAPIComponent
    from .astradb_graph import AstraDBGraphVectorStoreComponent
    from .astradb_tool import AstraDBToolComponent
    from .astradb_vectorize import AstraVectorizeComponent
    from .astradb_vectorstore import AstraDBVectorStoreComponent
    from .dotenv import Dotenv
    from .getenvvar import GetEnvVar
    from .graph_rag import GraphRAGComponent
    from .hcd import HCDVectorStoreComponent

_dynamic_imports = {
    "AstraDBCQLToolComponent": "astradb_cql",
    "AstraDBChatMemory": "astradb_chatmemory",
    "AstraDBDataAPIComponent": "astradb_data_api",
    "AstraDBGraphVectorStoreComponent": "astradb_graph",
    "AstraDBToolComponent": "astradb_tool",
    "AstraDBVectorStoreComponent": "astradb_vectorstore",
    "AstraVectorizeComponent": "astradb_vectorize",
    "Dotenv": "dotenv",
    "GetEnvVar": "getenvvar",
    "GraphRAGComponent": "graph_rag",
    "HCDVectorStoreComponent": "hcd",
}

__all__ = [
    "AstraDBCQLToolComponent",
    "AstraDBChatMemory",
    "AstraDBDataAPIComponent",
    "AstraDBGraphVectorStoreComponent",
    "AstraDBToolComponent",
    "AstraDBVectorStoreComponent",
    "AstraVectorizeComponent",
    "Dotenv",
    "GetEnvVar",
    "GraphRAGComponent",
    "HCDVectorStoreComponent",
]


def __getattr__(attr_name: str) -> Any:
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
