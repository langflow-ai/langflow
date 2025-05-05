"""
Backend Implementation Module

This module contains a backend implementation that is currently disabled.
"""

__version__ = "0.1.0"

from fastapi import APIRouter

# Initialize the API router
api_router = APIRouter(prefix="/feature", tags=["Feature"])

# Import registry routes
from .api.registry_routes import router as registry_router

# Include registry routes
api_router.include_router(registry_router)

# Function to initialize the module
def init_monkey_agent():
    """Initialize the module"""
    from .registry.utils import build_registry, save_registry
    
    # Build and save the registry
    registry = build_registry()
    save_registry(registry)
    
    return api_router

# Note: We're deliberately not calling init_monkey_agent() here
# to avoid integration issues and just get the system running
