from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .astradb_assistant_manager import AstraAssistantManager
    from .astradb_chatmemory import AstraDBChatMemory
    from .astradb_cql import AstraDBCQLToolComponent
    from .astradb_graph import AstraDBGraphVectorStoreComponent
    from .astradb_tool import AstraDBToolComponent
    from .astradb_vectorize import AstraVectorizeComponent
    from .astradb_vectorstore import AstraDBVectorStoreComponent
    from .create_assistant import AssistantsCreateAssistant
    from .create_thread import AssistantsCreateThread
    from .dotenv import Dotenv
    from .get_assistant import AssistantsGetAssistantName
    from .getenvvar import GetEnvVar
    from .graph_rag import GraphRAGComponent
    from .list_assistants import AssistantsListAssistants
    from .run import AssistantsRun

_dynamic_imports = {
    "AssistantsCreateAssistant": "create_assistant",
    "AssistantsCreateThread": "create_thread",
    "AssistantsGetAssistantName": "get_assistant",
    "AssistantsListAssistants": "list_assistants",
    "AssistantsRun": "run",
    "AstraAssistantManager": "astradb_assistant_manager",
    "AstraDBCQLToolComponent": "astradb_cql",
    "AstraDBChatMemory": "astradb_chatmemory",
    "AstraDBGraphVectorStoreComponent": "astradb_graph",
    "AstraDBToolComponent": "astradb_tool",
    "AstraDBVectorStoreComponent": "astradb_vectorstore",
    "AstraVectorizeComponent": "astradb_vectorize",
    "Dotenv": "dotenv",
    "GetEnvVar": "getenvvar",
    "GraphRAGComponent": "graph_rag",
}

__all__ = [
    "AssistantsCreateAssistant",
    "AssistantsCreateThread",
    "AssistantsGetAssistantName",
    "AssistantsListAssistants",
    "AssistantsRun",
    "AstraAssistantManager",
    "AstraDBCQLToolComponent",
    "AstraDBChatMemory",
    "AstraDBGraphVectorStoreComponent",
    "AstraDBToolComponent",
    "AstraDBVectorStoreComponent",
    "AstraVectorizeComponent",
    "Dotenv",
    "GetEnvVar",
    "GraphRAGComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import datastax components on attribute access."""
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
