"""Memory management for lfx with dynamic loading.

This module automatically chooses between full langflow implementations
(when available) and lfx stub implementations (when standalone).
"""

import importlib.util

from loguru import logger


def _has_langflow_memory():
    """Check if langflow.memory with database support is available."""
    try:
        # Check if langflow.memory and MessageTable are available
        return importlib.util.find_spec("langflow") is not None
    except (ImportError, ModuleNotFoundError):
        pass
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error checking for langflow.memory: {e}")
    return False


#### TODO: This _LANGFLOW_AVAILABLE implementation should be changed later ####
# Consider refactoring to lazy loading or a more robust service discovery mechanism
# that can handle runtime availability changes.
_LANGFLOW_AVAILABLE = _has_langflow_memory()

# Import the appropriate implementations
if _LANGFLOW_AVAILABLE:
    try:
        # Import from full langflow implementation
        from langflow.memory import (
            aadd_messages,
            aadd_messagetables,
            add_messages,
            adelete_messages,
            aget_messages,
            astore_message,
            aupdate_messages,
            delete_message,
            delete_messages,
            get_messages,
            store_message,
        )
    except (ImportError, ModuleNotFoundError):
        # Fall back to stubs if langflow import fails
        from lfx.memory.stubs import (
            aadd_messages,
            aadd_messagetables,
            add_messages,
            adelete_messages,
            aget_messages,
            astore_message,
            aupdate_messages,
            delete_message,
            delete_messages,
            get_messages,
            store_message,
        )
else:
    # Use lfx stub implementations
    from lfx.memory.stubs import (
        aadd_messages,
        aadd_messagetables,
        add_messages,
        adelete_messages,
        aget_messages,
        astore_message,
        aupdate_messages,
        delete_message,
        delete_messages,
        get_messages,
        store_message,
    )

# Export the available functions and classes
__all__ = [
    "aadd_messages",
    "aadd_messagetables",
    "add_messages",
    "adelete_messages",
    "aget_messages",
    "astore_message",
    "aupdate_messages",
    "delete_message",
    "delete_messages",
    "get_messages",
    "store_message",
]
