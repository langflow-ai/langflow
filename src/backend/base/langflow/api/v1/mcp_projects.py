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
from typing import Annotated, Any, cast
from uuid import UUID

from anyio import BrokenResourceError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from lfx.base.mcp.constants import MAX_MCP_SERVER_NAME_LENGTH
from lfx.base.mcp.util import sanitize_mcp_name
from lfx.log import logger
from lfx.services.deps import get_settings_service, session_scope
from lfx.services.mcp_composer.service import MCPComposerError, MCPComposerService
from lfx.services.schema import ServiceType
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveMCPUser, extract_global_variables_from_headers
from langflow.api.utils.mcp import auto_configure_starter_projects_mcp, get_project_sse_url, get_url_by_os
from langflow.api.v1.auth_helpers import handle_auth_settings_update
from langflow.api.v1.mcp_utils import (
    current_request_variables_ctx,
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
from langflow.services.auth.utils import AUTO_LOGIN_WARNING
from langflow.services.database.models import Flow, Folder
from langflow.services.database.models.api_key.crud import check_key, create_api_key
from langflow.services.database.models.api_key.model import ApiKey, ApiKeyCreate
from langflow.services.database.models.user.crud import get_user_by_username
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_service

# Constants
ALL_INTERFACES_HOST = "0.0.0.0"  # noqa: S104

router = APIRouter(prefix="/mcp/project", tags=["mcp_projects"])


async def verify_project_auth(
    db: AsyncSession,
    project_id: UUID,
    query_param: str,
    header_param: str,
) -> User:
    """MCP-specific user authentication that allows fallback to username lookup when not using API key auth.

    This function provides authentication for MCP endpoints when using MCP Composer and no API key is provided,
    or checks if the API key is valid.
    """
    settings_service = get_settings_service()
    result: ApiKey | User | None

    project = (await db.exec(select(Folder).where(Folder.id == project_id))).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    auth_settings: AuthSettings | None = None
    # Check if this project requires API key only authentication
    if project.auth_settings:
        auth_settings = AuthSettings(**project.auth_settings)

    if (not auth_settings and not settings_service.auth_settings.AUTO_LOGIN) or (
        auth_settings and auth_settings.auth_type == "apikey"
    ):
        api_key = query_param or header_param
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="API key required for this project. Provide x-api-key header or query parameter.",
            )

        # Validate the API key
        user = await check_key(db, api_key)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Verify user has access to the project
        project_access = (
            await db.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == user.id))
        ).first()

        if not project_access:
            raise HTTPException(status_code=404, detail="Project not found")

        return user

    # Get the first user
    if not settings_service.auth_settings.SUPERUSER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing superuser username in auth settings",
        )
    # For MCP endpoints, always fall back to username lookup when no API key is provided
    result = await get_user_by_username(db, settings_service.auth_settings.SUPERUSER)
    if result:
        await logger.awarning(AUTO_LOGIN_WARNING)
        return result
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid user",
    )


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

        # Extract token
        token: str | None = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

        # Extract API keys
        api_key_query_value = request.query_params.get("x-api-key")
        api_key_header_value = request.headers.get("x-api-key")

        # Check if this project requires API key only authentication
        if get_settings_service().settings.mcp_composer_enabled:
            return await verify_project_auth(session, project_id, api_key_query_value, api_key_header_value)

        # For all other cases, use standard MCP authentication (allows JWT + API keys)
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


def get_project_sse(project_id: UUID | None) -> SseServerTransport:
    """Get or create an SSE transport for a specific project."""
    if not project_id:
        raise HTTPException(status_code=400, detail="Project ID is required to start MCP server")

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
) -> MCPProjectResponse | None:
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

            # Get project-level auth settings but mask sensitive fields for security
            auth_settings = None
            if project.auth_settings:
                # Decrypt to get the settings structure
                decrypted_settings = decrypt_auth_settings(project.auth_settings)
                if decrypted_settings:
                    # Mask sensitive fields before sending to frontend
                    masked_settings = decrypted_settings.copy()
                    if masked_settings.get("oauth_client_secret"):
                        masked_settings["oauth_client_secret"] = "*******"  # noqa: S105
                    if masked_settings.get("api_key"):
                        masked_settings["api_key"] = "*******"
                    auth_settings = AuthSettings(**masked_settings)

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
    # Extract request-level variables from headers with prefix X-LANGFLOW-GLOBAL-VAR-*
    variables = extract_global_variables_from_headers(request.headers)
    req_vars_token = current_request_variables_ctx.set(variables or None)

    try:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:  # noqa: SLF001
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
        current_request_variables_ctx.reset(req_vars_token)

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
    # Extract request-level variables from headers with prefix X-LANGFLOW-GLOBAL-VAR-*
    variables = extract_global_variables_from_headers(request.headers)
    req_vars_token = current_request_variables_ctx.set(variables or None)

    try:
        sse = get_project_sse(project_id)
        await sse.handle_post_message(request.scope, request.receive, request._send)  # noqa: SLF001
    except BrokenResourceError as e:
        await logger.ainfo("Project MCP Server disconnected for project %s", project_id)
        raise HTTPException(status_code=404, detail=f"Project MCP Server disconnected, error: {e}") from e
    finally:
        current_user_ctx.reset(user_token)
        current_project_ctx.reset(project_token)
        current_request_variables_ctx.reset(req_vars_token)


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
    """Update the MCP settings of all flows in a project and project-level auth settings.

    On MCP Composer failure, this endpoint should return with a 200 status code and an error message in
    the body of the response to display to the user.
    """
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

            # Track if MCP Composer needs to be started or stopped
            should_handle_mcp_composer = False
            should_start_composer = False
            should_stop_composer = False

            # Update project-level auth settings with encryption
            if "auth_settings" in request.model_fields_set and request.auth_settings is not None:
                auth_result = handle_auth_settings_update(
                    existing_project=project,
                    new_auth_settings=request.auth_settings,
                )

                should_handle_mcp_composer = auth_result["should_handle_composer"]
                should_start_composer = auth_result["should_start_composer"]
                should_stop_composer = auth_result["should_stop_composer"]

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

            response: dict[str, Any] = {
                "message": f"Updated MCP settings for {len(updated_flows)} flows and project auth settings"
            }

            if should_handle_mcp_composer:
                if should_start_composer:
                    await logger.adebug(
                        f"Auth settings changed to OAuth for project {project.name} ({project_id}), "
                        "starting MCP Composer"
                    )

                    if should_use_mcp_composer(project):
                        try:
                            auth_config = await _get_mcp_composer_auth_config(project)
                            await get_or_start_mcp_composer(auth_config, project.name, project_id)
                            composer_sse_url = await get_composer_sse_url(project)
                            response["result"] = {
                                "project_id": str(project_id),
                                "sse_url": composer_sse_url,
                                "uses_composer": True,
                            }
                        except MCPComposerError as e:
                            response["result"] = {
                                "project_id": str(project_id),
                                "uses_composer": True,
                                "error_message": e.message,
                            }
                        except Exception as e:
                            # Unexpected errors
                            await logger.aerror(f"Failed to get mcp composer URL for project {project_id}: {e}")
                            raise HTTPException(status_code=500, detail=str(e)) from e
                    else:
                        # This shouldn't happen - we determined we should start composer but now we can't use it
                        await logger.aerror(
                            f"PATCH: OAuth set but MCP Composer is disabled in settings for project {project_id}"
                        )
                        response["result"] = {
                            "project_id": str(project_id),
                            "uses_composer": False,
                            "error_message": "OAuth authentication is set but MCP Composer is disabled in settings",
                        }
                elif should_stop_composer:
                    await logger.adebug(
                        f"Auth settings changed from OAuth for project {project.name} ({project_id}), "
                        "stopping MCP Composer"
                    )
                    mcp_composer_service: MCPComposerService = cast(
                        "MCPComposerService", get_service(ServiceType.MCP_COMPOSER_SERVICE)
                    )
                    await mcp_composer_service.stop_project_composer(str(project_id))

                    # Provide the direct SSE URL since we're no longer using composer
                    sse_url = await get_project_sse_url(project_id)
                    if not sse_url:
                        raise HTTPException(status_code=500, detail="Failed to get direct SSE URL")

                    response["result"] = {
                        "project_id": str(project_id),
                        "sse_url": sse_url,
                        "uses_composer": False,
                    }

            return response

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
    if ip_str == ALL_INTERFACES_HOST:
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
        project = await verify_project_access(project_id, current_user)

        # Check if project requires API key authentication and generate if needed
        generated_api_key = None

        # Determine if we need to generate an API key
        should_generate_api_key = False
        if not get_settings_service().settings.mcp_composer_enabled:
            # When MCP_COMPOSER is disabled, check auth settings or fallback to auto_login setting
            settings_service = get_settings_service()
            if project.auth_settings:
                # Project has auth settings - check if it requires API key
                if project.auth_settings.get("auth_type") == "apikey":
                    should_generate_api_key = True
            elif not settings_service.auth_settings.AUTO_LOGIN:
                # No project auth settings but auto_login is disabled - generate API key
                should_generate_api_key = True
        elif project.auth_settings:
            # When MCP_COMPOSER is enabled, only generate if auth_type is "apikey"
            if project.auth_settings.get("auth_type") == "apikey":
                should_generate_api_key = True

        # Get settings service to build the SSE URL
        settings_service = get_settings_service()
        settings = settings_service.settings
        host = settings.host or None
        port = settings.port or None
        if not host or not port:
            raise HTTPException(status_code=500, detail="Host and port are not set in settings")

        # Determine command and args based on operating system
        os_type = platform.system()

        use_mcp_composer = should_use_mcp_composer(project)

        if use_mcp_composer:
            try:
                auth_config = await _get_mcp_composer_auth_config(project)
                await get_or_start_mcp_composer(auth_config, project.name, project_id)
                sse_url = await get_composer_sse_url(project)
            except MCPComposerError as e:
                await logger.aerror(
                    f"Failed to start MCP Composer for project '{project.name}' ({project_id}): {e.message}"
                )
                raise HTTPException(status_code=500, detail=e.message) from e
            except Exception as e:
                error_msg = f"Failed to start MCP Composer for project '{project.name}' ({project_id}): {e!s}"
                await logger.aerror(error_msg)
                error_detail = "Failed to start MCP Composer. See logs for details."
                raise HTTPException(status_code=500, detail=error_detail) from e

            # For OAuth/MCP Composer, use the special format
            settings = get_settings_service().settings
            command = "uvx"
            args = [
                f"mcp-composer{settings.mcp_composer_version}",
                "--mode",
                "stdio",
                "--sse-url",
                sse_url,
                "--disable-composer-tools",
                "--client_auth_type",
                "oauth",
            ]
        else:
            # For non-OAuth (API key or no auth), use mcp-proxy
            sse_url = await get_project_sse_url(project_id)
            command = "uvx"
            args = ["mcp-proxy"]
            # Check if we need to add Langflow API key headers
            # Necessary only when Project API Key Authentication is enabled

            # Generate a Langflow API key for auto-install if needed
            # Only add API key headers for projects with "apikey" auth type (not "none" or OAuth)

            if should_generate_api_key:
                async with session_scope() as api_key_session:
                    api_key_create = ApiKeyCreate(name=f"MCP Server {project.name}")
                    api_key_response = await create_api_key(api_key_session, api_key_create, current_user.id)
                    langflow_api_key = api_key_response.api_key
                    args.extend(["--headers", "x-api-key", langflow_api_key])

            # Add the SSE URL for mcp-proxy
            args.append(sse_url)

        if os_type == "Windows" and not use_mcp_composer:
            # Only wrap in cmd for Windows when using mcp-proxy
            command = "cmd"
            args = ["/c", "uvx", *args]
            await logger.adebug("Windows detected, using cmd command")

        name = project.name
        server_name = f"lf-{sanitize_mcp_name(name)[: (MAX_MCP_SERVER_NAME_LENGTH - 4)]}"

        # Create the MCP configuration
        server_config: dict[str, Any] = {
            "command": command,
            "args": args,
        }

        mcp_config = {"mcpServers": {server_name: server_config}}

        await logger.adebug("Installing MCP config for project: %s (server name: %s)", project.name, server_name)

        # Get the config file path and check if client is available
        try:
            config_path = await get_config_path(body.client.lower())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        # Check if the client application is available (config directory exists)
        if not config_path.parent.exists():
            raise HTTPException(
                status_code=400,
                detail=f"{body.client.capitalize()} is not installed on this system. "
                f"Please install {body.client.capitalize()} first.",
            )

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

        existing_config, removed_servers = remove_server_by_sse_url(existing_config, sse_url)

        if removed_servers:
            await logger.adebug("Removed existing MCP servers with same SSE URL for reinstall: %s", removed_servers)

        # Merge new config with existing config
        existing_config["mcpServers"].update(mcp_config["mcpServers"])

        # Write the updated config
        with config_path.open("w") as f:
            json.dump(existing_config, f, indent=2)

    except HTTPException:
        raise
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
            auth_type = "API key" if get_settings_service().settings.mcp_composer_enabled else "legacy API key"
            message += f" with {auth_type} authentication (key name: 'MCP Project {project.name} - {body.client}')"
        await logger.adebug(message)
        return {"message": message}


@router.get("/{project_id}/composer-url")
async def get_project_composer_url(
    project_id: UUID,
    current_user: CurrentActiveMCPUser,
):
    """Get the MCP Composer URL for a specific project.

    On failure, this endpoint should return with a 200 status code and an error message in
    the body of the response to display to the user.
    """
    try:
        project = await verify_project_access(project_id, current_user)
        if not should_use_mcp_composer(project):
            return {
                "project_id": str(project_id),
                "uses_composer": False,
                "error_message": (
                    "MCP Composer is only available for projects with MCP Composer enabled and OAuth authentication"
                ),
            }

        auth_config = await _get_mcp_composer_auth_config(project)

        try:
            await get_or_start_mcp_composer(auth_config, project.name, project_id)
            composer_sse_url = await get_composer_sse_url(project)
            return {"project_id": str(project_id), "sse_url": composer_sse_url, "uses_composer": True}
        except MCPComposerError as e:
            return {"project_id": str(project_id), "uses_composer": True, "error_message": e.message}
        except Exception as e:  # noqa: BLE001
            await logger.aerror(f"Unexpected error getting composer URL: {e}")
            return {
                "project_id": str(project_id),
                "uses_composer": True,
                "error_message": "Failed to start MCP Composer. See logs for details.",
            }

    except Exception as e:  # noqa: BLE001
        msg = f"Error getting composer URL for project {project_id}: {e!s}"
        await logger.aerror(msg)
        return {
            "project_id": str(project_id),
            "uses_composer": True,
            "error_message": "Failed to get MCP Composer URL. See logs for details.",
        }


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

        project = await verify_project_access(project_id, current_user)
        if should_use_mcp_composer(project):
            project_sse_url = await get_composer_sse_url(project)
        else:
            project_sse_url = await get_project_sse_url(project_id)

        await logger.adebug(
            "Checking for installed MCP servers for project: %s (SSE URL: %s)", project.name, project_sse_url
        )

        # Define supported clients
        clients = ["cursor", "windsurf", "claude"]
        results = []

        for client_name in clients:
            try:
                # Get config path for this client
                config_path = await get_config_path(client_name)
                available = config_path.parent.exists()
                installed = False

                await logger.adebug("Checking %s config at: %s (exists: %s)", client_name, config_path, available)

                # If config file exists, check if project is installed
                if available:
                    try:
                        with config_path.open("r") as f:
                            config_data = json.load(f)
                            if config_contains_sse_url(config_data, project_sse_url):
                                await logger.adebug(
                                    "Found %s config with matching SSE URL: %s", client_name, project_sse_url
                                )
                                installed = True
                            else:
                                await logger.adebug(
                                    "%s config exists but no server with SSE URL: %s (available servers: %s)",
                                    client_name,
                                    project_sse_url,
                                    list(config_data.get("mcpServers", {}).keys()),
                                )
                    except json.JSONDecodeError:
                        await logger.awarning("Failed to parse %s config JSON at: %s", client_name, config_path)
                        # available is True but installed remains False due to parse error
                else:
                    await logger.adebug("%s config path not found or doesn't exist: %s", client_name, config_path)

                # Add result for this client
                results.append({"name": client_name, "installed": installed, "available": available})

            except Exception as e:  # noqa: BLE001
                # If there's an error getting config path or checking the client,
                # mark it as not available and not installed
                await logger.awarning("Error checking %s configuration: %s", client_name, str(e))
                results.append({"name": client_name, "installed": False, "available": False})

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
        if args and sse_url in args:
            logger.debug("Found matching SSE URL in server: %s", server_name)
            return True
    return False


async def get_composer_sse_url(project: Folder) -> str:
    """Get the SSE URL for a project using MCP Composer."""
    auth_config = await _get_mcp_composer_auth_config(project)
    composer_host = auth_config.get("oauth_host")
    composer_port = auth_config.get("oauth_port")
    if not composer_host or not composer_port:
        error_msg = "OAuth host and port are required to get the SSE URL for MCP Composer"
        raise ValueError(error_msg)

    composer_sse_url = f"http://{composer_host}:{composer_port}/sse"
    return await get_url_by_os(composer_host, composer_port, composer_sse_url)


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
                    stdout, _stderr = await proc.communicate()

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
                    await logger.awarning("Failed to determine Windows user path in WSL: %s", str(e))
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


async def _get_mcp_composer_auth_config(project) -> dict:
    """Get MCP Composer authentication configuration from project settings.

    Args:
        project: The project object containing auth_settings

    Returns:
        dict: The decrypted authentication configuration

    Raises:
        HTTPException: If MCP Composer is not enabled or auth config is missing
    """
    auth_config = None
    if project.auth_settings:
        decrypted_settings = decrypt_auth_settings(project.auth_settings)
        if decrypted_settings:
            auth_config = decrypted_settings

    if not auth_config:
        error_message = "Auth config is missing. Please check your settings and try again."
        raise ValueError(error_message)

    return auth_config


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


def get_project_mcp_server(project_id: UUID | None) -> ProjectMCPServer:
    """Get or create an MCP server for a specific project."""
    if project_id is None:
        error_message = "Project ID cannot be None when getting project MCP server"
        raise ValueError(error_message)

    project_id_str = str(project_id)
    if project_id_str not in project_mcp_servers:
        project_mcp_servers[project_id_str] = ProjectMCPServer(project_id)
    return project_mcp_servers[project_id_str]


async def register_project_with_composer(project: Folder):
    """Register a project with MCP Composer by starting a dedicated composer instance."""
    try:
        mcp_composer_service: MCPComposerService = cast(
            "MCPComposerService", get_service(ServiceType.MCP_COMPOSER_SERVICE)
        )

        settings = get_settings_service().settings
        if not settings.host or not settings.port:
            error_msg = "Langflow host and port must be set in settings to register project with MCP Composer"
            raise ValueError(error_msg)

        if not project.id:
            error_msg = "Project must have an ID to register with MCP Composer"
            raise ValueError(error_msg)

        sse_url = await get_project_sse_url(project.id)
        auth_config = await _get_mcp_composer_auth_config(project)

        error_message = await mcp_composer_service.start_project_composer(
            project_id=str(project.id),
            sse_url=sse_url,
            auth_config=auth_config,
        )
        if error_message is not None:
            raise RuntimeError(error_message)

        await logger.adebug(f"Registered project {project.name} ({project.id}) with MCP Composer")

    except Exception as e:  # noqa: BLE001
        await logger.awarning(f"Failed to register project {project.id} with MCP Composer: {e}")


async def init_mcp_servers():
    """Initialize MCP servers for all projects."""
    try:
        settings_service = get_settings_service()

        async with session_scope() as session:
            projects = (await session.exec(select(Folder))).all()

            for project in projects:
                try:
                    # Auto-enable API key auth for projects without auth settings or with "none" auth
                    # when AUTO_LOGIN is false
                    if not settings_service.auth_settings.AUTO_LOGIN:
                        should_update_to_apikey = False

                        if not project.auth_settings:
                            # No auth settings at all
                            should_update_to_apikey = True
                        # Check if existing auth settings have auth_type "none"
                        elif project.auth_settings.get("auth_type") == "none":
                            should_update_to_apikey = True

                        if should_update_to_apikey:
                            default_auth = {"auth_type": "apikey"}
                            project.auth_settings = encrypt_auth_settings(default_auth)
                            session.add(project)
                            await logger.ainfo(
                                f"Auto-enabled API key authentication for existing project {project.name} "
                                f"({project.id}) due to AUTO_LOGIN=false"
                            )

                    # WARN: If oauth projects exist in the database and the MCP Composer is disabled,
                    # these projects will be reset to "apikey" or "none" authentication, erasing all oauth settings.
                    if (
                        not settings_service.settings.mcp_composer_enabled
                        and project.auth_settings
                        and project.auth_settings.get("auth_type") == "oauth"
                    ):
                        # Reset OAuth projects to appropriate auth type based on AUTO_LOGIN setting
                        fallback_auth_type = "apikey" if not settings_service.auth_settings.AUTO_LOGIN else "none"
                        clean_auth = AuthSettings(auth_type=fallback_auth_type)
                        project.auth_settings = clean_auth.model_dump(exclude_none=True)
                        session.add(project)
                        await logger.adebug(
                            f"Updated OAuth project {project.name} ({project.id}) to use {fallback_auth_type} "
                            f"authentication because MCP Composer is disabled"
                        )

                    get_project_sse(project.id)
                    get_project_mcp_server(project.id)
                    await logger.adebug(f"Initialized MCP server for project: {project.name} ({project.id})")

                    # Only register with MCP Composer if OAuth authentication is configured
                    if get_settings_service().settings.mcp_composer_enabled and project.auth_settings:
                        auth_type = project.auth_settings.get("auth_type")
                        if auth_type == "oauth":
                            await logger.adebug(
                                f"Starting MCP Composer for OAuth project {project.name} ({project.id}) on startup"
                            )
                            await register_project_with_composer(project)

                except Exception as e:  # noqa: BLE001
                    msg = f"Failed to initialize MCP server for project {project.id}: {e}"
                    await logger.aexception(msg)
                    # Continue to next project even if this one fails

            # Auto-configure starter projects with MCP server settings if enabled
            await auto_configure_starter_projects_mcp(session)
            # Commit any auth settings updates
            await session.commit()

    except Exception as e:  # noqa: BLE001
        msg = f"Failed to initialize MCP servers: {e}"
        await logger.aexception(msg)


async def verify_project_access(project_id: UUID, current_user: CurrentActiveMCPUser) -> Folder:
    """Verify project exists and user has access."""
    async with session_scope() as session:
        project = (
            await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return project


def should_use_mcp_composer(project: Folder) -> bool:
    """Check if project uses OAuth authentication and MCP Composer is enabled."""
    # If MCP Composer is disabled globally, never use it regardless of project settings
    if not get_settings_service().settings.mcp_composer_enabled:
        return False

    return project.auth_settings is not None and project.auth_settings.get("auth_type", "") == "oauth"


async def get_or_start_mcp_composer(auth_config: dict, project_name: str, project_id: UUID) -> None:
    """Get MCP Composer or start it if not running.

    Raises:
        MCPComposerError: If MCP Composer fails to start
    """
    from lfx.services.mcp_composer.service import MCPComposerConfigError

    mcp_composer_service: MCPComposerService = cast("MCPComposerService", get_service(ServiceType.MCP_COMPOSER_SERVICE))

    # Prepare current auth config for comparison
    settings = get_settings_service().settings
    if not settings.host or not settings.port:
        error_msg = "Langflow host and port must be set in settings to register project with MCP Composer"
        raise ValueError(error_msg)

    sse_url = await get_project_sse_url(project_id)
    if not auth_config:
        error_msg = f"Auth config is required to start MCP Composer for project {project_name}"
        raise MCPComposerConfigError(error_msg, str(project_id))

    await mcp_composer_service.start_project_composer(str(project_id), sse_url, auth_config)
