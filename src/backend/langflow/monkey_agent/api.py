"""
Monkey Agent API Endpoints

This module contains the API endpoints for the Monkey Agent backend.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

# Create API router
router = APIRouter(
    prefix="/api/v1/monkey-agent",
    tags=["Monkey Agent"],
    responses={404: {"description": "Not found"}},
)

class NodeTypeResponse(BaseModel):
    """Response model for node types"""
    types: Dict[str, Dict[str, Any]]
    categories: Dict[str, list]
    
class CommandRequest(BaseModel):
    """Request model for command processing"""
    message: str
    flow_state: Dict[str, Any]
    api_key: Optional[str] = None
    
class CommandResponse(BaseModel):
    """Response model for command processing"""
    message: str
    success: bool
    action: str
    details: Dict[str, Any]

@router.get("/node-types")
async def get_node_types() -> NodeTypeResponse:
    """
    Get all available node types for use in the Monkey Agent.
    
    This is a placeholder that will be implemented later to provide
    context-aware node creation capabilities.
    """
    # This will eventually fetch node types from the Langflow backend
    return NodeTypeResponse(
        types={},
        categories={}
    )

@router.post("/process-command")
async def process_command(request: CommandRequest) -> CommandResponse:
    """
    Process a command from the Monkey Agent.
    
    This is a placeholder that will be implemented later to provide
    more sophisticated command processing capabilities.
    """
    # This will eventually process commands using AI
    return CommandResponse(
        message="Command processing not yet implemented on the backend.",
        success=False,
        action="unimplemented",
        details={"message": request.message}
    )
