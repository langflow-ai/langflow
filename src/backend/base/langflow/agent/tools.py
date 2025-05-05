"""
Tools and functions for the Langflow AI Agent.
This module defines the available tools that the agent can use
to manipulate the Langflow canvas.
"""

from typing import Dict, List, Any, Optional, Callable
import uuid
from pydantic import BaseModel, Field

class NodePosition(BaseModel):
    """Position of a node on the canvas."""
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")

class AddNodeInput(BaseModel):
    """Input for adding a node to the canvas."""
    node_type: str = Field(..., description="Type of node to add (e.g., 'ChatOpenAI', 'PromptTemplate')")
    position: Optional[NodePosition] = Field(None, description="Position on canvas (if not provided, will use default)")
    id: Optional[str] = Field(None, description="ID for the node (if not provided, will be generated)")
    
class EditNodeInput(BaseModel):
    """Input for editing a node on the canvas."""
    node_id: str = Field(..., description="ID of the node to edit")
    parameters: Dict[str, Any] = Field(..., description="Parameters to update on the node")

class ConnectNodesInput(BaseModel):
    """Input for connecting two nodes together."""
    source_id: str = Field(..., description="ID of the source node")
    target_id: str = Field(..., description="ID of the target node")
    source_handle: Optional[str] = Field(None, description="Source handle (if specific)")
    target_handle: Optional[str] = Field(None, description="Target handle (if specific)")

class CreateWorkflowInput(BaseModel):
    """Input for creating a new workflow."""
    name: str = Field(..., description="Name for the new workflow")

# Define tool functions
def add_node_tool(input_data: AddNodeInput) -> Dict[str, Any]:
    """
    Add a new node to the canvas.
    
    Args:
        input_data: Specification for the node to add
        
    Returns:
        Dict with the created node information
    """
    # Generate a unique ID if not provided
    node_id = input_data.id or f"{input_data.node_type}_{str(uuid.uuid4())[:8]}"
    
    # Create the node data structure
    node_data = {
        "id": node_id,
        "type": "genericNode",
        "position": input_data.position.dict() if input_data.position else None,
        "data": {
            "type": input_data.node_type,
            "node": {
                "template": {}
            }
        }
    }
    
    return {
        "type": "add_node",
        "data": node_data
    }

def edit_node_tool(input_data: EditNodeInput) -> Dict[str, Any]:
    """
    Edit an existing node's parameters.
    
    Args:
        input_data: Specification for the node to edit
        
    Returns:
        Dict with the action information
    """
    return {
        "type": "edit_node",
        "node_id": input_data.node_id,
        "parameters": input_data.parameters
    }

def connect_nodes_tool(input_data: ConnectNodesInput) -> Dict[str, Any]:
    """
    Connect two nodes together.
    
    Args:
        input_data: Specification for the connection
        
    Returns:
        Dict with the action information
    """
    return {
        "type": "connect_nodes",
        "source_id": input_data.source_id,
        "target_id": input_data.target_id,
        "source_handle": input_data.source_handle,
        "target_handle": input_data.target_handle
    }

def create_workflow_tool(input_data: CreateWorkflowInput) -> Dict[str, Any]:
    """
    Create a new workflow.
    
    Args:
        input_data: Specification for the new workflow
        
    Returns:
        Dict with the action information
    """
    return {
        "type": "create_workflow",
        "name": input_data.name
    }

# Map of tool name to function
AGENT_TOOLS = {
    "add_node": add_node_tool,
    "edit_node": edit_node_tool,
    "connect_nodes": connect_nodes_tool,
    "create_workflow": create_workflow_tool
}

# Agent tool descriptions for the OpenAI function calling API
AGENT_TOOL_DESCRIPTIONS = [
    {
        "type": "function",
        "function": {
            "name": "add_node",
            "description": "Add a new node to the Langflow canvas",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_type": {
                        "type": "string",
                        "description": "Type of node to add (e.g., 'ChatOpenAI', 'PromptTemplate')"
                    },
                    "position": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "X coordinate on the canvas"
                            },
                            "y": {
                                "type": "number",
                                "description": "Y coordinate on the canvas"
                            }
                        },
                        "description": "Position on canvas (if not provided, will use default placement)"
                    },
                    "id": {
                        "type": "string",
                        "description": "Optional ID for the node (if not provided, will be generated)"
                    }
                },
                "required": ["node_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_node",
            "description": "Edit an existing node's parameters",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "ID of the node to edit"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Parameters to update on the node"
                    }
                },
                "required": ["node_id", "parameters"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "connect_nodes",
            "description": "Connect two nodes together",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "ID of the source node"
                    },
                    "target_id": {
                        "type": "string",
                        "description": "ID of the target node"
                    },
                    "source_handle": {
                        "type": "string",
                        "description": "Optional source handle (if specific)"
                    },
                    "target_handle": {
                        "type": "string",
                        "description": "Optional target handle (if specific)"
                    }
                },
                "required": ["source_id", "target_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_workflow",
            "description": "Create a new workflow",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the new workflow"
                    }
                },
                "required": ["name"]
            }
        }
    }
]

# Common workflow patterns and components

def create_question_answering_workflow() -> List[Dict[str, Any]]:
    """
    Create a standard question-answering workflow.
    
    Returns:
        List of actions to create a question-answering workflow
    """
    qa_prompt = """You are a helpful AI assistant who answers questions accurately and concisely, based on the provided context.

Question: {question}
"""

    chatbot_id = f"ChatOpenAI_{str(uuid.uuid4())[:8]}"
    prompt_id = f"PromptTemplate_{str(uuid.uuid4())[:8]}"
    input_id = f"InputField_{str(uuid.uuid4())[:8]}"
    
    return [
        {
            "type": "add_node",
            "data": {
                "id": input_id,
                "type": "genericNode",
                "position": {"x": 100, "y": 100},
                "data": {
                    "type": "InputField",
                    "node": {
                        "template": {
                            "content": {
                                "value": "",
                                "type": "str"
                            }
                        }
                    }
                }
            }
        },
        {
            "type": "add_node",
            "data": {
                "id": prompt_id,
                "type": "genericNode",
                "position": {"x": 100, "y": 250},
                "data": {
                    "type": "PromptTemplate",
                    "node": {
                        "template": {
                            "template": {
                                "value": qa_prompt,
                                "type": "str"
                            }
                        }
                    }
                }
            }
        },
        {
            "type": "add_node",
            "data": {
                "id": chatbot_id,
                "type": "genericNode",
                "position": {"x": 100, "y": 400},
                "data": {
                    "type": "ChatOpenAI",
                    "node": {
                        "template": {
                            "model_name": {
                                "value": "gpt-3.5-turbo",
                                "type": "str"
                            },
                            "temperature": {
                                "value": 0.7,
                                "type": "float"
                            }
                        }
                    }
                }
            }
        },
        {
            "type": "connect_nodes",
            "source_id": input_id,
            "target_id": prompt_id,
            "source_handle": "output",
            "target_handle": "question"
        },
        {
            "type": "connect_nodes",
            "source_id": prompt_id,
            "target_id": chatbot_id,
            "source_handle": "output",
            "target_handle": "input"
        }
    ]
