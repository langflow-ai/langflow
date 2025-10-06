"""Langflow environment utility functions."""

import importlib.util

from lfx.log.logger import logger

# Tri-state:
# - None: Langflow check not performed yet
# - True: Langflow is available
# - False: Langflow is not available
_is_langflow_available = None


def has_langflow_memory():
    """Check if langflow.memory (with database support) and MessageTable are available."""
    global _is_langflow_available  # noqa: PLW0603

    # TODO: REVISIT: Optimize this implementation later
    # - Consider refactoring to use lazy loading or a more robust service discovery mechanism
    #   that can handle runtime availability changes.

    # Use cached check from previous invocation (if applicable)
    if _is_langflow_available is not None:
        return _is_langflow_available

    # First check (lazy load and cache check)
    try:
        _is_langflow_available = importlib.util.find_spec("langflow") is not None
        return _is_langflow_available  # noqa: TRY300
    except (ImportError, ModuleNotFoundError):
        pass
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error encountered checking for langflow.memory: {e}")

    return False
