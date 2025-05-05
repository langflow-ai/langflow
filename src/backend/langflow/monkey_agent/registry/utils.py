"""
Utility functions for the enhanced node registry.

This module provides utility functions for working with the enhanced node registry,
including functions for building and initializing the registry.
"""

import os
import json
from typing import Dict, List, Optional, Any, Union

from .node_registry import EnhancedNodeRegistry, EnhancedNodeType
from .node_types import (
    INPUT_NODES, 
    OUTPUT_NODES, 
    PROMPT_NODES, 
    DATA_NODES,
    get_all_nodes
)
from .compatibility import (
    can_nodes_connect,
    find_compatible_connections,
    generate_connection_handle_json
)

# Default registry file path
DEFAULT_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "registry.json"
)


def build_registry() -> EnhancedNodeRegistry:
    """
    Build the enhanced node registry from all registered nodes.
    
    Returns:
        EnhancedNodeRegistry: The complete node registry
    """
    registry = EnhancedNodeRegistry()
    
    # Register all nodes from each category
    for node_id, node in get_all_nodes().items():
        registry.register_node(node)
    
    return registry


def save_registry(registry: EnhancedNodeRegistry, file_path: str = DEFAULT_REGISTRY_PATH) -> None:
    """
    Save the registry to a JSON file.
    
    Args:
        registry (EnhancedNodeRegistry): The registry to save
        file_path (str, optional): Path to save the registry to. Defaults to DEFAULT_REGISTRY_PATH.
    """
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Save the registry
    registry.save_to_file(file_path)


def load_registry(file_path: str = DEFAULT_REGISTRY_PATH) -> Optional[EnhancedNodeRegistry]:
    """
    Load the registry from a JSON file.
    
    Args:
        file_path (str, optional): Path to load the registry from. Defaults to DEFAULT_REGISTRY_PATH.
        
    Returns:
        Optional[EnhancedNodeRegistry]: The loaded registry, or None if the file doesn't exist
    """
    if not os.path.exists(file_path):
        return None
    
    return EnhancedNodeRegistry.load_from_file(file_path)


def get_or_create_registry(file_path: str = DEFAULT_REGISTRY_PATH) -> EnhancedNodeRegistry:
    """
    Get the registry from a file if it exists, or create and save a new one.
    
    Args:
        file_path (str, optional): Path to the registry file. Defaults to DEFAULT_REGISTRY_PATH.
        
    Returns:
        EnhancedNodeRegistry: The registry
    """
    registry = load_registry(file_path)
    if registry is None:
        registry = build_registry()
        save_registry(registry, file_path)
    
    return registry


def get_node_connection_metadata(node_id: str, registry: EnhancedNodeRegistry) -> Dict[str, Any]:
    """
    Get detailed connection metadata for a node.
    
    Args:
        node_id (str): The ID of the node
        registry (EnhancedNodeRegistry): The node registry
        
    Returns:
        Dict[str, Any]: Dictionary containing connection metadata
    """
    node = registry.get_node(node_id)
    if not node:
        return {}
    
    return {
        "id": node.id,
        "displayName": node.displayName,
        "category": node.category,
        "inputs": {
            name: {
                "types": field.type,
                "displayName": field.displayName,
                "required": field.required,
                "connectionFormat": field.connectionFormat.to_dict()
            }
            for name, field in node.inputs.items()
        },
        "outputs": {
            name: {
                "types": field.type,
                "displayName": field.displayName,
                "connectionFormat": field.connectionFormat.to_dict()
            }
            for name, field in node.outputs.items()
        }
    }


def suggest_connections(source_node_id: str, target_node_id: str, registry: EnhancedNodeRegistry) -> List[Dict[str, Any]]:
    """
    Suggest possible connections between two nodes.
    
    Args:
        source_node_id (str): The ID of the source node
        target_node_id (str): The ID of the target node
        registry (EnhancedNodeRegistry): The node registry
        
    Returns:
        List[Dict[str, Any]]: List of possible connections with detailed metadata
    """
    connections = find_compatible_connections(source_node_id, target_node_id, registry)
    
    if not connections:
        return []
    
    # Enhance connection suggestions with handle formats
    enhanced_connections = []
    for conn in connections:
        source_handle, target_handle = generate_connection_handle_json(
            source_node_id, conn["source_field"],
            target_node_id, conn["target_field"],
            registry
        )
        
        if source_handle and target_handle:
            enhanced_connections.append({
                **conn,
                "source_handle": source_handle,
                "target_handle": target_handle
            })
    
    return enhanced_connections


def generate_workflow_connections(nodes: Dict[str, Dict[str, Any]], registry: EnhancedNodeRegistry) -> List[Dict[str, Any]]:
    """
    Generate all possible connections for a set of nodes in a workflow.
    
    Args:
        nodes (Dict[str, Dict[str, Any]]): Dictionary mapping node IDs to node data
            Each node should have a "type" field indicating the node type
        registry (EnhancedNodeRegistry): The node registry
        
    Returns:
        List[Dict[str, Any]]: List of possible connections between the nodes
    """
    connections = []
    
    # Check each possible pair of nodes
    node_ids = list(nodes.keys())
    for i in range(len(node_ids)):
        for j in range(len(node_ids)):
            if i == j:
                continue
            
            source_id = node_ids[i]
            target_id = node_ids[j]
            
            # Get the node types
            source_type = nodes[source_id].get("type")
            target_type = nodes[target_id].get("type")
            
            if not source_type or not target_type:
                continue
            
            # Find possible connections
            node_connections = suggest_connections(source_type, target_type, registry)
            
            # Add the node IDs to each connection
            for conn in node_connections:
                connections.append({
                    **conn,
                    "source_node_id": source_id,
                    "target_node_id": target_id
                })
    
    return connections


def get_compatible_node_types(node_id: str, as_source: bool = True, registry: EnhancedNodeRegistry = None) -> List[str]:
    """
    Get all node types that are compatible with a given node.
    
    Args:
        node_id (str): The ID of the node
        as_source (bool, optional): Whether to get nodes that can connect to this node (False)
            or nodes that this node can connect to (True). Defaults to True.
        registry (EnhancedNodeRegistry, optional): The node registry. If None, a new registry will be created.
        
    Returns:
        List[str]: List of compatible node type IDs
    """
    if registry is None:
        registry = get_or_create_registry()
    
    node = registry.get_node(node_id)
    if not node:
        return []
    
    compatible_nodes = set()
    
    if as_source:
        # This node as source - find all nodes that can accept its outputs
        for output_field in node.outputs.values():
            for output_type in output_field.type:
                for other_node_id, other_node in registry.nodes.items():
                    if other_node_id == node_id:
                        continue
                    
                    for input_field in other_node.inputs.values():
                        for input_type in input_field.type:
                            from .compatibility import are_types_compatible
                            if are_types_compatible(output_type, input_type):
                                compatible_nodes.add(other_node_id)
    else:
        # This node as target - find all nodes whose outputs can connect to this node
        for input_field in node.inputs.values():
            for input_type in input_field.type:
                for other_node_id, other_node in registry.nodes.items():
                    if other_node_id == node_id:
                        continue
                    
                    for output_field in other_node.outputs.values():
                        for output_type in output_field.type:
                            from .compatibility import are_types_compatible
                            if are_types_compatible(output_type, input_type):
                                compatible_nodes.add(other_node_id)
    
    return list(compatible_nodes)
