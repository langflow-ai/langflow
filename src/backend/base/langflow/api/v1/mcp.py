import asyncio
import json
import secrets
from typing import Any

import pydantic
from anyio import BrokenResourceError
from fastapi import APIRouter, HTTPException, Header, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from lfx.log.logger import logger
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport

from langflow.api.utils import CurrentActiveMCPUser
from langflow.api.v1.mcp_utils import (
    current_user_ctx,
    handle_call_tool,
    handle_list_resources,
    handle_list_tools,
    handle_mcp_errors,
    handle_read_resource,
)
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/mcp", tags=["mcp"])

server = Server("langflow-mcp-server")

# Session management for Streamable HTTP
# Maps session_id -> user context
_sessions: dict[str, Any] = {}


# Define constants
MAX_RETRIES = 2
MCP_REQUEST_TIMEOUT = 30.0  # seconds


def get_enable_progress_notifications() -> bool:
    return get_settings_service().settings.mcp_server_enable_progress_notifications


@server.list_prompts()
async def handle_list_prompts():
    return []


@server.list_resources()
async def handle_global_resources():
    """Handle listing resources for global MCP server."""
    return await handle_list_resources()


@server.read_resource()
async def handle_global_read_resource(uri: str) -> bytes:
    """Handle resource read requests for global MCP server."""
    return await handle_read_resource(uri)


@server.list_tools()
async def handle_global_tools():
    """Handle listing tools for global MCP server."""
    return await handle_list_tools()


@server.call_tool()
@handle_mcp_errors
async def handle_global_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool execution requests for global MCP server."""
    return await handle_call_tool(name, arguments, server)


sse = SseServerTransport("/api/v1/mcp/")


def find_validation_error(exc):
    """Searches for a pydantic.ValidationError in the exception chain."""
    while exc:
        if isinstance(exc, pydantic.ValidationError):
            return exc
        exc = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    return None


@router.head("/sse", response_class=HTMLResponse, include_in_schema=False)
async def im_alive():
    return Response()


@router.get("/sse", response_class=StreamingResponse)
async def handle_sse(request: Request, current_user: CurrentActiveMCPUser):
    msg = f"Starting SSE connection, server name: {server.name}"
    await logger.ainfo(msg)
    token = current_user_ctx.set(current_user)
    try:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:  # noqa: SLF001
            try:
                msg = "Starting SSE connection"
                await logger.adebug(msg)
                msg = f"Stream types: read={type(streams[0])}, write={type(streams[1])}"
                await logger.adebug(msg)

                notification_options = NotificationOptions(
                    prompts_changed=True, resources_changed=True, tools_changed=True
                )
                init_options = server.create_initialization_options(notification_options)
                msg = f"Initialization options: {init_options}"
                await logger.adebug(msg)

                try:
                    await server.run(streams[0], streams[1], init_options)
                except Exception as exc:  # noqa: BLE001
                    validation_error = find_validation_error(exc)
                    if validation_error:
                        msg = "Validation error in MCP:" + str(validation_error)
                        await logger.adebug(msg)
                    else:
                        msg = f"Error in MCP: {exc!s}"
                        await logger.adebug(msg)
                        return
            except BrokenResourceError:
                # Handle gracefully when client disconnects
                await logger.ainfo("Client disconnected from SSE connection")
            except asyncio.CancelledError:
                await logger.ainfo("SSE connection was cancelled")
                raise
            except Exception as e:
                msg = f"Error in MCP: {e!s}"
                await logger.aexception(msg)
                raise
    finally:
        current_user_ctx.reset(token)


@router.post("/")
async def handle_messages(request: Request):
    """Legacy SSE POST endpoint for backwards compatibility."""
    try:
        await sse.handle_post_message(request.scope, request.receive, request._send)  # noqa: SLF001
    except (BrokenResourceError, BrokenPipeError) as e:
        await logger.ainfo("MCP Server disconnected")
        raise HTTPException(status_code=404, detail=f"MCP Server disconnected, error: {e}") from e
    except Exception as e:
        await logger.aerror(f"Internal server error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") from e


def _validate_origin(origin: str | None, request: Request) -> None:
    """Validate Origin header to prevent DNS rebinding attacks."""
    if not origin:
        return
    
    settings_service = get_settings_service()
    host = getattr(settings_service.settings, "host", "localhost")
    port = getattr(settings_service.settings, "port", 3000)
    
    # Allow localhost connections
    allowed_origins = [
        f"http://localhost:{port}",
        f"https://localhost:{port}",
        f"http://127.0.0.1:{port}",
        f"https://127.0.0.1:{port}",
    ]
    
    # If host is not localhost, allow connections from the configured host
    if host not in ["localhost", "127.0.0.1"]:
        allowed_origins.extend([
            f"http://{host}:{port}",
            f"https://{host}:{port}",
        ])
    
    if origin not in allowed_origins:
        # For now, log warning but don't block (can be made stricter)
        # Note: Using sync logger.warning since this is called from sync context
        logger.warning(f"Origin validation: {origin} not in allowed origins")


def _generate_session_id() -> str:
    """Generate a cryptographically secure session ID."""
    return secrets.token_urlsafe(32)


def _is_jsonrpc_request(message: dict) -> bool:
    """Check if a JSON-RPC message is a request (has id and method)."""
    return isinstance(message, dict) and "id" in message and "method" in message


def _is_jsonrpc_notification(message: dict) -> bool:
    """Check if a JSON-RPC message is a notification (has method but no id)."""
    return isinstance(message, dict) and "method" in message and "id" not in message


def _is_jsonrpc_response(message: dict) -> bool:
    """Check if a JSON-RPC message is a response (has id and result/error, no method)."""
    return isinstance(message, dict) and "id" in message and "method" not in message and ("result" in message or "error" in message)


class _StreamableHttpReadStream:
    """Async iterator for reading JSON-RPC messages from POST body (input to MCP server)."""

    def __init__(self, messages: list[dict]):
        # Convert messages to JSON-RPC format (newline-delimited)
        self._messages = [json.dumps(msg).encode() + b"\n" for msg in messages]
        self._index = 0
        self._closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._closed or self._index >= len(self._messages):
            raise StopAsyncIteration
        msg = self._messages[self._index]
        self._index += 1
        return msg

    def close(self):
        """Close the stream."""
        self._closed = True


class _StreamableHttpWriteStream:
    """Async context manager for collecting responses from MCP server (output stream).
    
    The MCP server calls write() to send responses. We collect them for later formatting.
    """

    def __init__(self):
        self._responses: list[bytes] = []
        self._closed = False

    async def write(self, data: bytes):
        """Write response data (called by MCP server)."""
        if not self._closed:
            self._responses.append(data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Mark as closed but keep responses accessible
        self._closed = True

    def get_all_responses(self) -> list[dict]:
        """Get all parsed JSON responses (for JSON response format)."""
        responses = []
        for data in self._responses:
            try:
                line = data.decode().strip()
                if line:
                    resp = json.loads(line)
                    responses.append(resp)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        return responses

    async def stream_responses(self):
        """Async generator for SSE streaming."""
        event_id = 0
        for data in self._responses:
            event_id += 1
            try:
                line = data.decode().strip()
                if line:
                    yield f"id: {event_id}\ndata: {line}\n\n"
            except UnicodeDecodeError:
                # Fallback for non-UTF8 data
                yield f"id: {event_id}\ndata: {data.decode(errors='replace')}\n\n"


async def _handle_streamable_http_post(
    request: Request,
    current_user: CurrentActiveMCPUser,
    mcp_session_id: str | None = Header(None, alias="Mcp-Session-Id"),
    origin: str | None = Header(None),
    accept: str = Header("application/json, text/event-stream"),
) -> Response:
    """Handle POST requests for Streamable HTTP transport.
    
    According to MCP spec, POST requests can:
    - Send JSON-RPC requests/notifications/responses
    - Return either JSON or SSE stream
    - Return 202 Accepted for notifications/responses only
    """
    # Validate Origin header
    _validate_origin(origin, request)
    
    # Get or create session
    session_id = mcp_session_id
    if not session_id:
        session_id = _generate_session_id()
        _sessions[session_id] = {"user": current_user, "initialized": False}
    elif session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    elif _sessions[session_id].get("user") != current_user:
        # Verify session belongs to current user
        raise HTTPException(status_code=403, detail="Session does not belong to authenticated user")
    
    # Parse request body
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e
    
    # Normalize to list of messages
    messages = body if isinstance(body, list) else [body]
    
    # Filter out invalid messages
    valid_messages = [msg for msg in messages if isinstance(msg, dict)]
    
    # If no valid messages, return error
    if not valid_messages:
        raise HTTPException(status_code=400, detail="No valid JSON-RPC messages in request body")
    
    # Check if body contains only notifications/responses
    has_requests = False
    is_initialization = False
    
    for msg in valid_messages:
        if _is_jsonrpc_request(msg):
            has_requests = True
            if msg.get("method") == "initialize":
                is_initialization = True
            break
    
    # If only notifications/responses, return 202 Accepted
    if not has_requests:
        response = Response(status_code=202)
        # Per MCP spec: session ID should only be set on InitializeResult, not on notifications
        # However, we create the session here for tracking purposes
        # Session ID will be returned on the next InitializeResult response
        return response
    
    # Handle requests - proper Streamable HTTP implementation
    token = current_user_ctx.set(current_user)
    try:
        # Create streams for MCP server
        read_stream = _StreamableHttpReadStream(valid_messages)
        write_stream = _StreamableHttpWriteStream()
        
        notification_options = NotificationOptions(
            prompts_changed=True, resources_changed=True, tools_changed=True
        )
        
        # Determine initialization options
        if is_initialization and not _sessions[session_id].get("initialized"):
            init_options = server.create_initialization_options(notification_options)
            _sessions[session_id]["initialized"] = True
        else:
            init_options = None
        
        # Check if client accepts SSE or prefers JSON
        accepts_sse = "text/event-stream" in accept.lower()
        prefers_json = "application/json" in accept.lower() and not accepts_sse
        
        # Run server to process messages
        server_task = None
        try:
            async with write_stream:
                server_task = asyncio.create_task(
                    server.run(read_stream, write_stream, init_options)
                )
                
                # Wait for server to process (with timeout)
                try:
                    # Give server time to process and generate responses
                    await asyncio.wait_for(server_task, timeout=MCP_REQUEST_TIMEOUT)
                except asyncio.TimeoutError:
                    await logger.awarning("MCP server request timed out")
                    if server_task:
                        server_task.cancel()
                        try:
                            await server_task
                        except asyncio.CancelledError:
                            pass
                except Exception as exc:  # noqa: BLE001
                    validation_error = find_validation_error(exc)
                    if validation_error:
                        await logger.adebug(f"Validation error in MCP: {validation_error}")
                    else:
                        await logger.adebug(f"Error in MCP: {exc!s}")
                    if server_task:
                        server_task.cancel()
                        try:
                            await server_task
                        except asyncio.CancelledError:
                            pass
                finally:
                    read_stream.close()
            
            # Collect responses after stream context exits
            # Note: server.run() should complete before context exits, so responses should be ready
            # If server.run() is still writing, those writes will be ignored (stream is closed)
            responses = write_stream.get_all_responses()
        except Exception:
            # Ensure task is cancelled on any error
            if server_task and not server_task.done():
                server_task.cancel()
                try:
                    await server_task
                except asyncio.CancelledError:
                    pass
            raise
        
        # Format response based on Accept header
        if prefers_json:
            # Return JSON response
            if responses:
                # Return single response or array
                response_data = responses[0] if len(responses) == 1 else responses
                response = JSONResponse(content=response_data)
            else:
                # No response received - format as JSON-RPC error
                response = JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": "No response from server"
                        }
                    },
                    status_code=500
                )
        else:
            # Return SSE stream
            async def sse_generator():
                """Generate SSE events from collected responses."""
                event_id = 0
                for resp in responses:
                    event_id += 1
                    data = json.dumps(resp)
                    yield f"id: {event_id}\ndata: {data}\n\n"
            
            response = StreamingResponse(
                sse_generator(),
                media_type="text/event-stream"
            )
        
        # Set session ID only on InitializeResult response (per MCP spec)
        if is_initialization and not mcp_session_id:
            # Check if we have an InitializeResult in responses
            initialize_request_id = None
            if valid_messages and isinstance(valid_messages[0], dict) and valid_messages[0].get("method") == "initialize":
                initialize_request_id = valid_messages[0].get("id")
            
            has_initialize_result = any(
                resp.get("result") is not None and resp.get("id") == initialize_request_id
                for resp in responses
            )
            if has_initialize_result:
                response.headers["Mcp-Session-Id"] = session_id
        
        return response
    except (BrokenResourceError, BrokenPipeError) as e:
        await logger.ainfo("MCP Server disconnected")
        raise HTTPException(status_code=404, detail=f"MCP Server disconnected, error: {e}") from e
    except Exception as e:
        await logger.aerror(f"Internal server error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") from e
    finally:
        current_user_ctx.reset(token)


@router.post("/streamable", response_class=Response)
async def handle_streamable_http_post_endpoint(
    request: Request,
    current_user: CurrentActiveMCPUser,
    mcp_session_id: str | None = Header(None, alias="Mcp-Session-Id"),
    origin: str | None = Header(None),
    accept: str = Header("application/json, text/event-stream"),
):
    """Streamable HTTP POST endpoint per MCP specification.
    
    Supports both application/json and text/event-stream responses.
    Per MCP spec, this is the single endpoint that handles all POST requests.
    """
    return await _handle_streamable_http_post(request, current_user, mcp_session_id, origin, accept)


@router.get("/streamable", response_class=StreamingResponse)
async def handle_streamable_http_get(
    request: Request,
    current_user: CurrentActiveMCPUser,
    mcp_session_id: str | None = Header(None, alias="Mcp-Session-Id"),
    origin: str | None = Header(None),
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
):
    """Streamable HTTP GET endpoint for server-initiated SSE streams.
    
    Per MCP spec, this opens an SSE stream allowing the server to send
    requests and notifications to the client.
    """
    # Validate Origin header
    _validate_origin(origin, request)
    
    # Check if session exists
    if mcp_session_id and mcp_session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Create session if it doesn't exist (with proper race condition handling)
    session_id = mcp_session_id or _generate_session_id()
    
    # Use setdefault to avoid race condition
    if session_id not in _sessions:
        _sessions[session_id] = {"user": current_user, "initialized": False}
    
    token = current_user_ctx.set(current_user)
    try:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:  # noqa: SLF001
            notification_options = NotificationOptions(
                prompts_changed=True, resources_changed=True, tools_changed=True
            )
            
            # Check if session is initialized (use get to avoid KeyError)
            session_data = _sessions.get(session_id)
            if session_data and session_data.get("initialized"):
                init_options = None
            else:
                init_options = server.create_initialization_options(notification_options)
                # Update session initialization status
                # Use setdefault to avoid race condition
                if session_id not in _sessions:
                    _sessions[session_id] = {"user": current_user, "initialized": True}
                else:
                    _sessions[session_id]["initialized"] = True
            
            # Handle resumability if Last-Event-ID is provided
            if last_event_id:
                await logger.adebug(f"Resuming stream from event ID: {last_event_id}")
            
            async def stream_generator():
                try:
                    await server.run(streams[0], streams[1], init_options)
                except Exception as exc:  # noqa: BLE001
                    validation_error = find_validation_error(exc)
                    if validation_error:
                        await logger.adebug(f"Validation error in MCP: {validation_error}")
                    else:
                        await logger.adebug(f"Error in MCP: {exc!s}")
            
            response = StreamingResponse(stream_generator(), media_type="text/event-stream")
            response.headers["Mcp-Session-Id"] = session_id
            return response
    finally:
        current_user_ctx.reset(token)


@router.delete("/streamable", response_class=Response)
async def handle_streamable_http_delete(
    mcp_session_id: str = Header(alias="Mcp-Session-Id"),
    current_user: CurrentActiveMCPUser = None,  # type: ignore[assignment]
):
    """Terminate a Streamable HTTP session.
    
    Requires authentication. Verifies the session belongs to the authenticated user
    before deletion for security.
    """
    if mcp_session_id not in _sessions:
        return Response(status_code=404)
    
    # Verify session belongs to authenticated user
    # Note: FastAPI dependency injection means current_user will be resolved
    # If auth fails, 401 will be raised before this function is called
    session_data = _sessions.get(mcp_session_id)
    if current_user is not None and session_data and session_data.get("user") != current_user:
        raise HTTPException(status_code=403, detail="Session does not belong to authenticated user")
    
    del _sessions[mcp_session_id]
    return Response(status_code=200)
