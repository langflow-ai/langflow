"""
Node type definitions for the enhanced node registry.

This module contains definitions for specific node types organized by category.
"""

from . import input_nodes
from . import output_nodes
from . import prompt_nodes
from . import data_nodes

# Re-export the node registries for easy access
from .input_nodes import INPUT_NODES
from .output_nodes import OUTPUT_NODES
from .prompt_nodes import PROMPT_NODES
from .data_nodes import DATA_NODES

# Combine all nodes into a single registry
def get_all_nodes():
    """
    Get all registered nodes from all categories.
    
    Returns:
        dict: A dictionary mapping node IDs to node definitions.
    """
    all_nodes = {}
    all_nodes.update(INPUT_NODES)
    all_nodes.update(OUTPUT_NODES)
    all_nodes.update(PROMPT_NODES)
    all_nodes.update(DATA_NODES)
    return all_nodes
