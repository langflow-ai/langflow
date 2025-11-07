"""Utilities for auto-configuring the Langflow Agentic MCP server."""

import sys

from lfx.log.logger import logger
from lfx.services.deps import get_settings_service
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.v2.mcp import get_server_list, update_server
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_service
from langflow.services.schema import ServiceType


async def auto_configure_agentic_mcp_server(session: AsyncSession) -> None:
    """Auto-configure the Langflow Agentic MCP server for all users.

    This function adds the langflow-agentic MCP server to each user's MCP
    configuration, making the agentic tools available in their MCP clients
    (like Claude Desktop).

    Args:
        session: Database session for querying users.
    """
    settings_service = get_settings_service()

    # Only configure if agentic experience is enabled
    if not settings_service.settings.agentic_experience:
        await logger.adebug("Agentic experience disabled, skipping agentic MCP server configuration")
        return

    await logger.ainfo("Auto-configuring Langflow Agentic MCP server for all users...")

    try:
        # Get all users in the system
        users = (await session.exec(select(User))).all()
        await logger.adebug(f"Found {len(users)} users in the system")

        if not users:
            await logger.adebug("No users found, skipping agentic MCP server configuration")
            return

        # Get services
        storage_service = get_service(ServiceType.STORAGE_SERVICE)

        # Server configuration
        server_name = "langflow-agentic"
        python_executable = sys.executable
        server_config = {
            "command": python_executable,
            "args": ["-m", "langflow.agentic.mcp"],
            "metadata": {
                "description": "Langflow Agentic MCP server providing tools for flow/component operations, "
                "template search, and graph visualization",
                "auto_configured": True,
                "langflow_internal": True,
            },
        }

        # Add server to each user's configuration
        servers_added = 0
        servers_skipped = 0

        for user in users:
            try:
                await logger.adebug(f"Configuring agentic MCP server for user: {user.username}")

                # Check if server already exists for this user
                try:
                    server_list = await get_server_list(user, session, storage_service, settings_service)
                    server_exists = server_name in server_list.get("mcpServers", {})

                    if server_exists:
                        await logger.adebug(
                            f"Agentic MCP server already exists for user {user.username}, skipping"
                        )
                        servers_skipped += 1
                        continue

                except Exception as e:
                    # If listing fails, skip this user to avoid duplicates
                    await logger.awarning(
                        f"Could not check existing servers for user {user.username}: {e}. "
                        "Skipping to avoid potential duplicates."
                    )
                    servers_skipped += 1
                    continue

                # Add the server
                await update_server(
                    server_name=server_name,
                    server_config=server_config,
                    current_user=user,
                    session=session,
                    storage_service=storage_service,
                    settings_service=settings_service,
                )

                servers_added += 1
                await logger.adebug(f"Added agentic MCP server for user: {user.username}")

            except Exception as e:
                await logger.aexception(f"Failed to configure agentic MCP server for user {user.username}: {e}")
                continue

        await logger.ainfo(
            f"Agentic MCP server configuration complete: {servers_added} added, {servers_skipped} skipped"
        )

    except Exception as e:
        await logger.aexception(f"Error during agentic MCP server auto-configuration: {e}")


async def remove_agentic_mcp_server(session: AsyncSession) -> None:
    """Remove the Langflow Agentic MCP server from all users.

    This function removes the langflow-agentic MCP server from each user's MCP
    configuration. Used when agentic experience is disabled.

    Args:
        session: Database session for querying users.
    """
    await logger.ainfo("Removing Langflow Agentic MCP server from all users...")

    try:
        # Get all users
        users = (await session.exec(select(User))).all()

        if not users:
            await logger.adebug("No users found")
            return

        # Get services
        storage_service = get_service(ServiceType.STORAGE_SERVICE)
        settings_service = get_settings_service()

        server_name = "langflow-agentic"
        servers_removed = 0

        for user in users:
            try:
                # Remove the server by passing empty config
                await update_server(
                    server_name=server_name,
                    server_config={},  # Empty config removes the server
                    current_user=user,
                    session=session,
                    storage_service=storage_service,
                    settings_service=settings_service,
                )

                servers_removed += 1
                await logger.adebug(f"Removed agentic MCP server for user: {user.username}")

            except Exception as e:
                await logger.adebug(f"Could not remove agentic MCP server for user {user.username}: {e}")
                continue

        await logger.ainfo(f"Removed agentic MCP server from {servers_removed} users")

    except Exception as e:
        await logger.aexception(f"Error removing agentic MCP server: {e}")
