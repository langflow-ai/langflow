from __future__ import annotations

from contextlib import asynccontextmanager

from langflow.api.v1.mcp_projects import (
    project_mcp_servers,
    start_project_task_group,
    stop_project_task_group,
)


@asynccontextmanager
async def project_session_manager_lifespan():
    """Test helper to ensure project session managers start and stop cleanly."""
    await start_project_task_group()
    try:
        yield
    finally:
        await stop_project_task_group()
        project_mcp_servers.clear()
