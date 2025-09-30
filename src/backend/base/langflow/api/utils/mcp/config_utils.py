import asyncio
import platform
from asyncio.subprocess import create_subprocess_exec
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from lfx.base.mcp.constants import MAX_MCP_SERVER_NAME_LENGTH
from lfx.base.mcp.util import sanitize_mcp_name
from lfx.log import logger
from lfx.services.deps import get_settings_service
from sqlmodel import select

from langflow.api.v2.mcp import get_server_list, update_server
from langflow.services.auth.mcp_encryption import encrypt_auth_settings
from langflow.services.database.models import Flow, Folder
from langflow.services.database.models.api_key.crud import create_api_key
from langflow.services.database.models.api_key.model import ApiKeyCreate
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_storage_service

ALL_INTERFACES_HOST = "0.0.0.0"  # noqa: S104


class MCPServerValidationResult:
    """Represents the result of an MCP server validation check.

    This class encapsulates the outcome of checking whether an MCP server
    configuration can be safely created or updated for a given project. The typical
    sequence is as follows:

    1. Initiation: An operation requiring an MCP server (e.g., creating a
        new project with MCP enabled) triggers a validation check.
    2. Validation: The validate_mcp_server_for_project function is called.
        It generates the expected server name from the project name and checks
        if a server with that name already exists.
    3. Ownership Check: If a server exists, the function verifies if it
        belongs to the current project by checking for the project's UUID in
        the server's configuration.
    4. Result: An instance of this class is returned, summarizing whether
        the server exists and if the project ID matches.
    5. Decision: The calling code uses the properties of this result
        (has_conflict, should_skip, should_proceed) to determine the next
        action, such as aborting on conflict, skipping if already configured,
        or proceeding with the setup.
    """

    def __init__(
        self,
        *,
        server_exists: bool,
        project_id_matches: bool,
        server_name: str = "",
        existing_config: dict | None = None,
        conflict_message: str = "",
    ):
        self.server_exists = server_exists
        self.project_id_matches = project_id_matches
        self.server_name = server_name
        self.existing_config = existing_config
        self.conflict_message = conflict_message

    @property
    def has_conflict(self) -> bool:
        """Returns True when an MCP server name collision occurs.

        This indicates that another project is already using the desired server name.
        """
        return self.server_exists and not self.project_id_matches

    @property
    def should_skip(self) -> bool:
        """Returns True when the MCP server configuration is already correct for this project.

        This indicates that the server exists and is properly configured for the current project.
        """
        return self.server_exists and self.project_id_matches

    @property
    def should_proceed(self) -> bool:
        """Returns True when MCP server setup can proceed safely without conflicts.

        This indicates either no server exists (safe to create) or the existing server
        belongs to the current project (safe to update).
        """
        return not self.server_exists or self.project_id_matches


async def validate_mcp_server_for_project(
    project_id: UUID,
    project_name: str,
    user,
    session,
    storage_service,
    settings_service,
    operation: str = "create",
) -> MCPServerValidationResult:
    """Validate MCP server for a project operation.

    Args:
        project_id: The project UUID
        project_name: The project name
        user: The user performing the operation
        session: Database session
        storage_service: Storage service
        settings_service: Settings service
        operation: Operation type ("create", "update", "delete")

    Returns:
        MCPServerValidationResult with validation details
    """
    # Generate server name that would be used for this project
    server_name = f"lf-{sanitize_mcp_name(project_name)[: (MAX_MCP_SERVER_NAME_LENGTH - 4)]}"

    try:
        existing_servers = await get_server_list(user, session, storage_service, settings_service)

        if server_name not in existing_servers.get("mcpServers", {}):
            # Server doesn't exist
            return MCPServerValidationResult(
                project_id_matches=False,
                server_exists=False,
                server_name=server_name,
            )

        # Server exists - check if project ID matches
        existing_server_config = existing_servers["mcpServers"][server_name]
        existing_args = existing_server_config.get("args", [])
        project_id_matches = False

        if existing_args:
            # SSE URL is typically the last argument
            # TODO: Better way Required to check the postion of the SSE URL in the args
            existing_sse_urls = await extract_urls_from_strings(existing_args)
            for existing_sse_url in existing_sse_urls:
                if str(project_id) in existing_sse_url:
                    project_id_matches = True
                    break
        else:
            project_id_matches = False

        # Generate appropriate conflict message based on operation
        conflict_message = ""
        if not project_id_matches:
            if operation == "create":
                conflict_message = (
                    f"MCP server name conflict: '{server_name}' already exists "
                    f"for a different project. Cannot create MCP server for project "
                    f"'{project_name}' (ID: {project_id})"
                )
            elif operation == "update":
                conflict_message = (
                    f"MCP server name conflict: '{server_name}' exists for a different project. "
                    f"Cannot update MCP server for project '{project_name}' (ID: {project_id})"
                )
            elif operation == "delete":
                conflict_message = (
                    f"MCP server '{server_name}' exists for a different project. "
                    f"Cannot delete MCP server for project '{project_name}' (ID: {project_id})"
                )

        return MCPServerValidationResult(
            server_exists=True,
            project_id_matches=project_id_matches,
            server_name=server_name,
            existing_config=existing_server_config,
            conflict_message=conflict_message,
        )

    except Exception as e:  # noqa: BLE001
        await logger.awarning(f"Could not validate MCP server for project {project_id}: {e}")
        # Return result allowing operation to proceed on validation failure
        return MCPServerValidationResult(
            project_id_matches=False,
            server_exists=False,
            server_name=server_name,
        )


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
            stdout, _ = await proc.communicate()

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
    # Check if auto-configure is enabled
    settings_service = get_settings_service()
    await logger.adebug("Starting auto-configure starter projects MCP")
    if not settings_service.settings.add_projects_to_mcp_servers:
        await logger.adebug("Auto-Configure MCP servers disabled, skipping starter project MCP configuration")
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

                # Validate MCP server for this starter projects folder
                validation_result = await validate_mcp_server_for_project(
                    user_starter_folder.id,
                    DEFAULT_FOLDER_NAME,
                    user,
                    session,
                    get_storage_service(),
                    settings_service,
                    operation="create",
                )

                # Skip if server already exists for this starter projects folder
                if validation_result.should_skip:
                    await logger.adebug(
                        f"MCP server '{validation_result.server_name}' already exists for user "
                        f"{user.username}'s starter projects (project ID: "
                        f"{user_starter_folder.id}), skipping"
                    )
                    continue  # Skip this user since server already exists for the same project

                server_name = validation_result.server_name

                # Set up THIS USER'S starter folder authentication (same as new projects)
                # If AUTO_LOGIN is false, automatically enable API key authentication
                default_auth = {"auth_type": "none"}
                await logger.adebug(f"Settings service auth settings: {settings_service.auth_settings}")
                await logger.adebug(f"User starter folder auth settings: {user_starter_folder.auth_settings}")
                if not settings_service.auth_settings.AUTO_LOGIN and not user_starter_folder.auth_settings:
                    default_auth = {"auth_type": "apikey"}
                    user_starter_folder.auth_settings = encrypt_auth_settings(default_auth)
                    await logger.adebug(f"Set up auth settings for user {user.username}'s starter folder")
                elif user_starter_folder.auth_settings:
                    default_auth = user_starter_folder.auth_settings

                # Create API key for this user to access their own starter projects
                api_key_name = f"MCP Project {DEFAULT_FOLDER_NAME} - {user.username}"
                unmasked_api_key = await create_api_key(session, ApiKeyCreate(name=api_key_name), user.id)

                # Build SSE URL for THIS USER'S starter folder (unique ID per user)
                sse_url = await get_project_sse_url(user_starter_folder.id)

                # Prepare server config (similar to new project creation)
                if default_auth.get("auth_type", "none") == "apikey":
                    command = "uvx"
                    args = [
                        "mcp-proxy",
                        "--headers",
                        "x-api-key",
                        unmasked_api_key.api_key,
                        sse_url,
                    ]
                elif default_auth.get("auth_type", "none") == "oauth":
                    msg = "OAuth authentication is not yet implemented for MCP server creation during project creation."
                    logger.warning(msg)
                    raise HTTPException(status_code=501, detail=msg)
                else:  # default_auth_type == "none"
                    # No authentication - direct connection
                    command = "uvx"
                    args = [
                        "mcp-proxy",
                        sse_url,
                    ]
                server_config = {"command": command, "args": args}

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

        await session.commit()

        if total_servers_added > 0:
            await logger.adebug(f"Added starter projects MCP servers for {total_servers_added} users")
        else:
            await logger.adebug("No new starter project MCP servers were added")

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Failed to auto-configure starter projects MCP servers: {e}")


async def extract_urls_from_strings(strings: list[str]) -> list[str]:
    """Extract URLs from a list of strings.

    Args:
        strings: List of strings to search for URLs

    Returns:
        List of URLs found in the input strings
    """
    import re

    # URL pattern to match http/https URLs
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;:!?]'

    urls = []
    for string in strings:
        if isinstance(string, str):
            found_urls = re.findall(url_pattern, string)
            urls.extend(found_urls)

    return urls
