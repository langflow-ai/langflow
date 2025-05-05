from typing import Dict, List, Optional, Any
from pydantic import BaseModel

class Action(BaseModel):
    """Base action class for AI Agent actions"""
    type: str

class AddNodeAction(Action):
    """Action to add a node to the canvas"""
    type: str = "add_node"
    data: Dict[str, Any]

class EditNodeAction(Action):
    """Action to edit a node's parameters"""
    type: str = "edit_node"
    node_id: str
    parameters: Dict[str, Any]

class ConnectNodesAction(Action):
    """Action to connect two nodes"""
    type: str = "connect_nodes"
    source_id: str
    target_id: str
    source_handle: str
    target_handle: str

class CreateWorkflowAction(Action):
    """Action to create a new workflow"""
    type: str = "create_workflow"
    name: str
