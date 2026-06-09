"""V2 API module."""

from .files import router as files_router
from .mcp import router as mcp_router
from .registration import router as registration_router
from .workflow import router as workflow_router

__all__ = ["files_router", "mcp_router", "registration_router", "workflow_router"]
