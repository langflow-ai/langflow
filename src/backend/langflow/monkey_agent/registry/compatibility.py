"""
Node compatibility definitions for the enhanced node registry.

This module defines which node output types can connect to which input types.
"""

from typing import Dict, List, Set

# Type compatibility matrix
# Maps from output type to compatible input types
TYPE_COMPATIBILITY: Dict[str, List[str]] = {
    # Text output types
    "str": ["str", "Message", "Text", "any"],
    "Message": ["str", "Message", "Text", "any"],
    "Text": ["str", "Message", "Text", "any"],
    
    # Document types
    "Document": ["Document", "any"],
    "List[Document]": ["Document", "List[Document]", "any"],
    
    # Chat related types
    "ChatHistory": ["ChatHistory", "any"],
    "ChatPromptValue": ["ChatPromptValue", "PromptValue", "any"],
    
    # Prompt related types
    "PromptValue": ["PromptValue", "str", "any"],
    
    # Data types
    "Embedding": ["Embedding", "any"],
    "VectorStore": ["VectorStore", "any"],
    
    # File types
    "File": ["File", "str", "any"],
    "Blob": ["Blob", "File", "any"],
    
    # API related types
    "APIResponse": ["APIResponse", "JSON", "str", "any"],
    "JSON": ["JSON", "Dict", "any"],
    "Dict": ["Dict", "JSON", "any"],
    
    # Agent types
    "Tool": ["Tool", "any"],
    "Chain": ["Chain", "any"],
    "Agent": ["Agent", "any"],
    
    # Generic types
    "List": ["List", "any"],
    "any": ["any"]  # "any" can only connect to "any"
}

def are_types_compatible(source_type: str, target_type: str) -> bool:
    """
    Check if a source output type is compatible with a target input type.
    
    Args:
        source_type (str): The output type of the source node
        target_type (str): The input type of the target node
        
    Returns:
        bool: True if the types are compatible, False otherwise
    """
    # If either type is not in the compatibility matrix, they're not compatible
    if source_type not in TYPE_COMPATIBILITY:
        return False
    
    # Check if target_type is in the list of compatible types for source_type
    return target_type in TYPE_COMPATIBILITY[source_type]

def get_compatible_types(source_type: str) -> List[str]:
    """
    Get all types compatible with a given source type.
    
    Args:
        source_type (str): The output type to check compatibility for
        
    Returns:
        List[str]: List of compatible input types
    """
    return TYPE_COMPATIBILITY.get(source_type, [])

def can_nodes_connect(source_node_id: str, source_output: str, 
                      target_node_id: str, target_input: str,
                      registry) -> bool:
    """
    Check if two nodes can be connected based on their types.
    
    Args:
        source_node_id (str): The ID of the source node
        source_output (str): The output field name of the source node
        target_node_id (str): The ID of the target node
        target_input (str): The input field name of the target node
        registry: The node registry containing the node definitions
        
    Returns:
        bool: True if the nodes can be connected, False otherwise
    """
    # Get the node definitions
    source_node = registry.get_node(source_node_id)
    target_node = registry.get_node(target_node_id)
    
    if not source_node or not target_node:
        return False
    
    # Get the output and input fields
    source_output_field = source_node.outputs.get(source_output)
    target_input_field = target_node.inputs.get(target_input)
    
    if not source_output_field or not target_input_field:
        return False
    
    # Check type compatibility
    for source_type in source_output_field.type:
        for target_type in target_input_field.type:
            if are_types_compatible(source_type, target_type):
                return True
    
    return False

def find_compatible_connections(source_node_id: str, target_node_id: str, registry):
    """
    Find all possible connections between two nodes.
    
    Args:
        source_node_id (str): The ID of the source node
        target_node_id (str): The ID of the target node
        registry: The node registry containing the node definitions
        
    Returns:
        List[dict]: List of possible connections, each containing:
            - source_field: The output field name of the source node
            - target_field: The input field name of the target node
            - source_type: The output type of the source field
            - target_type: The input type of the target field
    """
    # Get the node definitions
    source_node = registry.get_node(source_node_id)
    target_node = registry.get_node(target_node_id)
    
    if not source_node or not target_node:
        return []
    
    connections = []
    
    # Check each output field of the source node against each input field of the target node
    for source_field_name, source_field in source_node.outputs.items():
        for target_field_name, target_field in target_node.inputs.items():
            # Check type compatibility
            for source_type in source_field.type:
                for target_type in target_field.type:
                    if are_types_compatible(source_type, target_type):
                        connections.append({
                            "source_field": source_field_name,
                            "target_field": target_field_name,
                            "source_type": source_type,
                            "target_type": target_type
                        })
                        # Break once we find a compatible type
                        break
                else:
                    # Continue if the inner loop wasn't broken
                    continue
                # Break if the inner loop was broken
                break
    
    return connections

def generate_connection_handle_json(source_node_id: str, source_field: str, target_node_id: str, target_field: str, registry):
    """
    Generate the JSON handle format for a connection between two nodes.
    
    Args:
        source_node_id (str): The ID of the source node
        source_field (str): The output field name of the source node
        target_node_id (str): The ID of the target node
        target_field (str): The input field name of the target node
        registry: The node registry containing the node definitions
        
    Returns:
        tuple: A tuple containing (source_handle_json, target_handle_json) or (None, None) if not compatible
    """
    # Get the node definitions
    source_node = registry.get_node(source_node_id)
    target_node = registry.get_node(target_node_id)
    
    if not source_node or not target_node:
        return None, None
    
    # Get the output and input fields
    source_output_field = source_node.outputs.get(source_field)
    target_input_field = target_node.inputs.get(target_field)
    
    if not source_output_field or not target_input_field:
        return None, None
    
    # Replace NODE_ID with the actual node IDs
    source_handle_format = source_output_field.connectionFormat.handleFormat.replace("NODE_ID", source_node_id)
    target_handle_format = target_input_field.connectionFormat.handleFormat.replace("NODE_ID", target_node_id)
    
    return source_handle_format, target_handle_format
