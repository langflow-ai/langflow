import asyncio
import platform
from asyncio.subprocess import create_subprocess_exec
from datetime import datetime, timezone
from uuid import UUID

from lfx.base.mcp.constants import MAX_MCP_SERVER_NAME_LENGTH
from lfx.base.mcp.util import sanitize_mcp_name
from lfx.log import logger
from lfx.services.deps import get_settings_service
from sqlmodel import select

from langflow.api.v2.mcp import update_server
from langflow.services.auth.mcp_encryption import encrypt_auth_settings
from langflow.services.database.models import Flow, Folder
from langflow.services.database.models.api_key.crud import create_api_key
from langflow.services.database.models.api_key.model import ApiKeyCreate
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_storage_service

# Constants
ALL_INTERFACES_HOST = "0.0.0.0"  # noqa: S104


async def get_url_by_os(host: str, port: int, url: str) -> str:
    """Get the URL by operating system."""
    os_type = platform.system()
    is_wsl = os_type == "Linux" and "microsoft" in platform.uname().release.lower()

    if is_wsl and host in {"localhost", "127.0.0.1"}:
        try:
            proc = await create_subprocess_exec(
                "/usr/bin/hostname",
                "-I",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0 and stdout.strip():
                wsl_ip = stdout.decode().strip().split()[0]  # Get first IP address
                await logger.adebug("Using WSL IP for external access: %s", wsl_ip)
                # Replace the localhost with the WSL IP in the URL
                url = url.replace(f"http://{host}:{port}", f"http://{wsl_ip}:{port}")
        except OSError as e:
            await logger.awarning("Failed to get WSL IP address: %s. Using default URL.", str(e))

    return url


async def get_project_sse_url(project_id: UUID) -> str:
    """Generate the SSE URL for a project, including WSL handling."""
    # Get settings service to build the SSE URL
    settings_service = get_settings_service()
    server_host = getattr(settings_service.settings, "host", "localhost")
    # Use the runtime-detected port if available, otherwise fall back to configured port
    server_port = (
        getattr(settings_service.settings, "runtime_port", None)
        or getattr(settings_service.settings, "port", None)
        or 7860
    )

    # For MCP clients, always use localhost instead of 0.0.0.0
    # 0.0.0.0 is a bind address, not a connect address
    host = "localhost" if server_host == ALL_INTERFACES_HOST else server_host
    port = server_port

    base_url = f"http://{host}:{port}".rstrip("/")
    project_sse_url = f"{base_url}/api/v1/mcp/project/{project_id}/sse"

    return await get_url_by_os(host, port, project_sse_url)


async def auto_configure_starter_projects_mcp(session):
    """Auto-configure MCP servers for starter projects for all users at startup."""
    # Check if auto-add is enabled
    settings_service = get_settings_service()
    await logger.adebug("Starting auto-configure starter projects MCP")
    if not settings_service.settings.add_projects_to_mcp_servers:
        await logger.adebug("Auto-add MCP servers disabled, skipping starter project MCP configuration")
        return
    await logger.adebug(
        f"Auto-configure settings: add_projects_to_mcp_servers="
        f"{settings_service.settings.add_projects_to_mcp_servers}, "
        f"create_starter_projects={settings_service.settings.create_starter_projects}, "
        f"update_starter_projects={settings_service.settings.update_starter_projects}"
    )

    try:
        # Get all users in the system
        users = (await session.exec(select(User))).all()
        await logger.adebug(f"Found {len(users)} users in the system")
        if not users:
            await logger.adebug("No users found, skipping starter project MCP configuration")
            return

        # Add starter projects to each user's MCP server configuration
        total_servers_added = 0
        for user in users:
            await logger.adebug(f"Processing user: {user.username} (ID: {user.id})")
            try:
                # First, let's see what folders this user has
                all_user_folders = (await session.exec(select(Folder).where(Folder.user_id == user.id))).all()
                folder_names = [f.name for f in all_user_folders]
                await logger.adebug(f"User {user.username} has folders: {folder_names}")

                # Find THIS USER'S own starter projects folder
                # Each user has their own "Starter Projects" folder with unique ID
                user_starter_folder = (
                    await session.exec(
                        select(Folder).where(
                            Folder.name == DEFAULT_FOLDER_NAME,
                            Folder.user_id == user.id,  # Each user has their own!
                        )
                    )
                ).first()
                if not user_starter_folder:
                    await logger.adebug(
                        f"No starter projects folder ('{DEFAULT_FOLDER_NAME}') found for user {user.username}, skipping"
                    )
                    # Log what folders this user does have for debugging
                    await logger.adebug(f"User {user.username} available folders: {folder_names}")
                    continue

                await logger.adebug(
                    f"Found starter folder '{user_starter_folder.name}' for {user.username}: "
                    f"ID={user_starter_folder.id}"
                )

                # Configure MCP settings for flows in THIS USER'S starter folder
                flows_query = select(Flow).where(
                    Flow.folder_id == user_starter_folder.id,
                    Flow.is_component == False,  # noqa: E712
                )
                user_starter_flows = (await session.exec(flows_query)).all()

                # Enable MCP for starter flows if not already configured
                flows_configured = 0
                for flow in user_starter_flows:
                    if flow.mcp_enabled is None:
                        flow.mcp_enabled = True
                        if not flow.action_name:
                            flow.action_name = sanitize_mcp_name(flow.name)
                        if not flow.action_description:
                            flow.action_description = flow.description or f"Starter project: {flow.name}"
                        flow.updated_at = datetime.now(timezone.utc)
                        session.add(flow)
                        flows_configured += 1

                if flows_configured > 0:
                    await logger.adebug(f"Enabled MCP for {flows_configured} starter flows for user {user.username}")

                # Set up THIS USER'S starter folder authentication (same as new projects)
                if not user_starter_folder.auth_settings:
                    user_starter_folder.auth_settings = encrypt_auth_settings({"auth_type": "apikey"})
                    session.add(user_starter_folder)
                    await logger.adebug(f"Set up auth settings for user {user.username}'s starter folder")

                # Create API key for this user to access their own starter projects
                api_key_name = f"MCP Project {DEFAULT_FOLDER_NAME} - {user.username}"
                unmasked_api_key = await create_api_key(session, ApiKeyCreate(name=api_key_name), user.id)

                # Build SSE URL for THIS USER'S starter folder (unique ID per user)
                sse_url = await get_project_sse_url(user_starter_folder.id)

                # Prepare server config (similar to new project creation)
                command = "uvx"
                args = [
                    "mcp-proxy",
                    "--headers",
                    "x-api-key",
                    unmasked_api_key.api_key,
                    sse_url,
                ]
                server_config = {"command": command, "args": args}

                # Create unique server name for starter projects
                server_name = f"lf-{sanitize_mcp_name(DEFAULT_FOLDER_NAME)[: (MAX_MCP_SERVER_NAME_LENGTH - 4)]}"

                # Add to user's MCP servers configuration
                await logger.adebug(f"Adding MCP server '{server_name}' for user {user.username}")
                await update_server(
                    server_name,
                    server_config,
                    user,
                    session,
                    get_storage_service(),
                    settings_service,
                )

                total_servers_added += 1
                await logger.adebug(f"Added starter projects MCP server for user: {user.username}")

            except Exception as e:  # noqa: BLE001
                # If server already exists or other issues, just log and continue
                await logger.aerror(f"Could not add starter projects MCP server for user {user.username}: {e}")
                continue

        # Commit all changes at the end
        await session.commit()

        if total_servers_added > 0:
            await logger.adebug(f"Added starter projects MCP servers for {total_servers_added} users")
        else:
            await logger.adebug("No new starter project MCP servers were added")

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Failed to auto-configure starter projects MCP servers: {e}")
        # Don't raise the exception to avoid breaking startup
