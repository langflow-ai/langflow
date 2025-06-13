import asyncio
import base64
import json
import logging
import os
import platform
from asyncio.subprocess import create_subprocess_exec
from contextvars import ContextVar
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated
from urllib.parse import quote, unquote, urlparse
from uuid import UUID, uuid4

from anyio import BrokenResourceError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport
from sqlalchemy.orm import selectinload
from sqlmodel import select

from langflow.api.v1.endpoints import simple_run_flow
from langflow.api.v1.mcp import (
    current_user_ctx,
    get_mcp_config,
    handle_mcp_errors,
    with_db_session,
)
from langflow.api.v1.schemas import MCPInstallRequest, MCPSettings, SimplifiedAPIRequest
from langflow.base.mcp.constants import MAX_MCP_SERVER_NAME_LENGTH, MAX_MCP_TOOL_NAME_LENGTH
from langflow.base.mcp.util import get_flow_snake_case, get_unique_name
from langflow.helpers.flow import json_schema_from_flow
from langflow.schema.message import Message
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models import Flow, Folder, User
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME, NEW_FOLDER_NAME
from langflow.services.deps import get_settings_service, get_storage_service, session_scope
from langflow.services.storage.utils import build_content_type_from_extension

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp/project", tags=["mcp_projects"])

# Create a context variable to store the current project
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
    current_user: Annotated[User, Depends(get_current_active_user)],
    *,
    mcp_enabled: bool = True,
) -> list[MCPSettings]:
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
                flow_name = "_".join(flow.name.lower().split())

                # Use action_name and action_description if available, otherwise use defaults
                name = flow.action_name or flow_name
                description = flow.action_description or (
                    flow.description if flow.description else f"Tool generated from flow: {flow_name}"
                )
                try:
                    tool = MCPSettings(
                        id=str(flow.id),
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
                    logger.warning(msg)
                    continue

    except Exception as e:
        msg = f"Error listing project tools: {e!s}"
        logger.exception(msg)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return tools


@router.head("/{project_id}/sse", response_class=HTMLResponse, include_in_schema=False)
async def im_alive():
    return Response()


@router.get("/{project_id}/sse", response_class=HTMLResponse)
async def handle_project_sse(
    project_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
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
    logger.debug("Project MCP server name: %s", project_server.server.name)

    # Set context variables
    user_token = current_user_ctx.set(current_user)
    project_token = current_project_ctx.set(project_id)

    try:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            try:
                logger.debug("Starting SSE connection for project %s", project_id)

                notification_options = NotificationOptions(
                    prompts_changed=True, resources_changed=True, tools_changed=True
                )
                init_options = project_server.server.create_initialization_options(notification_options)

                try:
                    await project_server.server.run(streams[0], streams[1], init_options)
                except Exception:
                    logger.exception("Error in project MCP")
            except BrokenResourceError:
                logger.info("Client disconnected from project SSE connection")
            except asyncio.CancelledError:
                logger.info("Project SSE connection was cancelled")
                raise
            except Exception:
                logger.exception("Error in project MCP")
                raise
    finally:
        current_user_ctx.reset(user_token)
        current_project_ctx.reset(project_token)

    return Response(status_code=200)


@router.post("/{project_id}")
async def handle_project_messages(
    project_id: UUID, request: Request, current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Handle POST messages for a project-specific MCP server."""
    # Verify project exists and user has access
    async with session_scope() as session:
        project = (
            await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    # Set context variables
    user_token = current_user_ctx.set(current_user)
    project_token = current_project_ctx.set(project_id)

    try:
        sse = get_project_sse(project_id)
        await sse.handle_post_message(request.scope, request.receive, request._send)
    except BrokenResourceError as e:
        logger.info("Project MCP Server disconnected for project %s", project_id)
        raise HTTPException(status_code=404, detail=f"Project MCP Server disconnected, error: {e}") from e
    finally:
        current_user_ctx.reset(user_token)
        current_project_ctx.reset(project_token)


@router.post("/{project_id}/")
async def handle_project_messages_with_slash(
    project_id: UUID, request: Request, current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Handle POST messages for a project-specific MCP server with trailing slash."""
    # Call the original handler
    return await handle_project_messages(project_id, request, current_user)


@router.patch("/{project_id}", status_code=200)
async def update_project_mcp_settings(
    project_id: UUID,
    settings: list[MCPSettings],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Update the MCP settings of all flows in a project."""
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
            flows = (await session.exec(select(Flow).where(Flow.folder_id == project_id))).all()
            flows_to_update = {x.id: x for x in settings}

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

            return {"message": f"Updated MCP settings for {len(updated_flows)} flows"}

    except Exception as e:
        msg = f"Error updating project MCP settings: {e!s}"
        logger.exception(msg)
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
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Install MCP server configuration for Cursor or Claude."""
    # Check if the request is coming from a local IP address
    client_ip = get_client_ip(request)
    if not is_local_ip(client_ip):
        raise HTTPException(status_code=500, detail="MCP configuration can only be installed from a local connection")

    try:
        # Verify project exists and user has access
        async with session_scope() as session:
            project = (
                await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

        # Get settings service to build the SSE URL
        settings_service = get_settings_service()
        host = getattr(settings_service.settings, "host", "localhost")
        port = getattr(settings_service.settings, "port", 3000)
        base_url = f"http://{host}:{port}".rstrip("/")
        sse_url = f"{base_url}/api/v1/mcp/project/{project_id}/sse"

        # Determine command and args based on operating system
        os_type = platform.system()
        command = "uvx"
        args = ["mcp-proxy", sse_url]

        # Check if running on WSL (will appear as Linux but with Microsoft in release info)
        if os_type == "Linux" and "microsoft" in platform.uname().release.lower():
            logger.debug("WSL detected, using Windows-specific configuration")

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
                    stdout, stderr = await proc.communicate()

                    if proc.returncode == 0 and stdout.strip():
                        wsl_ip = stdout.decode().strip().split()[0]  # Get first IP address
                        logger.debug("Using WSL IP for external access: %s", wsl_ip)
                        # Replace the localhost with the WSL IP in the URL
                        sse_url = sse_url.replace(f"http://{host}:{port}", f"http://{wsl_ip}:{port}")
                except OSError as e:
                    logger.warning("Failed to get WSL IP address: %s. Using default URL.", str(e))

        if os_type == "Windows":
            command = "cmd"
            args = ["/c", "uvx", "mcp-proxy", sse_url]
            logger.debug("Windows detected, using cmd command")

        name = project.name
        name = NEW_FOLDER_NAME if name == DEFAULT_FOLDER_NAME else name

        # Create the MCP configuration
        mcp_config = {
            "mcpServers": {
                f"lf-{name.lower().replace(' ', '_')[: (MAX_MCP_SERVER_NAME_LENGTH - 4)]}": {
                    "command": command,
                    "args": args,
                }
            }
        }

        # Determine the config file path based on the client and OS
        if body.client.lower() == "cursor":
            config_path = Path.home() / ".cursor" / "mcp.json"
        elif body.client.lower() == "claude":
            if os_type == "Darwin":  # macOS
                config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
            elif os_type == "Windows":
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

        # Merge new config with existing config
        if "mcpServers" not in existing_config:
            existing_config["mcpServers"] = {}
        existing_config["mcpServers"].update(mcp_config["mcpServers"])

        # Write the updated config
        with config_path.open("w") as f:
            json.dump(existing_config, f, indent=2)

    except Exception as e:
        msg = f"Error installing MCP configuration: {e!s}"
        logger.exception(msg)
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        message = f"Successfully installed MCP configuration for {body.client}"
        logger.info(message)
        return {"message": message}


@router.get("/{project_id}/installed")
async def check_installed_mcp_servers(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Check if MCP server configuration is installed for this project in Cursor or Claude."""
    try:
        # Verify project exists and user has access
        async with session_scope() as session:
            project = (
                await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

        # Project server name pattern
        project_server_name = f"lf-{project.name.lower().replace(' ', '_')[: (MAX_MCP_SERVER_NAME_LENGTH - 4)]}"

        # Check configurations for different clients
        results = []

        # Check Cursor configuration
        cursor_config_path = Path.home() / ".cursor" / "mcp.json"
        if cursor_config_path.exists():
            try:
                with cursor_config_path.open("r") as f:
                    cursor_config = json.load(f)
                    if "mcpServers" in cursor_config and project_server_name in cursor_config["mcpServers"]:
                        results.append("cursor")
            except json.JSONDecodeError:
                pass

        # Check Claude configuration
        claude_config_path = None
        if platform.system() == "Darwin":  # macOS
            claude_config_path = (
                Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
            )
        elif platform.system() == "Windows":
            claude_config_path = Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"

        if claude_config_path and claude_config_path.exists():
            try:
                with claude_config_path.open("r") as f:
                    claude_config = json.load(f)
                    if "mcpServers" in claude_config and project_server_name in claude_config["mcpServers"]:
                        results.append("claude")
            except json.JSONDecodeError:
                pass

    except Exception as e:
        msg = f"Error checking MCP configuration: {e!s}"
        logger.exception(msg)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return results


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
            tools = []
            try:
                async with session_scope() as session:
                    # Get flows with mcp_enabled flag set to True and in this project
                    flows = (
                        await session.exec(
                            select(Flow).where(Flow.mcp_enabled == True, Flow.folder_id == self.project_id)  # noqa: E712
                        )
                    ).all()
                    existing_names = set()
                    for flow in flows:
                        if flow.user_id is None:
                            continue

                        # Use action_name if available, otherwise construct from flow name
                        base_name = flow.action_name or "_".join(flow.name.lower().split())
                        name = get_unique_name(base_name, MAX_MCP_TOOL_NAME_LENGTH, existing_names)

                        # Use action_description if available, otherwise use defaults
                        description = flow.action_description or (
                            flow.description if flow.description else f"Tool generated from flow: {name}"
                        )

                        tool = types.Tool(
                            name=name,
                            description=description,
                            inputSchema=json_schema_from_flow(flow),
                        )
                        tools.append(tool)
                        existing_names.add(name)
            except Exception as e:  # noqa: BLE001
                msg = f"Error in listing project tools: {e!s} from flow: {name}"
                logger.warning(msg)
            return tools

        @self.server.list_prompts()
        async def handle_list_prompts():
            return []

        @self.server.list_resources()
        async def handle_list_resources():
            resources = []
            try:
                storage_service = get_storage_service()
                settings_service = get_settings_service()

                # Build full URL from settings
                host = getattr(settings_service.settings, "host", "localhost")
                port = getattr(settings_service.settings, "port", 3000)

                base_url = f"http://{host}:{port}".rstrip("/")

                async with session_scope() as session:
                    flows = (await session.exec(select(Flow))).all()

                    for flow in flows:
                        if flow.id:
                            try:
                                files = await storage_service.list_files(flow_id=str(flow.id))
                                for file_name in files:
                                    # URL encode the filename
                                    safe_filename = quote(file_name)
                                    resource = types.Resource(
                                        uri=f"{base_url}/api/v1/files/{flow.id}/{safe_filename}",
                                        name=file_name,
                                        description=f"File in flow: {flow.name}",
                                        mimeType=build_content_type_from_extension(file_name),
                                    )
                                    resources.append(resource)
                            except FileNotFoundError as e:
                                msg = f"Error listing files for flow {flow.id}: {e}"
                                logger.debug(msg)
                                continue
            except Exception as e:
                msg = f"Error in listing resources: {e!s}"
                logger.exception(msg)
                raise
            return resources

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> bytes:
            """Handle resource read requests."""
            try:
                # Parse the URI properly
                parsed_uri = urlparse(str(uri))
                # Path will be like /api/v1/files/{flow_id}/{filename}
                path_parts = parsed_uri.path.split("/")
                # Remove empty strings from split
                path_parts = [p for p in path_parts if p]

                # The flow_id and filename should be the last two parts
                two = 2
                if len(path_parts) < two:
                    msg = f"Invalid URI format: {uri}"
                    raise ValueError(msg)

                flow_id = path_parts[-2]
                filename = unquote(path_parts[-1])  # URL decode the filename

                storage_service = get_storage_service()

                # Read the file content
                content = await storage_service.get_file(flow_id=flow_id, file_name=filename)
                if not content:
                    msg = f"File {filename} not found in flow {flow_id}"
                    raise ValueError(msg)

                # Ensure content is base64 encoded
                if isinstance(content, str):
                    content = content.encode()
                return base64.b64encode(content)
            except Exception as e:
                msg = f"Error reading resource {uri}: {e!s}"
                logger.exception(msg)
                raise

        @self.server.call_tool()
        @handle_mcp_errors
        async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            """Handle tool execution requests."""
            mcp_config = get_mcp_config()
            if mcp_config.enable_progress_notifications is None:
                settings_service = get_settings_service()
                mcp_config.enable_progress_notifications = (
                    settings_service.settings.mcp_server_enable_progress_notifications
                )

            current_user = current_user_ctx.get()

            async def execute_tool(session):
                # get flow id from name
                flow = await get_flow_snake_case(name, current_user.id, session, is_action=True)
                if not flow:
                    msg = f"Flow with name '{name}' not found"
                    raise ValueError(msg)

                # Process inputs
                processed_inputs = dict(arguments)

                # Initial progress notification
                if mcp_config.enable_progress_notifications and (
                    progress_token := self.server.request_context.meta.progressToken
                ):
                    await self.server.request_context.session.send_progress_notification(
                        progress_token=progress_token, progress=0.0, total=1.0
                    )

                conversation_id = str(uuid4())
                input_request = SimplifiedAPIRequest(
                    input_value=processed_inputs.get("input_value", ""), session_id=conversation_id
                )

                async def send_progress_updates(progress_token):
                    try:
                        progress = 0.0
                        while True:
                            await self.server.request_context.session.send_progress_notification(
                                progress_token=progress_token, progress=min(0.9, progress), total=1.0
                            )
                            progress += 0.1
                            await asyncio.sleep(1.0)
                    except asyncio.CancelledError:
                        if mcp_config.enable_progress_notifications:
                            await self.server.request_context.session.send_progress_notification(
                                progress_token=progress_token, progress=1.0, total=1.0
                            )
                        raise

                collected_results = []
                try:
                    progress_task = None
                    if mcp_config.enable_progress_notifications and self.server.request_context.meta.progressToken:
                        progress_task = asyncio.create_task(
                            send_progress_updates(self.server.request_context.meta.progressToken)
                        )

                    try:
                        try:
                            result = await simple_run_flow(
                                flow=flow,
                                input_request=input_request,
                                stream=False,
                                api_key_user=current_user,
                            )
                            # Process all outputs and messages
                            for run_output in result.outputs:
                                for component_output in run_output.outputs:
                                    # Handle messages
                                    for msg in component_output.messages or []:
                                        text_content = types.TextContent(type="text", text=msg.message)
                                        collected_results.append(text_content)
                                    # Handle results
                                    for value in (component_output.results or {}).values():
                                        if isinstance(value, Message):
                                            text_content = types.TextContent(type="text", text=value.get_text())
                                            collected_results.append(text_content)
                                        else:
                                            collected_results.append(types.TextContent(type="text", text=str(value)))
                        except Exception as e:  # noqa: BLE001
                            error_msg = f"Error Executing the {flow.name} tool. Error: {e!s}"
                            collected_results.append(types.TextContent(type="text", text=error_msg))

                        return collected_results
                    finally:
                        if progress_task:
                            progress_task.cancel()
                            await asyncio.gather(progress_task, return_exceptions=True)

                except Exception:
                    if mcp_config.enable_progress_notifications and (
                        progress_token := self.server.request_context.meta.progressToken
                    ):
                        await self.server.request_context.session.send_progress_notification(
                            progress_token=progress_token, progress=1.0, total=1.0
                        )
                    raise

            try:
                return await with_db_session(execute_tool)
            except Exception as e:
                msg = f"Error executing tool {name}: {e!s}"
                logger.exception(msg)
                raise


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
                except Exception as e:
                    msg = f"Failed to initialize MCP server for project {project.id}: {e}"
                    logger.exception(msg)
                    # Continue to next project even if this one fails

    except Exception as e:
        msg = f"Failed to initialize MCP servers: {e}"
        logger.exception(msg)
