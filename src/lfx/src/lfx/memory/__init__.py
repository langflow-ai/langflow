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
        return (
            importlib.util.find_spec("langflow.memory") is not None
            and importlib.util.find_spec("langflow.services.database.models.message.model") is not None
        )
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error checking for langflow.memory: {e}")
    return False


_LANGFLOW_AVAILABLE = _has_langflow_memory()

# Import the appropriate implementations
if _LANGFLOW_AVAILABLE:
    try:
        # Import from full langflow implementation
        from lfx.memory import (
            adelete_messages,
            aget_messages,
            astore_message,
            aupdate_messages,
            delete_message,
            delete_messages,
            get_messages,
            store_message,
        )
    except ImportError:
        # Fall back to stubs if langflow import fails
        from lfx.memory.stubs import (
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
    "adelete_messages",
    "aget_messages",
    "astore_message",
    "aupdate_messages",
    "delete_message",
    "delete_messages",
    "get_messages",
    "store_message",
]
