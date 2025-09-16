"""Utilities for preparing Model Context Protocol servers per organisation."""

from __future__ import annotations

import logging

from sqlmodel import select

from langflow.api.v1.mcp_projects import get_project_mcp_server, get_project_sse
from langflow.services.database.models import Folder
from langflow.services.database.organisation import OrganizationService
from langflow.services.deps import get_settings_service

logger = logging.getLogger(__name__)


async def init_mcp_servers_for_org(org_id: str) -> None:
    """Initialise MCP servers for every project stored in the given organisation."""
    db_service = OrganizationService.get_db_service_for_org(org_id)
    async with db_service.with_session() as session:
        projects = (await session.exec(select(Folder))).all()

        for project in projects:
            try:
                get_project_sse(project.id)
                get_project_mcp_server(project.id)
            except Exception as exc:
                msg = f"Failed to initialize MCP server for project {project.id}: {exc}"
                logger.exception(msg)


async def init_mcp_servers_for_all_orgs() -> None:
    """Discover organisation databases and prepare MCP servers for each of them."""
    settings_service = get_settings_service()
    if not settings_service.auth_settings.CLERK_AUTH_ENABLED:
        return

    org_ids = await OrganizationService.list_existing_org_ids()
    if not org_ids:
        return

    for org_id in org_ids:
        try:
            await init_mcp_servers_for_org(org_id)
        except Exception:
            logger.exception("Failed to initialise MCP servers for organisation %s", org_id)
