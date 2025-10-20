"""HTTP/SSE Server for Langflow Agentic MCP.

This module provides an HTTP server with Server-Sent Events (SSE) streaming
for real-time communication with clients.
"""

import asyncio
import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import SERVER_DESCRIPTION, SERVER_NAME, SERVER_VERSION
from .discovery import discover_all_tools, get_tool_list


# Pydantic models for request/response
class ToolCallRequest(BaseModel):
    """Request model for tool execution."""

    tool_name: str
    arguments: dict[str, Any]
    stream: bool = False


class ToolCallResponse(BaseModel):
    """Response model for tool execution."""

    tool_name: str
    success: bool
    result: Any | None = None
    error: str | None = None


class ServerInfo(BaseModel):
    """Server information model."""

    name: str
    version: str
    description: str
    tools_count: int


# Create FastAPI app
app = FastAPI(
    title=SERVER_NAME,
    version=SERVER_VERSION,
    description=SERVER_DESCRIPTION,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Discover tools at startup
discovered_tools = discover_all_tools()


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": SERVER_NAME,
        "version": SERVER_VERSION,
        "description": SERVER_DESCRIPTION,
        "endpoints": {
            "info": "/info",
            "tools": "/tools",
            "call": "/call",
            "stream": "/stream",
        },
    }


@app.get("/info")
async def get_info() -> ServerInfo:
    """Get server information.

    Returns:
        Server metadata including name, version, and tool count
    """
    return ServerInfo(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        description=SERVER_DESCRIPTION,
        tools_count=len(discovered_tools),
    )


@app.get("/tools")
async def list_tools() -> list[dict[str, Any]]:
    """List all available tools.

    Returns:
        List of tool metadata including names, descriptions, and schemas
    """
    return get_tool_list()


@app.post("/call")
async def call_tool(request: ToolCallRequest) -> ToolCallResponse:
    """Execute a tool with given arguments.

    Args:
        request: Tool call request with tool name and arguments

    Returns:
        Tool execution result or error

    Raises:
        HTTPException: If tool not found or execution fails
    """
    tool_name = request.tool_name

    if tool_name not in discovered_tools:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    tool_metadata = discovered_tools[tool_name]
    func = tool_metadata["function"]

    try:
        # Execute the function
        result = func(**request.arguments)

        return ToolCallResponse(
            tool_name=tool_name,
            success=True,
            result=result,
        )

    except Exception as e:
        return ToolCallResponse(
            tool_name=tool_name,
            success=False,
            error=f"{type(e).__name__}: {e!s}",
        )


@app.post("/stream")
async def stream_tool(request: ToolCallRequest) -> StreamingResponse:
    """Execute a tool and stream results using Server-Sent Events (SSE).

    Args:
        request: Tool call request with tool name and arguments

    Returns:
        Streaming response with SSE events

    Raises:
        HTTPException: If tool not found
    """
    tool_name = request.tool_name

    if tool_name not in discovered_tools:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    async def event_generator():
        """Generate SSE events for streaming response."""
        try:
            # Send start event
            yield f"data: {json.dumps({'event': 'start', 'tool': tool_name})}\n\n"

            tool_metadata = discovered_tools[tool_name]
            func = tool_metadata["function"]

            # Execute the function
            result = func(**request.arguments)

            # For now, send the complete result
            # In the future, functions could yield partial results
            yield f"data: {json.dumps({'event': 'data', 'data': result})}\n\n"

            # Send completion event
            yield f"data: {json.dumps({'event': 'done', 'success': True})}\n\n"

        except Exception as e:
            # Send error event
            error_data = {
                "event": "error",
                "error": str(e),
                "type": type(e).__name__,
            }
            yield f"data: {json.dumps(error_data)}\n\n"

        finally:
            # Send final event
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.get("/tools/{tool_name}")
async def get_tool_info(tool_name: str) -> dict[str, Any]:
    """Get detailed information about a specific tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Tool metadata including schema and description

    Raises:
        HTTPException: If tool not found
    """
    if tool_name not in discovered_tools:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    tool_metadata = discovered_tools[tool_name]

    return {
        "name": tool_name,
        "description": tool_metadata["description"],
        "schema": tool_metadata["schema"],
        "module_path": tool_metadata["module_path"],
        "function_name": tool_metadata["function_name"],
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy", "server": SERVER_NAME}


def run_http_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the HTTP server.

    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to bind to (default: 8000)
        reload: Enable auto-reload for development (default: False)
    """
    import uvicorn

    uvicorn.run(
        "langflow.agentic.mcp.http_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    run_http_server()
