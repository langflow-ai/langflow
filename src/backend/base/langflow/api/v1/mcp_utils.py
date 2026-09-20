"""Common MCP handler functions shared between mcp.py and mcp_projects.py.

This module serves as the single source of truth for MCP functionality.
"""

import asyncio
import base64
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ParamSpec, TypeVar
from urllib.parse import quote, unquote, urlparse
from uuid import UUID, uuid4

from fastapi import HTTPException
from lfx.base.mcp.constants import MAX_MCP_TOOL_NAME_LENGTH
from lfx.base.mcp.util import get_flow_snake_case, get_unique_name, sanitize_mcp_name
from lfx.log.logger import logger
from lfx.observability import execution_protocol
from lfx.utils.flow_validation import (
    CustomComponentValidationError,
    prepare_public_flow_build,
    validate_public_flow_no_code_execution,
)
from lfx.utils.helpers import build_content_type_from_extension
from mcp import types
from sqlmodel import select

from langflow.api.utils.core import strip_secret_field_values
from langflow.api.utils.flow_utils import compute_virtual_flow_id, scope_session_to_namespace
from langflow.api.v1.endpoints import simple_run_flow
from langflow.api.v1.run_validation import HITL_UNSUPPORTED_DETAIL, flow_requires_hitl
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.helpers.flow import get_flow_input_tweaks, json_schema_from_flow
from langflow.schema.message import Message
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.authorization.public_access import public_execution_user
from langflow.services.database.models import Flow
from langflow.services.database.models.file.model import File as UserFile
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, get_storage_service, session_scope

T = TypeVar("T")
P = ParamSpec("P")

MCP_SERVERS_FILE = "_mcp_servers"

# Create context variables
current_user_ctx: ContextVar[User] = ContextVar("current_user_ctx")

authenticated_caller_ctx: ContextVar[UUID | None] = ContextVar("authenticated_caller_ctx", default=None)


def caller_owns_resource(owner_id: UUID | None) -> bool:
    """Whether the credential presented on this request belongs to the resource owner.

    The principal a tool call *executes as* is not always the principal that authenticated:
    a project with ``auth_type="none"`` runs as its owner on behalf of an anonymous caller,
    so comparing the execution principal to the owner answers yes for everyone. The caller
    context defaults to unset, which reads as anonymous, so a path that never establishes a
    caller loses the privilege instead of inheriting the owner's.
    """
    caller_id = authenticated_caller_ctx.get()
    return caller_id is not None and owner_id is not None and caller_id == owner_id


def _public_mcp_session_namespace(server: Any, project_id: UUID, flow_id: UUID) -> str:
    """Return a per-MCP-connection namespace for anonymous session IDs."""
    mcp_session = getattr(getattr(server, "request_context", None), "session", None)
    connection_id = getattr(mcp_session, "session_id", None)
    if not connection_id:
        # The SSE session object is stable for the life of a connection even on
        # SDK versions that do not expose a public session identifier.
        connection_id = str(id(mcp_session)) if mcp_session is not None else str(uuid4())
    identifier = f"mcp:{project_id}:{connection_id}"
    return str(compute_virtual_flow_id(identifier, flow_id, principal_type="client"))


def _restore_public_mcp_request_variable_references(
    source: Any,
    sanitized: Any,
    request_variables: dict[str, str],
) -> None:
    """Restore sanitized variable names only when the current request supplies them.

    Public MCP execution scrubs all secret-looking values before building the flow. A
    ``load_from_db`` field or table cell contains a variable *name*, not the stored
    secret, and the build needs that name to resolve a request-scoped override. Restore
    only references that have a matching request value so anonymous execution cannot
    fall back to an owner's database variables or ambient environment credentials.
    """
    if isinstance(source, dict) and isinstance(sanitized, dict):
        source_value = source.get("value")
        if source.get("load_from_db") is True and isinstance(source_value, str) and source_value in request_variables:
            sanitized["value"] = source_value

        row_load_from_db_fields = source.get("__load_from_db_fields")
        if isinstance(row_load_from_db_fields, dict):
            variable_fields = [name for name, enabled in row_load_from_db_fields.items() if enabled is True]
        elif isinstance(row_load_from_db_fields, list):
            variable_fields = row_load_from_db_fields
        else:
            variable_fields = []
        for field_name in variable_fields:
            variable_name = source.get(field_name)
            if isinstance(field_name, str) and isinstance(variable_name, str) and variable_name in request_variables:
                sanitized[field_name] = variable_name

        for key, source_child in source.items():
            if key in sanitized:
                _restore_public_mcp_request_variable_references(
                    source_child,
                    sanitized[key],
                    request_variables,
                )
    elif isinstance(source, list) and isinstance(sanitized, list):
        for source_item, sanitized_item in zip(source, sanitized, strict=False):
            _restore_public_mcp_request_variable_references(source_item, sanitized_item, request_variables)


async def _prepare_public_mcp_execution_flow(
    flow: Flow,
    request_variables: dict[str, str] | None = None,
) -> Flow:
    """Apply the shared anonymous-flow policy to a detached MCP execution graph."""
    validate_public_flow_no_code_execution(flow.data)
    prepared_data = await prepare_public_flow_build(flow.data)
    source_data = prepared_data if prepared_data is not None else flow.data
    sanitized_data = strip_secret_field_values(source_data)
    if request_variables:
        _restore_public_mcp_request_variable_references(source_data, sanitized_data, request_variables)
    return flow.model_copy(update={"data": sanitized_data}, deep=True)


EXCLUDED_FLOWS_META_KEY = "langflow.org/excluded-flows"
# Carries per-request variables injected via HTTP headers (e.g., X-Langflow-Global-Var-*)
current_request_variables_ctx: ContextVar[dict[str, str] | None] = ContextVar(
    "current_request_variables_ctx", default=None
)
# Carries the inbound request's headers into the deep MCP tool dispatch. The MCP SDK invokes
# handle_call_tool through its own machinery, so the live FastAPI request is not on the call
# chain; the streamable/SSE endpoint stashes ``request.headers`` here (same pattern as
# current_request_variables_ctx) so a tool run can scope to the serving end-user identity via
# the same ``resolve_serving_scope`` path /run and /workflows use. None outside a request.
current_request_headers_ctx: ContextVar[Any] = ContextVar("current_request_headers_ctx", default=None)


def handle_mcp_errors(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """Decorator to handle MCP endpoint errors consistently."""

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            msg = f"Error in {func.__name__}: {e!s}"
            await logger.aexception(msg)
            raise

    return wrapper


async def with_db_session(operation: Callable[[Any], Awaitable[T]]) -> T:
    """Execute an operation within a database session context."""
    async with session_scope() as session:
        return await operation(session)


class MCPConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.enable_progress_notifications = None
        return cls._instance


def get_mcp_config():
    return MCPConfig()


def raise_if_sse_disabled() -> None:
    """Reject legacy SSE transport requests when the deployment has turned it off."""
    if not get_settings_service().settings.mcp_sse_enabled:
        raise HTTPException(status_code=404, detail="SSE transport is disabled. Use the Streamable HTTP endpoint.")


async def handle_list_resources(project_id=None):
    """Handle listing resources for MCP.

    Args:
        project_id: Optional project ID to filter resources by project
    """
    resources = []
    try:
        storage_service = get_storage_service()
        settings_service = get_settings_service()

        # Build full URL from settings
        host = getattr(settings_service.settings, "host", "localhost")
        port = getattr(settings_service.settings, "port", 3000)

        base_url = f"http://{host}:{port}".rstrip("/")
        try:
            current_user = current_user_ctx.get()
        except Exception as e:  # noqa: BLE001
            msg = f"Error getting current user: {e!s}"
            await logger.aexception(msg)
            current_user = None

        # SECURITY: The current_user context is required to scope resources.
        # Without it we cannot safely list files from any flow because the
        # global server previously leaked every user's flow URIs (PVR0754098).
        if current_user is None:
            await logger.awarning("handle_list_resources called without a current user; returning empty list")
            return resources

        async with session_scope() as session:
            # SECURITY: Always scope to the calling user to prevent cross-user enumeration.
            if project_id:
                flows_query = select(Flow).where(Flow.folder_id == project_id, Flow.user_id == current_user.id)
            else:
                flows_query = select(Flow).where(Flow.user_id == current_user.id)

            flows = (await session.exec(flows_query)).all()

            for flow in flows:
                if flow.id:
                    try:
                        files = await storage_service.list_files(flow_id=str(flow.id))
                        for file_name in files:
                            # URL encode the filename
                            safe_filename = quote(file_name)
                            resource = types.Resource(
                                uri=f"{base_url}/api/v1/files/download/{flow.id}/{safe_filename}",
                                name=file_name,
                                description=f"File in flow: {flow.name}",
                                mimeType=build_content_type_from_extension(file_name),
                            )
                            resources.append(resource)
                    except FileNotFoundError as e:
                        msg = f"Error listing files for flow {flow.id}: {e}"
                        await logger.adebug(msg)
                        continue
            ####################################################
            # When a user uploads a file inside a flow
            # (e.g., via the File Read component),
            # it hits /api/v2/files (POST),
            # which saves files at the user-level.
            # So the above query for flow files is not enough.
            # So we list all user files for the current user.
            # This is not good. We need to fix this for 1.8.0.
            #
            # SECURITY (PVR0754098): user-level files have no project association,
            # so they must not be exposed through a project-scoped MCP server —
            # doing so would let a project client enumerate files unrelated to
            # the project. Only include them on the global (project_id is None) server.
            ###################################################
            if project_id is None:
                user_files_stmt = select(UserFile).where(UserFile.user_id == current_user.id)
                user_files = (await session.exec(user_files_stmt)).all()
                for user_file in user_files:
                    stored_path = getattr(user_file, "path", "") or ""
                    stored_filename = Path(stored_path).name if stored_path else user_file.name
                    safe_filename = quote(stored_filename)
                    if stored_filename.startswith(f"{MCP_SERVERS_FILE}_{current_user.id}"):
                        # reserved file name for langflow MCP server config file(s)
                        continue
                    description = getattr(user_file, "provider", None) or "User file uploaded via File Manager"
                    resource = types.Resource(
                        uri=f"{base_url}/api/v1/files/download/{current_user.id}/{safe_filename}",
                        name=stored_filename,
                        description=description,
                        mimeType=build_content_type_from_extension(stored_filename),
                    )
                    resources.append(resource)
    except Exception as e:
        msg = f"Error in listing resources: {e!s}"
        await logger.aexception(msg)
        raise
    return resources


async def handle_read_resource(uri: str, project_id: UUID | str | None = None) -> bytes:
    """Handle resource read requests.

    Args:
        uri: The resource URI; last two path segments are the namespace (flow_id or user_id)
            and filename.
        project_id: When invoked from a project-scoped server, restricts the lookup so a
            caller cannot read resources that live outside the project.
    """
    try:
        # Parse the URI properly
        parsed_uri = urlparse(str(uri))
        # Path will be like /api/v1/files/download/{namespace}/{filename}
        path_parts = parsed_uri.path.split("/")
        # Remove empty strings from split
        path_parts = [p for p in path_parts if p]

        # The flow_id and filename should be the last two parts
        two = 2
        if len(path_parts) < two:
            msg = f"Invalid URI format: {uri}"
            raise ValueError(msg)

        namespace_id = path_parts[-2]
        filename = unquote(path_parts[-1])  # URL decode the filename

        # SECURITY (defense-in-depth): reject obvious traversal attempts before any
        # service call. The storage service validates as well, but failing fast here
        # keeps error logs from the storage layer off the hot path and closes the gap
        # between the MCP decode step and the storage layer for future refactors.
        if not filename or ".." in filename or "/" in filename or "\\" in filename:
            await logger.awarning(f"Rejected MCP resource read with invalid filename: {filename!r}")
            msg = "Invalid filename"
            raise ValueError(msg)

        # SECURITY: authorise the caller before reading. The storage layer alone is
        # not enough because the filesystem doesn't know about Langflow users, and
        # previously any authenticated user could request any flow_id.
        try:
            current_user = current_user_ctx.get()
        except LookupError as exc:
            msg = "Authenticated user context is required to read MCP resources"
            raise ValueError(msg) from exc

        parsed_project_id = None
        if project_id is not None:
            try:
                parsed_project_id = UUID(str(project_id))
            except ValueError as exc:
                msg = "Resource not found or access denied"
                raise ValueError(msg) from exc

        async with session_scope() as session:
            try:
                flow_id = UUID(namespace_id)
            except ValueError:
                flow = None
            else:
                flow_query = select(Flow).where(Flow.id == flow_id, Flow.user_id == current_user.id)
                if parsed_project_id is not None:
                    flow_query = flow_query.where(Flow.folder_id == parsed_project_id)
                flow = (await session.exec(flow_query)).first()

            if flow is None:
                # The namespace segment may refer to the user's own bucket (user-level
                # files uploaded via /api/v2/files) rather than a flow id.
                if str(current_user.id) != str(namespace_id):
                    msg = "Resource not found or access denied"
                    raise ValueError(msg)
                # User-level access is never in-scope for a project-scoped server.
                if project_id is not None:
                    msg = "Resource not found or access denied"
                    raise ValueError(msg)

        storage_service = get_storage_service()

        # Read the file content
        content = await storage_service.get_file(flow_id=namespace_id, file_name=filename)
        if not content:
            msg = f"File {filename} not found in flow {namespace_id}"
            raise ValueError(msg)

        # Ensure content is base64 encoded
        if isinstance(content, str):
            content = content.encode()
        return base64.b64encode(content)
    except Exception as e:
        msg = f"Error reading resource {uri}: {e!s}"
        await logger.aexception(msg)
        raise


async def handle_call_tool(
    name: str, arguments: dict, server, project_id=None, *, is_action=False
) -> list[types.TextContent]:
    """Handle tool execution requests.

    Args:
        name: Tool name
        arguments: Tool arguments
        server: MCP server instance
        project_id: Optional project ID to filter flows by project
        is_action: Whether to use action name for flow lookup
    """
    mcp_config = get_mcp_config()
    if mcp_config.enable_progress_notifications is None:
        settings_service = get_settings_service()
        mcp_config.enable_progress_notifications = settings_service.settings.mcp_server_enable_progress_notifications

    current_user = current_user_ctx.get()
    # Build execution context with request-level variables if present
    request_variables = current_request_variables_ctx.get()
    exec_context = {"request_variables": request_variables} if request_variables else None

    async def execute_tool(session):
        # Scoping in the query, not after it: post-filtering let an unexposed flow run by
        # name and let one project win a name shared with another, silencing the second.
        flow = await get_flow_snake_case(
            name,
            current_user.id,
            session,
            is_action=is_action,
            project_id=project_id,
            mcp_enabled_only=project_id is not None,
        )
        if not flow:
            msg = f"Flow with name '{name}' not found"
            raise ValueError(msg)

        # Defense in depth: the query above already scopes by project.
        if project_id and flow.folder_id != project_id:
            msg = f"Flow '{name}' not found in project {project_id}"
            raise ValueError(msg)

        # Enforce execute permission (owner override + external access ceiling)
        # before running the flow. Without this an external "viewer" could run a
        # flow as a tool, escaping the deny-only access ceiling.
        await ensure_flow_permission(
            current_user,
            FlowAction.EXECUTE,
            flow_id=flow.id,
            flow_user_id=flow.user_id,
            workspace_id=flow.workspace_id,
            folder_id=flow.folder_id,
        )

        if flow_requires_hitl(flow.data or {}):
            raise RuntimeError(HITL_UNSUPPORTED_DETAIL)

        is_public_project_call = project_id is not None and authenticated_caller_ctx.get() is None
        execution_flow = flow
        execution_user = current_user
        if is_public_project_call:
            try:
                execution_flow = await _prepare_public_mcp_execution_flow(flow, request_variables)
            except CustomComponentValidationError as exc:
                await logger.awarning(f"Public MCP tool call blocked for flow {flow.id}: {exc!s}")
                msg = "This flow cannot be executed through a public MCP project."
                raise RuntimeError(msg) from exc
            execution_user = public_execution_user()

        # Process inputs
        processed_inputs = dict(arguments)

        # Initial progress notification
        if mcp_config.enable_progress_notifications and (progress_token := server.request_context.meta.progressToken):
            await server.request_context.session.send_progress_notification(
                progress_token=progress_token, progress=0.0, total=1.0
            )

        session_id = processed_inputs.pop("session_id", None) or str(uuid4())
        if is_public_project_call:
            namespace = _public_mcp_session_namespace(server, project_id, flow.id)
            session_id = scope_session_to_namespace(session_id, namespace) or namespace
        input_value = processed_inputs.pop("input_value", "")
        tweaks = get_flow_input_tweaks(execution_flow, processed_inputs) if processed_inputs else None
        input_request = SimplifiedAPIRequest(
            input_value=input_value,
            session_id=session_id,
            tweaks=tweaks or None,
        )

        async def send_progress_updates(progress_token):
            try:
                progress = 0.0
                while True:
                    await server.request_context.session.send_progress_notification(
                        progress_token=progress_token, progress=min(0.9, progress), total=1.0
                    )
                    progress += 0.1
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                if mcp_config.enable_progress_notifications:
                    await server.request_context.session.send_progress_notification(
                        progress_token=progress_token, progress=1.0, total=1.0
                    )
                raise

        collected_results = []
        try:
            progress_task = None
            if mcp_config.enable_progress_notifications and server.request_context.meta.progressToken:
                progress_task = asyncio.create_task(send_progress_updates(server.request_context.meta.progressToken))

            try:
                # Scope the run to the serving end-user identity exactly as /run and
                # /workflows do: the MCP SDK dispatch has no live request on the call
                # chain, so replay the endpoint-captured headers through a minimal shim
                # (resolve_serving_scope only needs ``headers.get``). None -> feature off
                # / no request -> scoping skipped, byte-for-byte the prior behavior.
                req_headers = current_request_headers_ctx.get()
                http_request_shim = SimpleNamespace(headers=req_headers) if req_headers is not None else None
                try:
                    with execution_protocol("mcp"):
                        result = await simple_run_flow(
                            flow=execution_flow,
                            input_request=input_request,
                            stream=False,
                            api_key_user=execution_user,
                            context=exec_context,
                            expose_error_details=caller_owns_resource(flow.user_id),
                            http_request=http_request_shim,
                        )
                    # Process all outputs and messages, ensuring no duplicates
                    processed_texts = set()

                    def add_result(text: str):
                        if text not in processed_texts:
                            processed_texts.add(text)
                            collected_results.append(types.TextContent(type="text", text=text))

                    for run_output in result.outputs:
                        for component_output in run_output.outputs:
                            # Handle messages
                            for msg in component_output.messages or []:
                                add_result(msg.message)
                            # Handle results
                            for value in (component_output.results or {}).values():
                                if isinstance(value, Message):
                                    add_result(value.get_text())
                                else:
                                    add_result(str(value))
                # Raise rather than return the message as content: an MCP client cannot
                # tell a failure from an answer unless the response carries isError.
                except CustomComponentValidationError as exc:
                    logger.warning(f"MCP tool call blocked for flow {flow.id}: {exc!s}")
                    msg = f"Flow build blocked for the {flow.name} tool. Error: {exc!s}"
                    raise RuntimeError(msg) from exc
                except Exception as exc:
                    msg = f"Error Executing the {flow.name} tool. Error: {exc!s}"
                    raise RuntimeError(msg) from exc

                return collected_results
            finally:
                if progress_task:
                    progress_task.cancel()
                    await asyncio.gather(progress_task, return_exceptions=True)

        except Exception:
            if mcp_config.enable_progress_notifications and (
                progress_token := server.request_context.meta.progressToken
            ):
                await server.request_context.session.send_progress_notification(
                    progress_token=progress_token, progress=1.0, total=1.0
                )
            raise

    try:
        return await with_db_session(execute_tool)
    except Exception as e:
        msg = f"Error executing tool {name}: {e!s}"
        await logger.aexception(msg)
        raise


async def _collect_tools(
    project_id: UUID | None = None, *, mcp_enabled_only: bool = False
) -> tuple[list[types.Tool], list[dict[str, str]]]:
    """Build the tool list for MCP, returning the flows that could not be built alongside it.

    Args:
        project_id: Optional project ID to filter tools by project
        mcp_enabled_only: Whether to filter for MCP-enabled flows only

    Returns:
        The tools that built successfully and one entry per flow dropped from the list.
    """
    tools: list[types.Tool] = []
    excluded: list[dict[str, str]] = []
    try:
        # SECURITY: tools returned from the global server previously included every
        # user's flows (PVR0754098). Always scope to the authenticated caller.
        try:
            current_user = current_user_ctx.get()
        except LookupError:
            current_user = None

        async with session_scope() as session:
            # Build query based on parameters
            if project_id:
                # SECURITY (defense-in-depth): Filter by both folder_id AND user_id.
                # While verify_project_auth_conditional already ensures the user owns the project,
                # this query-level filter provides an additional safety layer and maintains
                # consistency with handle_list_resources() and handle_read_resource().
                if current_user is None:
                    await logger.awarning(
                        "handle_list_tools called with project_id but no current user; returning empty list"
                    )
                    return tools, excluded
                # Ordered for the same reason the call path is: without it, which duplicate
                # holds the bare callable name and which gets get_unique_name's _1 suffix
                # is heap order, so it can flip between two calls.
                flows_query = (
                    select(Flow)
                    .where(
                        Flow.folder_id == project_id,
                        Flow.user_id == current_user.id,
                        Flow.is_component == False,  # noqa: E712
                    )
                    .order_by(Flow.id)
                )
                if mcp_enabled_only:
                    flows_query = flows_query.where(Flow.mcp_enabled == True)  # noqa: E712
            elif current_user is not None:
                # Global server: scope to the calling user only.
                flows_query = select(Flow).where(Flow.user_id == current_user.id).order_by(Flow.id)
            else:
                await logger.awarning(
                    "handle_list_tools called without a current user and no project_id; returning empty list"
                )
                return tools, excluded

            flows = (await session.exec(flows_query)).all()

            existing_names = set()
            for flow in flows:
                if flow.user_id is None:
                    continue

                # For project-specific tools, use action names if available
                if project_id:
                    base_name = (
                        sanitize_mcp_name(flow.action_name) if flow.action_name else sanitize_mcp_name(flow.name)
                    )
                    name = get_unique_name(base_name, MAX_MCP_TOOL_NAME_LENGTH, existing_names)
                    description = flow.action_description or (
                        flow.description if flow.description else f"Tool generated from flow: {name}"
                    )
                else:
                    # For global tools, use simple sanitized names
                    base_name = sanitize_mcp_name(flow.name)
                    name = base_name[:MAX_MCP_TOOL_NAME_LENGTH]
                    if name in existing_names:
                        i = 1
                        while True:
                            suffix = f"_{i}"
                            truncated_base = base_name[: MAX_MCP_TOOL_NAME_LENGTH - len(suffix)]
                            candidate = f"{truncated_base}{suffix}"
                            if candidate not in existing_names:
                                name = candidate
                                break
                            i += 1
                    description = (
                        f"{flow.id}: {flow.description}" if flow.description else f"Tool generated from flow: {name}"
                    )

                try:
                    tool = types.Tool(
                        name=name,
                        description=description,
                        inputSchema=json_schema_from_flow(flow),
                    )
                    tools.append(tool)
                    existing_names.add(name)
                except Exception as e:  # noqa: BLE001
                    # Type only: the project endpoint answers end users on the serving plane, and a raw
                    # exception string carries paths, SQL and component internals. The full
                    # message stays in the error log below, where only the operator reads it.
                    excluded.append({"flow_id": str(flow.id), "tool_name": base_name, "reason": type(e).__name__})
                    await logger.aerror(f"Flow excluded from MCP tool list -- {base_name} ({flow.id}): {e!s}")
                    continue

            # A project that answers 200 with an empty list reads as "no tools configured".
            # If every flow was dropped, say so instead of letting the deploy look healthy.
            # Scoped to the project endpoint: the global server is the editor-plane surface,
            # where an empty list is a normal state and raising would be a UI regression.
            if project_id and excluded and not tools:
                raise RuntimeError(_format_excluded(excluded))
    except Exception as e:
        msg = f"Error in listing tools: {e!s}"
        await logger.aexception(msg)
        raise
    return tools, excluded


def _format_excluded(excluded: list[dict[str, str]]) -> str:
    details = "; ".join(f"{item['tool_name']} ({item['flow_id']}): {item['reason']}" for item in excluded)
    return f"No MCP tools could be built. Excluded flows: {details}"


async def handle_list_tools(project_id: UUID | None = None, *, mcp_enabled_only: bool = False) -> list[types.Tool]:
    """Handle listing tools for MCP.

    Args:
        project_id: Optional project ID to filter tools by project
        mcp_enabled_only: Whether to filter for MCP-enabled flows only
    """
    tools, _ = await _collect_tools(project_id, mcp_enabled_only=mcp_enabled_only)
    return tools


async def handle_list_tools_result(
    project_id: UUID | None = None, *, mcp_enabled_only: bool = False
) -> types.ListToolsResult:
    """Handle listing tools for a project, reporting any flow that had to be dropped.

    Returning only the surviving tools reads as a complete list, so an operator cannot tell
    that a tool went missing and the sole trace is a server-side log line. Partial failures
    ride along in ``_meta`` because the tool array itself must stay callable-only.
    """
    tools, excluded = await _collect_tools(project_id, mcp_enabled_only=mcp_enabled_only)
    result = types.ListToolsResult(tools=tools)
    if excluded:
        # Assigned rather than passed to the constructor: the field is aliased to `_meta`
        # and the model has no populate_by_name, so `meta=` lands as an extra field.
        result.meta = {EXCLUDED_FLOWS_META_KEY: excluded}
    return result
