from fastapi import APIRouter

from langflow.api.v2.files import router as files_router
from langflow.api.v2.mcp import router as mcp_router

__all__ = [
    "files_router",
    "mcp_router",
]
