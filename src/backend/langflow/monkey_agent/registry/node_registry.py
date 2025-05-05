"""
Enhanced Node Registry for Monkey Agent

This module defines an enhanced registry of node types with detailed information
about their inputs, outputs, and connection formats.
"""

from typing import Dict, List, Optional, Any, TypedDict
from dataclasses import dataclass, field
from enum import Enum
import json

class ConnectionFormatDict(TypedDict):
    """Type definition for connection format details"""
    fieldName: str
    handleFormat: str
    # Additional metadata can be added here


class InputFieldDict(TypedDict):
    """Type definition for input fields"""
    type: List[str]
    displayName: str
    required: bool
    connectionFormat: ConnectionFormatDict


class OutputFieldDict(TypedDict):
    """Type definition for output fields"""
    type: List[str]
    displayName: str
    connectionFormat: ConnectionFormatDict


@dataclass
class ConnectionFormat:
    """Connection format details for node inputs/outputs"""
    fieldName: str
    handleFormat: str
    # Add other connection metadata as needed
    
    def to_dict(self) -> ConnectionFormatDict:
        """Convert to dictionary representation"""
        return {
            "fieldName": self.fieldName,
            "handleFormat": self.handleFormat,
        }
    
    @classmethod
    def from_dict(cls, data: ConnectionFormatDict) -> "ConnectionFormat":
        """Create from dictionary"""
        return cls(
            fieldName=data["fieldName"],
            handleFormat=data["handleFormat"],
        )


@dataclass
class InputField:
    """Detailed information about a node input field"""
    type: List[str]
    displayName: str
    required: bool
    connectionFormat: ConnectionFormat
    
    def to_dict(self) -> InputFieldDict:
        """Convert to dictionary representation"""
        return {
            "type": self.type,
            "displayName": self.displayName,
            "required": self.required,
            "connectionFormat": self.connectionFormat.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: InputFieldDict) -> "InputField":
        """Create from dictionary"""
        return cls(
            type=data["type"],
            displayName=data["displayName"],
            required=data["required"],
            connectionFormat=ConnectionFormat.from_dict(data["connectionFormat"]),
        )


@dataclass
class OutputField:
    """Detailed information about a node output field"""
    type: List[str]
    displayName: str
    connectionFormat: ConnectionFormat
    
    def to_dict(self) -> OutputFieldDict:
        """Convert to dictionary representation"""
        return {
            "type": self.type,
            "displayName": self.displayName,
            "connectionFormat": self.connectionFormat.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: OutputFieldDict) -> "OutputField":
        """Create from dictionary"""
        return cls(
            type=data["type"],
            displayName=data["displayName"],
            connectionFormat=ConnectionFormat.from_dict(data["connectionFormat"]),
        )


@dataclass
class EnhancedNodeType:
    """
    Enhanced node type with detailed information about inputs, outputs,
    and connection formats.
    """
    id: str
    displayName: str
    description: str
    category: str
    inputs: Dict[str, InputField] = field(default_factory=dict)
    outputs: Dict[str, OutputField] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "displayName": self.displayName,
            "description": self.description,
            "category": self.category,
            "inputs": {k: v.to_dict() for k, v in self.inputs.items()},
            "outputs": {k: v.to_dict() for k, v in self.outputs.items()},
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EnhancedNodeType":
        """Create from dictionary"""
        return cls(
            id=data["id"],
            displayName=data["displayName"],
            description=data["description"],
            category=data["category"],
            inputs={
                k: InputField.from_dict(v) 
                for k, v in data.get("inputs", {}).items()
            },
            outputs={
                k: OutputField.from_dict(v) 
                for k, v in data.get("outputs", {}).items()
            },
        )
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "EnhancedNodeType":
        """Create from JSON string"""
        return cls.from_dict(json.loads(json_str))


class EnhancedNodeRegistry:
    """
    Registry for enhanced node types with detailed connection information
    """
    def __init__(self):
        self.nodes: Dict[str, EnhancedNodeType] = {}
    
    def register_node(self, node: EnhancedNodeType) -> None:
        """Register a node in the registry"""
        self.nodes[node.id] = node
    
    def get_node(self, node_id: str) -> Optional[EnhancedNodeType]:
        """Get a node by ID"""
        return self.nodes.get(node_id)
    
    def get_nodes_by_category(self, category: str) -> List[EnhancedNodeType]:
        """Get all nodes in a category"""
        return [node for node in self.nodes.values() if node.category == category]
    
    def to_dict(self) -> Dict[str, dict]:
        """Convert registry to dictionary"""
        return {k: v.to_dict() for k, v in self.nodes.items()}
    
    def to_json(self) -> str:
        """Convert registry to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def save_to_file(self, file_path: str) -> None:
        """Save registry to a JSON file"""
        with open(file_path, "w") as f:
            f.write(self.to_json())
    
    @classmethod
    def from_dict(cls, data: Dict[str, dict]) -> "EnhancedNodeRegistry":
        """Create registry from dictionary"""
        registry = cls()
        for node_id, node_data in data.items():
            registry.register_node(EnhancedNodeType.from_dict(node_data))
        return registry
    
    @classmethod
    def from_json(cls, json_str: str) -> "EnhancedNodeRegistry":
        """Create registry from JSON string"""
        return cls.from_dict(json.loads(json_str))
    
    @classmethod
    def load_from_file(cls, file_path: str) -> "EnhancedNodeRegistry":
        """Load registry from a JSON file"""
        with open(file_path, "r") as f:
            return cls.from_json(f.read())


# Helper functions for creating common node types
def create_input_node(
    node_id: str,
    display_name: str,
    description: str,
    output_field_name: str,
    output_types: List[str],
    output_display_name: str,
) -> EnhancedNodeType:
    """
    Create a typical input node with a single output
    """
    output_format = ConnectionFormat(
        fieldName=output_field_name,
        handleFormat=f"{{\"dataType\": \"{node_id}\", \"id\": \"NODE_ID\", \"name\": \"{output_field_name}\", \"output_types\": {json.dumps(output_types)}}}"
    )
    
    output_field = OutputField(
        type=output_types,
        displayName=output_display_name,
        connectionFormat=output_format
    )
    
    return EnhancedNodeType(
        id=node_id,
        displayName=display_name,
        description=description,
        category="Inputs",
        outputs={output_field_name: output_field}
    )


def create_model_node(
    node_id: str,
    display_name: str,
    description: str,
    input_field_name: str,
    input_types: List[str],
    input_display_name: str,
    output_field_name: str,
    output_types: List[str],
    output_display_name: str,
) -> EnhancedNodeType:
    """
    Create a typical model node with a standard input and output
    """
    input_format = ConnectionFormat(
        fieldName=input_field_name,
        handleFormat=f"{{\"fieldName\": \"{input_field_name}\", \"id\": \"NODE_ID\", \"inputTypes\": {json.dumps(input_types)}, \"type\": \"str\"}}"
    )
    
    input_field = InputField(
        type=input_types,
        displayName=input_display_name,
        required=True,
        connectionFormat=input_format
    )
    
    output_format = ConnectionFormat(
        fieldName=output_field_name,
        handleFormat=f"{{\"dataType\": \"{node_id}\", \"id\": \"NODE_ID\", \"name\": \"{output_field_name}\", \"output_types\": {json.dumps(output_types)}}}"
    )
    
    output_field = OutputField(
        type=output_types,
        displayName=output_display_name,
        connectionFormat=output_format
    )
    
    return EnhancedNodeType(
        id=node_id,
        displayName=display_name,
        description=description,
        category="Models",
        inputs={input_field_name: input_field},
        outputs={output_field_name: output_field}
    )
