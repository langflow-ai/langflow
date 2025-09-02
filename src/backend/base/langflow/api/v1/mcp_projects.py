import asyncio
import json
import os
import platform
from asyncio.subprocess import create_subprocess_exec
from contextvars import ContextVar
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from subprocess import CalledProcessError
from typing import Annotated, Any
from uuid import UUID

from anyio import BrokenResourceError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from lfx.base.mcp.constants import MAX_MCP_SERVER_NAME_LENGTH
from lfx.base.mcp.util import sanitize_mcp_name
from lfx.log import logger
from lfx.services.deps import get_settings_service, session_scope
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport
from sqlalchemy.orm import selectinload
from sqlmodel import select

from langflow.api.utils import CurrentActiveMCPUser
from langflow.api.v1.mcp_utils import (
    current_user_ctx,
    handle_call_tool,
    handle_list_resources,
    handle_list_tools,
    handle_mcp_errors,
    handle_read_resource,
)
from langflow.api.v1.schemas import (
    AuthSettings,
    MCPInstallRequest,
    MCPProjectResponse,
    MCPProjectUpdateRequest,
    MCPSettings,
)
from langflow.services.auth.mcp_encryption import decrypt_auth_settings, encrypt_auth_settings
from langflow.services.database.models import Flow, Folder
from langflow.services.database.models.api_key.crud import check_key, create_api_key
from langflow.services.database.models.api_key.model import ApiKeyCreate
from langflow.services.database.models.user.model import User

router = APIRouter(prefix="/mcp/project", tags=["mcp_projects"])


async def verify_project_auth(
    project_id: UUID,
    query_param: str | None = None,
    header_param: str | None = None,
) -> User:
    """Custom authentication for MCP project endpoints when API key is required.

    This is only used when MCP composer is enabled and project requires API key auth.
    """
    async with session_scope() as session:
        # First, get the project to check its auth settings
        project = (await session.exec(select(Folder).where(Folder.id == project_id))).first()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # For MCP composer enabled, only use API key
        api_key = query_param or header_param
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="API key required for this project. Provide x-api-key header or query parameter.",
            )

        # Validate the API key
        user = await check_key(session, api_key)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Verify user has access to the project
        project_access = (
            await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == user.id))
        ).first()

        if not project_access:
            raise HTTPException(status_code=403, detail="Access denied to this project")

        return user


# Smart authentication dependency that chooses method based on project settings
async def verify_project_auth_conditional(
    project_id: UUID,
    request: Request,
) -> User:
    """Choose authentication method based on project settings.

    - MCP Composer enabled + API key auth: Only allow API keys
    - All other cases: Use standard MCP auth (JWT + API keys)
    """
    async with session_scope() as session:
        # Get project to check auth settings
        project = (await session.exec(select(Folder).where(Folder.id == project_id))).first()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Check if this project requires API key only authentication
        if FEATURE_FLAGS.mcp_composer and project.auth_settings:
            auth_settings = AuthSettings(**project.auth_settings)
            if auth_settings.auth_type == "apikey":
                # For MCP composer projects with API key auth, use custom API key validation
                api_key_header_value = request.headers.get("x-api-key")
                api_key_query_value = request.query_params.get("x-api-key")
                return await verify_project_auth(project_id, api_key_query_value, api_key_header_value)

        # For all other cases, use standard MCP authentication (allows JWT + API keys)
        # Extract token
        token: str | None = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

        # Extract API keys
        api_key_query_value = request.query_params.get("x-api-key")
        api_key_header_value = request.headers.get("x-api-key")

        # Call the MCP auth function directly
        from langflow.services.auth.utils import get_current_user_mcp

        user = await get_current_user_mcp(
            token=token or "", query_param=api_key_query_value, header_param=api_key_header_value, db=session
        )

        # Verify project access
        project_access = (
            await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == user.id))
        ).first()

        if not project_access:
            raise HTTPException(status_code=404, detail="Project not found")

        return user


# Create project-specific context variable
current_project_ctx: ContextVar[UUID | None] = ContextVar("current_project_ctx", default=None)

# Create a mapping of project-specific SSE transports
project_sse_transports = {}


def get_project_sse(project_id: UUID) -> SseServerTransport:
    """Get or create an SSE transport for a specific project."""
    project_id_str = str(project_id)
    if project_id_str not in project_sse_transports:
        project_sse_transports[project_id_str] = SseServerTransport(f"/api/v1/mcp/project/{project_id_str}/")
    return project_sse_transports[project_id_str]


@router.get("/{project_id}")
async def list_project_tools(
    project_id: UUID,
    current_user: CurrentActiveMCPUser,
    *,
    mcp_enabled: bool = True,
) -> MCPProjectResponse:
    """List all tools in a project that are enabled for MCP."""
    tools: list[MCPSettings] = []
    try:
        async with session_scope() as session:
            # Fetch the project first to verify it exists and belongs to the current user
            project = (
                await session.exec(
                    select(Folder)
                    .options(selectinload(Folder.flows))
                    .where(Folder.id == project_id, Folder.user_id == current_user.id)
                )
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Query flows in the project
            flows_query = select(Flow).where(Flow.folder_id == project_id, Flow.is_component == False)  # noqa: E712

            # Optionally filter for MCP-enabled flows only
            if mcp_enabled:
                flows_query = flows_query.where(Flow.mcp_enabled == True)  # noqa: E712

            flows = (await session.exec(flows_query)).all()

            for flow in flows:
                if flow.user_id is None:
                    continue

                # Format the flow name according to MCP conventions (snake_case)
                flow_name = sanitize_mcp_name(flow.name)

                # Use action_name and action_description if available, otherwise use defaults
                name = sanitize_mcp_name(flow.action_name) if flow.action_name else flow_name
                description = flow.action_description or (
                    flow.description if flow.description else f"Tool generated from flow: {flow_name}"
                )
                try:
                    tool = MCPSettings(
                        id=flow.id,
                        action_name=name,
                        action_description=description,
                        mcp_enabled=flow.mcp_enabled,
                        # inputSchema=json_schema_from_flow(flow),
                        name=flow.name,
                        description=flow.description,
                    )
                    tools.append(tool)
                except Exception as e:  # noqa: BLE001
                    msg = f"Error in listing project tools: {e!s} from flow: {name}"
                    await logger.awarning(msg)
                    continue

            # Get project-level auth settings and decrypt sensitive fields
            auth_settings = None
            if project.auth_settings:
                from langflow.api.v1.schemas import AuthSettings

                # Decrypt sensitive fields before returning
                decrypted_settings = decrypt_auth_settings(project.auth_settings)
                auth_settings = AuthSettings(**decrypted_settings) if decrypted_settings else None

    except Exception as e:
        msg = f"Error listing project tools: {e!s}"
        await logger.aexception(msg)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return MCPProjectResponse(tools=tools, auth_settings=auth_settings)


@router.head("/{project_id}/sse", response_class=HTMLResponse, include_in_schema=False)
async def im_alive(project_id: str):  # noqa: ARG001
    return Response()


@router.get("/{project_id}/sse", response_class=HTMLResponse)
async def handle_project_sse(
    project_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(verify_project_auth_conditional)],
):
    """Handle SSE connections for a specific project."""
    # Verify project exists and user has access
    async with session_scope() as session:
        project = (
            await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
        ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get project-specific SSE transport and MCP server
    sse = get_project_sse(project_id)
    project_server = get_project_mcp_server(project_id)
    await logger.adebug("Project MCP server name: %s", project_server.server.name)

    # Set context variables
    user_token = current_user_ctx.set(current_user)
    project_token = current_project_ctx.set(project_id)

    try:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            try:
                await logger.adebug("Starting SSE connection for project %s", project_id)

                notification_options = NotificationOptions(
                    prompts_changed=True, resources_changed=True, tools_changed=True
                )
                init_options = project_server.server.create_initialization_options(notification_options)

                try:
                    await project_server.server.run(streams[0], streams[1], init_options)
                except Exception:  # noqa: BLE001
                    await logger.aexception("Error in project MCP")
            except BrokenResourceError:
                await logger.ainfo("Client disconnected from project SSE connection")
            except asyncio.CancelledError:
                await logger.ainfo("Project SSE connection was cancelled")
                raise
            except Exception:
                await logger.aexception("Error in project MCP")
                raise
    finally:
        current_user_ctx.reset(user_token)
        current_project_ctx.reset(project_token)

    return Response(status_code=200)


@router.post("/{project_id}")
async def handle_project_messages(
    project_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(verify_project_auth_conditional)],
):
    """Handle POST messages for a project-specific MCP server."""
    # Set context variables
    user_token = current_user_ctx.set(current_user)
    project_token = current_project_ctx.set(project_id)

    try:
        sse = get_project_sse(project_id)
        await sse.handle_post_message(request.scope, request.receive, request._send)
    except BrokenResourceError as e:
        await logger.ainfo("Project MCP Server disconnected for project %s", project_id)
        raise HTTPException(status_code=404, detail=f"Project MCP Server disconnected, error: {e}") from e
    finally:
        current_user_ctx.reset(user_token)
        current_project_ctx.reset(project_token)


@router.post("/{project_id}/")
async def handle_project_messages_with_slash(
    project_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(verify_project_auth_conditional)],
):
    """Handle POST messages for a project-specific MCP server with trailing slash."""
    # Call the original handler
    return await handle_project_messages(project_id, request, current_user)


@router.patch("/{project_id}", status_code=200)
async def update_project_mcp_settings(
    project_id: UUID,
    request: MCPProjectUpdateRequest,
    current_user: CurrentActiveMCPUser,
):
    """Update the MCP settings of all flows in a project and project-level auth settings."""
    try:
        async with session_scope() as session:
            # Fetch the project first to verify it exists and belongs to the current user
            project = (
                await session.exec(
                    select(Folder)
                    .options(selectinload(Folder.flows))
                    .where(Folder.id == project_id, Folder.user_id == current_user.id)
                )
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Update project-level auth settings with encryption
            if "auth_settings" in request.model_fields_set:
                if request.auth_settings is None:
                    # Explicitly set to None - clear auth settings
                    project.auth_settings = None
                else:
                    # Use python mode to get raw values without SecretStr masking
                    auth_model = request.auth_settings
                    auth_dict = auth_model.model_dump(mode="python", exclude_none=True)

                    # Extract actual secret values before encryption
                    from pydantic import SecretStr

                    # Handle api_key if it's a SecretStr
                    api_key_val = getattr(auth_model, "api_key", None)
                    if isinstance(api_key_val, SecretStr):
                        auth_dict["api_key"] = api_key_val.get_secret_value()

                    # Handle oauth_client_secret if it's a SecretStr
                    client_secret_val = getattr(auth_model, "oauth_client_secret", None)
                    if isinstance(client_secret_val, SecretStr):
                        auth_dict["oauth_client_secret"] = client_secret_val.get_secret_value()

                    # Encrypt and store
                    encrypted_settings = encrypt_auth_settings(auth_dict)
                    project.auth_settings = encrypted_settings

            session.add(project)

            # Query flows in the project
            flows = (await session.exec(select(Flow).where(Flow.folder_id == project_id))).all()
            flows_to_update = {x.id: x for x in request.settings}

            updated_flows = []
            for flow in flows:
                if flow.user_id is None or flow.user_id != current_user.id:
                    continue

                if flow.id in flows_to_update:
                    settings_to_update = flows_to_update[flow.id]
                    flow.mcp_enabled = settings_to_update.mcp_enabled
                    flow.action_name = settings_to_update.action_name
                    flow.action_description = settings_to_update.action_description
                    flow.updated_at = datetime.now(timezone.utc)
                    session.add(flow)
                    updated_flows.append(flow)

            await session.commit()

            return {"message": f"Updated MCP settings for {len(updated_flows)} flows and project auth settings"}

    except Exception as e:
        msg = f"Error updating project MCP settings: {e!s}"
        await logger.aexception(msg)
        raise HTTPException(status_code=500, detail=str(e)) from e


def is_local_ip(ip_str: str) -> bool:
    """Check if an IP address is a loopback address (same machine).

    Args:
        ip_str: String representation of an IP address

    Returns:
        bool: True if the IP is a loopback address, False otherwise
    """
    # Check if it's exactly "localhost"
    if ip_str == "localhost":
        return True

    # Check if it's exactly "0.0.0.0" (which binds to all interfaces)
    if ip_str == "0.0.0.0":  # noqa: S104
        return True

    try:
        # Convert string to IP address object
        ip = ip_address(ip_str)

        # Check if it's a loopback address (127.0.0.0/8 for IPv4, ::1 for IPv6)
        return bool(ip.is_loopback)
    except ValueError:
        # If the IP address is invalid, default to False
        return False


def get_client_ip(request: Request) -> str:
    """Extract the client IP address from a FastAPI request.

    Args:
        request: FastAPI Request object

    Returns:
        str: The client's IP address
    """
    # Check for X-Forwarded-For header (common when behind proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # The client IP is the first one in the list
        return forwarded_for.split(",")[0].strip()

    # If no proxy headers, use the client's direct IP
    if request.client:
        return request.client.host

    # Fallback if we can't determine the IP - use a non-local IP
    return "255.255.255.255"  # Non-routable IP that will never be local


@router.post("/{project_id}/install")
async def install_mcp_config(
    project_id: UUID,
    body: MCPInstallRequest,
    request: Request,
    current_user: CurrentActiveMCPUser,
):
    """Install MCP server configuration for Cursor, Windsurf, or Claude."""
    # Check if the request is coming from a local IP address
    client_ip = get_client_ip(request)
    if not is_local_ip(client_ip):
        raise HTTPException(status_code=500, detail="MCP configuration can only be installed from a local connection")

    removed_servers: list[str] = []  # Track removed servers for reinstallation
    try:
        # Verify project exists and user has access
        async with session_scope() as session:
            project = (
                await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Check if project requires API key authentication and generate if needed
            generated_api_key = None

            # Determine if we need to generate an API key based on feature flag
            should_generate_api_key = False
            if not FEATURE_FLAGS.mcp_composer:
                # When MCP_COMPOSER is disabled, only generate API key if autologin is disabled
                # (matches frontend !isAutoLogin check)
                settings_service = get_settings_service()
                should_generate_api_key = not settings_service.auth_settings.AUTO_LOGIN
            elif project.auth_settings:
                # When MCP_COMPOSER is enabled, only generate if auth_type is "apikey"
                auth_settings = AuthSettings(**project.auth_settings) if project.auth_settings else AuthSettings()
                should_generate_api_key = auth_settings.auth_type == "apikey"

            if should_generate_api_key:
                # Generate API key with specific name format
                api_key_name = f"MCP Project {project.name} - {body.client}"
                api_key_create = ApiKeyCreate(name=api_key_name)
                unmasked_api_key = await create_api_key(session, api_key_create, current_user.id)
                generated_api_key = unmasked_api_key.api_key

        # Get settings service to build the SSE URL
        settings_service = get_settings_service()
        host = getattr(settings_service.settings, "host", "localhost")
        port = getattr(settings_service.settings, "port", 3000)
        base_url = f"http://{host}:{port}".rstrip("/")
        sse_url = f"{base_url}/api/v1/mcp/project/{project_id}/sse"

        # Determine command and args based on operating system
        os_type = platform.system()
        command = "uvx"

        # Check if running on WSL (will appear as Linux but with Microsoft in release info)
        is_wsl = os_type == "Linux" and "microsoft" in platform.uname().release.lower()

        if is_wsl:
            await logger.adebug("WSL detected, using Windows-specific configuration")

            # If we're in WSL and the host is localhost, we might need to adjust the URL
            # so Windows applications can reach the WSL service
            if host in {"localhost", "127.0.0.1"}:
                try:
                    # Try to get the WSL IP address for host.docker.internal or similar access

                    # This might vary depending on WSL version and configuration
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
                        sse_url = sse_url.replace(f"http://{host}:{port}", f"http://{wsl_ip}:{port}")
                except OSError as e:
                    await logger.awarning("Failed to get WSL IP address: %s. Using default URL.", str(e))

        # Base args
        args = ["mcp-composer"] if FEATURE_FLAGS.mcp_composer else ["mcp-proxy"]

        # Add authentication args based on MCP_COMPOSER feature flag and auth settings
        if not FEATURE_FLAGS.mcp_composer:
            # When MCP_COMPOSER is disabled, only use headers format if API key was generated
            # (when autologin is disabled)
            if generated_api_key:
                args.extend(["--headers", "x-api-key", generated_api_key])
        elif project.auth_settings:
            # Decrypt sensitive fields before using them
            decrypted_settings = decrypt_auth_settings(project.auth_settings)
            auth_settings = AuthSettings(**decrypted_settings) if decrypted_settings else AuthSettings()
            args.extend(["--auth_type", auth_settings.auth_type])

            # When MCP_COMPOSER is enabled, only add headers if auth_type is "apikey"
            auth_settings = AuthSettings(**project.auth_settings)
            if auth_settings.auth_type == "apikey" and generated_api_key:
                args.extend(["--headers", "x-api-key", generated_api_key])
            # If no auth_settings or auth_type is "none", don't add any auth headers

        # Add the SSE URL
        if FEATURE_FLAGS.mcp_composer:
            args.extend(["--sse-url", sse_url])
        else:
            args.append(sse_url)

        if os_type == "Windows":
            command = "cmd"
            args = ["/c", "uvx", *args]
            await logger.adebug("Windows detected, using cmd command")

        name = project.name

        # Create the MCP configuration
        server_config: dict[str, Any] = {
            "command": command,
            "args": args,
        }

        mcp_config = {
            "mcpServers": {f"lf-{sanitize_mcp_name(name)[: (MAX_MCP_SERVER_NAME_LENGTH - 4)]}": server_config}
        }

        server_name = f"lf-{sanitize_mcp_name(name)[: (MAX_MCP_SERVER_NAME_LENGTH - 4)]}"
        await logger.adebug("Installing MCP config for project: %s (server name: %s)", project.name, server_name)

        # Determine the config file path based on the client and OS
        if body.client.lower() == "cursor":
            config_path = Path.home() / ".cursor" / "mcp.json"
        elif body.client.lower() == "windsurf":
            config_path = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
        elif body.client.lower() == "claude":
            if os_type == "Darwin":  # macOS
                config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
            elif os_type == "Windows" or is_wsl:  # Windows or WSL (Claude runs on Windows host)
                if is_wsl:
                    # In WSL, we need to access the Windows APPDATA directory
                    try:
                        # First try to get the Windows username
                        proc = await create_subprocess_exec(
                            "/mnt/c/Windows/System32/cmd.exe",
                            "/c",
                            "echo %USERNAME%",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, stderr = await proc.communicate()

                        if proc.returncode == 0 and stdout.strip():
                            windows_username = stdout.decode().strip()
                            config_path = Path(
                                f"/mnt/c/Users/{windows_username}/AppData/Roaming/Claude/claude_desktop_config.json"
                            )
                        else:
                            # Fallback: try to find the Windows user directory
                            users_dir = Path("/mnt/c/Users")
                            if users_dir.exists():
                                # Get the first non-system user directory
                                user_dirs = [
                                    d
                                    for d in users_dir.iterdir()
                                    if d.is_dir() and not d.name.startswith(("Default", "Public", "All Users"))
                                ]
                                if user_dirs:
                                    config_path = (
                                        user_dirs[0] / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
                                    )
                                else:
                                    raise HTTPException(
                                        status_code=400, detail="Could not find Windows user directory in WSL"
                                    )
                            else:
                                raise HTTPException(
                                    status_code=400, detail="Windows C: drive not mounted at /mnt/c in WSL"
                                )
                    except (OSError, CalledProcessError) as e:
                        await logger.awarning("Failed to determine Windows user path in WSL: %s", str(e))
                        raise HTTPException(
                            status_code=400, detail=f"Could not determine Windows Claude config path in WSL: {e!s}"
                        ) from e
                else:
                    # Regular Windows
                    config_path = Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
            else:
                raise HTTPException(status_code=400, detail="Unsupported operating system for Claude configuration")
        else:
            raise HTTPException(status_code=400, detail="Unsupported client")

        # Create parent directories if they don't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing config if it exists
        existing_config = {}
        if config_path.exists():
            try:
                with config_path.open("r") as f:
                    existing_config = json.load(f)
            except json.JSONDecodeError:
                # If file exists but is invalid JSON, start fresh
                existing_config = {"mcpServers": {}}

        # Ensure mcpServers section exists
        if "mcpServers" not in existing_config:
            existing_config["mcpServers"] = {}

        # Remove any existing servers with the same SSE URL (for reinstalling)
        project_sse_url = await get_project_sse_url(project_id)
        existing_config, removed_servers = remove_server_by_sse_url(existing_config, project_sse_url)

        if removed_servers:
            logger.info("Removed existing MCP servers with same SSE URL for reinstall: %s", removed_servers)

        # Merge new config with existing config
        existing_config["mcpServers"].update(mcp_config["mcpServers"])

        # Write the updated config
        with config_path.open("w") as f:
            json.dump(existing_config, f, indent=2)

    except Exception as e:
        msg = f"Error installing MCP configuration: {e!s}"
        await logger.aexception(msg)
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        action = "reinstalled" if removed_servers else "installed"
        message = f"Successfully {action} MCP configuration for {body.client}"
        if removed_servers:
            message += f" (replaced existing servers: {', '.join(removed_servers)})"
        if generated_api_key:
            auth_type = "API key" if FEATURE_FLAGS.mcp_composer else "legacy API key"
            message += f" with {auth_type} authentication (key name: 'MCP Project {project.name} - {body.client}')"
        await logger.ainfo(message)
        return {"message": message}


@router.get("/{project_id}/installed")
async def check_installed_mcp_servers(
    project_id: UUID,
    current_user: CurrentActiveMCPUser,
):
    """Check if MCP server configuration is installed for this project in Cursor, Windsurf, or Claude."""
    try:
        # Verify project exists and user has access
        async with session_scope() as session:
            project = (
                await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

        # Generate the SSE URL for this project
        project_sse_url = await get_project_sse_url(project_id)

        await logger.adebug(
            "Checking for installed MCP servers for project: %s (SSE URL: %s)", project.name, project_sse_url
        )

        # Check configurations for different clients
        results = []

        # Check Cursor configuration
        cursor_config_path = Path.home() / ".cursor" / "mcp.json"
        await logger.adebug(
            "Checking Cursor config at: %s (exists: %s)", cursor_config_path, cursor_config_path.exists()
        )
        if cursor_config_path.exists():
            try:
                with cursor_config_path.open("r") as f:
                    cursor_config = json.load(f)
                    if config_contains_sse_url(cursor_config, project_sse_url):
                        await logger.adebug("Found Cursor config with matching SSE URL: %s", project_sse_url)
                        results.append("cursor")
                    else:
                        await logger.adebug(
                            "Cursor config exists but no server with SSE URL: %s (available servers: %s)",
                            project_sse_url,
                            list(cursor_config.get("mcpServers", {}).keys()),
                        )
            except json.JSONDecodeError:
                await logger.awarning("Failed to parse Cursor config JSON at: %s", cursor_config_path)

        # Check Windsurf configuration
        windsurf_config_path = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
        await logger.adebug(
            "Checking Windsurf config at: %s (exists: %s)", windsurf_config_path, windsurf_config_path.exists()
        )
        if windsurf_config_path.exists():
            try:
                with windsurf_config_path.open("r") as f:
                    windsurf_config = json.load(f)
                    if config_contains_sse_url(windsurf_config, project_sse_url):
                        await logger.adebug("Found Windsurf config with matching SSE URL: %s", project_sse_url)
                        results.append("windsurf")
                    else:
                        await logger.adebug(
                            "Windsurf config exists but no server with SSE URL: %s (available servers: %s)",
                            project_sse_url,
                            list(windsurf_config.get("mcpServers", {}).keys()),
                        )
            except json.JSONDecodeError:
                await logger.awarning("Failed to parse Windsurf config JSON at: %s", windsurf_config_path)

        # Check Claude configuration
        claude_config_path = None
        os_type = platform.system()
        is_wsl = os_type == "Linux" and "microsoft" in platform.uname().release.lower()

        if os_type == "Darwin":  # macOS
            claude_config_path = (
                Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
            )
        elif os_type == "Windows" or is_wsl:  # Windows or WSL (Claude runs on Windows host)
            if is_wsl:
                # In WSL, we need to access the Windows APPDATA directory
                try:
                    # First try to get the Windows username
                    proc = await create_subprocess_exec(
                        "/mnt/c/Windows/System32/cmd.exe",
                        "/c",
                        "echo %USERNAME%",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await proc.communicate()

                    if proc.returncode == 0 and stdout.strip():
                        windows_username = stdout.decode().strip()
                        claude_config_path = Path(
                            f"/mnt/c/Users/{windows_username}/AppData/Roaming/Claude/claude_desktop_config.json"
                        )
                    else:
                        # Fallback: try to find the Windows user directory
                        users_dir = Path("/mnt/c/Users")
                        if users_dir.exists():
                            # Get the first non-system user directory
                            user_dirs = [
                                d
                                for d in users_dir.iterdir()
                                if d.is_dir() and not d.name.startswith(("Default", "Public", "All Users"))
                            ]
                            if user_dirs:
                                claude_config_path = (
                                    user_dirs[0] / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
                                )
                except (OSError, CalledProcessError) as e:
                    await logger.awarning(
                        "Failed to determine Windows user path in WSL for checking Claude config: %s", str(e)
                    )
                    # Don't set claude_config_path, so it will be skipped
            else:
                # Regular Windows
                claude_config_path = Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"

        if claude_config_path and claude_config_path.exists():
            await logger.adebug("Checking Claude config at: %s", claude_config_path)
            try:
                with claude_config_path.open("r") as f:
                    claude_config = json.load(f)
                    if config_contains_sse_url(claude_config, project_sse_url):
                        await logger.adebug("Found Claude config with matching SSE URL: %s", project_sse_url)
                        results.append("claude")
                    else:
                        await logger.adebug(
                            "Claude config exists but no server with SSE URL: %s (available servers: %s)",
                            project_sse_url,
                            list(claude_config.get("mcpServers", {}).keys()),
                        )
            except json.JSONDecodeError:
                await logger.awarning("Failed to parse Claude config JSON at: %s", claude_config_path)
        else:
            await logger.adebug("Claude config path not found or doesn't exist: %s", claude_config_path)

    except Exception as e:
        msg = f"Error checking MCP configuration: {e!s}"
        await logger.aexception(msg)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return results


def config_contains_sse_url(config_data: dict, sse_url: str) -> bool:
    """Check if any MCP server in the config uses the specified SSE URL."""
    mcp_servers = config_data.get("mcpServers", {})
    for server_name, server_config in mcp_servers.items():
        args = server_config.get("args", [])
        # The SSE URL is typically the last argument in mcp-proxy configurations
        if args and args[-1] == sse_url:
            logger.debug("Found matching SSE URL in server: %s", server_name)
            return True
    return False


async def get_project_sse_url(project_id: UUID) -> str:
    """Generate the SSE URL for a project, including WSL handling."""
    # Get settings service to build the SSE URL
    settings_service = get_settings_service()
    host = getattr(settings_service.settings, "host", "localhost")
    port = getattr(settings_service.settings, "port", 3000)
    base_url = f"http://{host}:{port}".rstrip("/")
    project_sse_url = f"{base_url}/api/v1/mcp/project/{project_id}/sse"

    # Handle WSL case - must match the logic in install function
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
                logger.debug("Using WSL IP for external access: %s", wsl_ip)
                # Replace the localhost with the WSL IP in the URL
                project_sse_url = project_sse_url.replace(f"http://{host}:{port}", f"http://{wsl_ip}:{port}")
        except OSError as e:
            logger.warning("Failed to get WSL IP address: %s. Using default URL.", str(e))

    return project_sse_url


async def get_config_path(client: str) -> Path:
    """Get the configuration file path for a given client and operating system."""
    os_type = platform.system()
    is_wsl = os_type == "Linux" and "microsoft" in platform.uname().release.lower()

    if client.lower() == "cursor":
        return Path.home() / ".cursor" / "mcp.json"
    if client.lower() == "windsurf":
        return Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
    if client.lower() == "claude":
        if os_type == "Darwin":  # macOS
            return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        if os_type == "Windows" or is_wsl:  # Windows or WSL (Claude runs on Windows host)
            if is_wsl:
                # In WSL, we need to access the Windows APPDATA directory
                try:
                    # First try to get the Windows username
                    proc = await create_subprocess_exec(
                        "/mnt/c/Windows/System32/cmd.exe",
                        "/c",
                        "echo %USERNAME%",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await proc.communicate()

                    if proc.returncode == 0 and stdout.strip():
                        windows_username = stdout.decode().strip()
                        return Path(
                            f"/mnt/c/Users/{windows_username}/AppData/Roaming/Claude/claude_desktop_config.json"
                        )

                    # Fallback: try to find the Windows user directory
                    users_dir = Path("/mnt/c/Users")
                    if users_dir.exists():
                        # Get the first non-system user directory
                        user_dirs = [
                            d
                            for d in users_dir.iterdir()
                            if d.is_dir() and not d.name.startswith(("Default", "Public", "All Users"))
                        ]
                        if user_dirs:
                            return user_dirs[0] / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"

                    if not Path("/mnt/c").exists():
                        msg = "Windows C: drive not mounted at /mnt/c in WSL"
                        raise ValueError(msg)

                    msg = "Could not find valid Windows user directory in WSL"
                    raise ValueError(msg)
                except (OSError, CalledProcessError) as e:
                    logger.warning("Failed to determine Windows user path in WSL: %s", str(e))
                    msg = f"Could not determine Windows Claude config path in WSL: {e!s}"
                    raise ValueError(msg) from e
            # Regular Windows
            return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"

        msg = "Unsupported operating system for Claude configuration"
        raise ValueError(msg)

    msg = "Unsupported client"
    raise ValueError(msg)


def remove_server_by_sse_url(config_data: dict, sse_url: str) -> tuple[dict, list[str]]:
    """Remove any MCP servers that use the specified SSE URL from config data.

    Returns:
        tuple: (updated_config, list_of_removed_server_names)
    """
    if "mcpServers" not in config_data:
        return config_data, []

    removed_servers: list[str] = []
    servers_to_remove: list[str] = []

    # Find servers to remove
    for server_name, server_config in config_data["mcpServers"].items():
        args = server_config.get("args", [])
        if args and args[-1] == sse_url:
            servers_to_remove.append(server_name)

    # Remove the servers
    for server_name in servers_to_remove:
        del config_data["mcpServers"][server_name]
        removed_servers.append(server_name)
        logger.debug("Removed existing server with matching SSE URL: %s", server_name)

    return config_data, removed_servers


# Project-specific MCP server instance for handling project-specific tools
class ProjectMCPServer:
    def __init__(self, project_id: UUID):
        self.project_id = project_id
        self.server = Server(f"langflow-mcp-project-{project_id}")

        # Register handlers that filter by project
        @self.server.list_tools()
        @handle_mcp_errors
        async def handle_list_project_tools():
            """Handle listing tools for this specific project."""
            return await handle_list_tools(project_id=self.project_id, mcp_enabled_only=True)

        @self.server.list_prompts()
        async def handle_list_prompts():
            return []

        @self.server.list_resources()
        async def handle_list_project_resources():
            """Handle listing resources for this specific project."""
            return await handle_list_resources(project_id=self.project_id)

        @self.server.read_resource()
        async def handle_read_project_resource(uri: str) -> bytes:
            """Handle resource read requests for this specific project."""
            return await handle_read_resource(uri=uri)

        @self.server.call_tool()
        @handle_mcp_errors
        async def handle_call_project_tool(name: str, arguments: dict) -> list[types.TextContent]:
            """Handle tool execution requests for this specific project."""
            return await handle_call_tool(
                name=name,
                arguments=arguments,
                server=self.server,
                project_id=self.project_id,
                is_action=True,
            )


# Cache of project MCP servers
project_mcp_servers = {}


def get_project_mcp_server(project_id: UUID) -> ProjectMCPServer:
    """Get or create an MCP server for a specific project."""
    project_id_str = str(project_id)
    if project_id_str not in project_mcp_servers:
        project_mcp_servers[project_id_str] = ProjectMCPServer(project_id)
    return project_mcp_servers[project_id_str]


async def init_mcp_servers():
    """Initialize MCP servers for all projects."""
    try:
        async with session_scope() as session:
            projects = (await session.exec(select(Folder))).all()

            for project in projects:
                try:
                    get_project_sse(project.id)
                    get_project_mcp_server(project.id)
                except Exception as e:  # noqa: BLE001
                    msg = f"Failed to initialize MCP server for project {project.id}: {e}"
                    await logger.aexception(msg)
                    # Continue to next project even if this one fails

    except Exception as e:  # noqa: BLE001
        msg = f"Failed to initialize MCP servers: {e}"
        await logger.aexception(msg)
