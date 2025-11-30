"""Functions module - Wrap Python functions as Langflow components."""

from lfx.base.functions.function_component import (
    FunctionComponent,
    InputConfig,
    component,
    from_function,
)

__all__ = [
    "FunctionComponent",
    "InputConfig",
    "component",
    "from_function",
]
