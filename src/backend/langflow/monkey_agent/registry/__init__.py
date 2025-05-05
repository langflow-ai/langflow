"""
Monkey Agent Enhanced Node Registry

This package provides an enhanced registry of node types with detailed information
about their inputs, outputs, and connection formats.
"""

from .node_registry import (
    EnhancedNodeRegistry,
    EnhancedNodeType,
    InputField,
    OutputField,
    ConnectionFormat,
    create_input_node,
    create_model_node,
)
