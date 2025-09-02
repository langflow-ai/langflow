"""Component module for langflow - imports from lfx.

This maintains backward compatibility while using the lfx implementation.
"""

from lfx.custom.custom_component.component import (
    BACKWARDS_COMPATIBLE_ATTRIBUTES,
    CONFIG_ATTRIBUTES,
    Component,
    PlaceholderGraph,
    get_component_toolkit,
)

# For backwards compatibility - some code might still use the private function
_get_component_toolkit = get_component_toolkit

__all__ = [
    "BACKWARDS_COMPATIBLE_ATTRIBUTES",
    "CONFIG_ATTRIBUTES",
    "Component",
    "PlaceholderGraph",
    "_get_component_toolkit",
    "get_component_toolkit",
]
