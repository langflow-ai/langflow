from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from .astra_assistant_manager import AstraAssistantManager
    from .astra_db import AstraDBChatMemory
    from .astra_vectorize import AstraVectorizeComponent
    from .astradb_cql import AstraDBCQLToolComponent
    from .astradb_tool import AstraDBToolComponent
    from .cassandra import CassandraChatMemory
    from .create_assistant import AssistantsCreateAssistant
    from .create_thread import AssistantsCreateThread
    from .dotenv import Dotenv
    from .get_assistant import AssistantsGetAssistantName
    from .getenvvar import GetEnvVar
    from .list_assistants import AssistantsListAssistants
    from .run import AssistantsRun

_dynamic_imports = {
    "AssistantsCreateAssistant": "create_assistant",
    "AssistantsCreateThread": "create_thread",
    "AssistantsGetAssistantName": "get_assistant",
    "AssistantsListAssistants": "list_assistants",
    "AssistantsRun": "run",
    "AstraAssistantManager": "astra_assistant_manager",
    "AstraDBCQLToolComponent": "astradb_cql",
    "AstraDBChatMemory": "astra_db",
    "AstraDBToolComponent": "astradb_tool",
    "AstraVectorizeComponent": "astra_vectorize",
    "CassandraChatMemory": "cassandra",
    "Dotenv": "dotenv",
    "GetEnvVar": "getenvvar",
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
    "AstraDBToolComponent",
    "AstraVectorizeComponent",
    "CassandraChatMemory",
    "Dotenv",
    "GetEnvVar",
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
