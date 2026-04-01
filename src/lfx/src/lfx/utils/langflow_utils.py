"""Langflow environment utility functions."""

import importlib.util

from lfx.log.logger import logger


class _LangflowModule:
    # Static variable
    # Tri-state:
    # - None: Langflow check not performed yet
    # - True: Langflow is available
    # - False: Langflow is not available
    _available = None

    @classmethod
    def is_available(cls):
        return cls._available

    @classmethod
    def set_available(cls, value):
        cls._available = value


def has_langflow_memory():
    """Check if langflow.memory (with database support) and MessageTable are available."""
    # TODO: REVISIT: Optimize this implementation later
    # - Consider refactoring to use lazy loading or a more robust service discovery mechanism
    #   that can handle runtime availability changes.

    # Use cached check from previous invocation (if applicable)

    is_langflow_available = _LangflowModule.is_available()

    if is_langflow_available is not None:
        return is_langflow_available

    # First check (lazy load and cache check)

    module_spec = None

    try:
        module_spec = importlib.util.find_spec("langflow")
    except ImportError:
        pass
    except (TypeError, ValueError) as e:
        logger.error(f"Error encountered checking for langflow.memory: {e}")

    is_langflow_available = module_spec is not None
    _LangflowModule.set_available(is_langflow_available)

    return is_langflow_available
