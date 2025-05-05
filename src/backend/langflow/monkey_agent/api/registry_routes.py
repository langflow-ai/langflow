"""
API routes for the enhanced node registry
"""
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends

from ..registry.utils import get_or_create_registry
from ..registry.compatibility import find_compatible_connections, TYPE_COMPATIBILITY

# Create router - will be mounted at a prefix by the main API
router = APIRouter()

@router.get("/registry")
async def get_enhanced_registry() -> Dict[str, Any]:
    """Get the complete enhanced node registry"""
    registry = get_or_create_registry()
    return registry.to_dict()

@router.get("/registry/node/{node_id}")
async def get_node_registry_entry(node_id: str) -> Dict[str, Any]:
    """Get details for a specific node in the enhanced registry"""
    registry = get_or_create_registry()
    node = registry.get_node(node_id)
    if node:
        return node.to_dict()
    return {"error": f"Node {node_id} not found"}

@router.get("/registry/compatibility")
async def get_compatibility_matrix() -> Dict[str, List[str]]:
    """Get the type compatibility matrix"""
    return TYPE_COMPATIBILITY

@router.post("/connection/suggest")
async def suggest_connection(source_id: str, target_id: str) -> List[Dict[str, Any]]:
    """Suggest valid connections between two node types"""
    registry = get_or_create_registry()
    connections = find_compatible_connections(source_id, target_id, registry)
    return connections
