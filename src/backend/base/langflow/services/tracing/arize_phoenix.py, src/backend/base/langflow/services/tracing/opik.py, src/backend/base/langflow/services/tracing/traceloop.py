# File: src/backend/base/langflow/services/tracing/arize_phoenix.py
"""Utilities for converting values to Arize Phoenix-compatible types."""

import types
from typing import Any


def _convert_to_arize_phoenix_type(value: Any) -> Any:
    """Convert Python values into types supported by Arize Phoenix.
    Generators and None are stringified.
    """
    if isinstance(value, types.GeneratorType | type(None)):
        value = str(value)
    elif isinstance(value, (str, bool, int, float)):
        return value
    else:
        value = str(value)
    return value


# File: src/backend/base/langflow/services/tracing/opik.py
"""Utilities for converting values to Opik-compatible types."""
from typing import Any


def _convert_to_opik_type(value: Any) -> Any:
    """Convert Python values into types supported by Opik.
    Generators and None are stringified.
    """
    if isinstance(value, types.GeneratorType | type(None)):
        value = str(value)
    elif isinstance(value, (str, bool, int, float)):
        return value
    else:
        value = str(value)
    return value


# File: src/backend/base/langflow/services/tracing/traceloop.py
"""Utilities for converting values to TraceLoop-compatible types."""
from typing import Any


def _convert_to_traceloop_type(value: Any) -> Any:
    """Convert Python values into types supported by TraceLoop.
    Generators and None are stringified.
    """
    if isinstance(value, types.GeneratorType | type(None)):
        value = str(value)
    elif isinstance(value, (str, bool, int, float)):
        return value
    else:
        value = str(value)
    return value
