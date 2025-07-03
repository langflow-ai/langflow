"""MCP (Model Context Protocol) server implementation for Langflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from langflow.graph import Graph

# Type definitions for MCP integration
class FlowInput(BaseModel):
    """Input for flow execution via MCP."""
    input_value: str = Field(description="Input value to pass to the flow")
    tweaks: dict[str, Any] | None = Field(default=None, description="Optional tweaks to apply to the flow")


class FlowOutput(BaseModel):
    """Output from flow execution via MCP."""
    result: Any = Field(description="Result from flow execution")
    execution_time: float | None = Field(default=None, description="Execution time in seconds")
    error: str | None = Field(default=None, description="Error message if execution failed")


class FlowInfo(BaseModel):
    """Flow metadata information."""
    id: str = Field(description="Flow identifier")
    title: str = Field(description="Flow title")
    description: str | None = Field(default=None, description="Flow description")
    inputs: dict[str, Any] | None = Field(default=None, description="Flow input schema")
    outputs: dict[str, Any] | None = Field(default=None, description="Flow output schema")


def create_mcp_server(
    graphs: dict[str, Graph],
    metas: dict[str, Any],
    server_name: str = "Langflow MCP Server",
    root_dir: Path | None = None,
) -> FastMCP:
    """Create an MCP server that exposes Langflow flows as tools and resources.
    
    Args:
        graphs: Dictionary of flow_id -> Graph objects
        metas: Dictionary of flow_id -> FlowMeta objects
        server_name: Name for the MCP server
        root_dir: Root directory for relative paths
        
    Returns:
        FastMCP server instance
    """
    mcp = FastMCP(server_name)

    # =====================================================================
    # MCP TOOLS - Execute flow actions
    # =====================================================================
    
    for flow_id, graph in graphs.items():
        meta = metas.get(flow_id, {})
        flow_title = getattr(meta, 'title', flow_id)
        flow_description = getattr(meta, 'description', None) or f"Execute the {flow_title} flow"
        
        # Create a dynamic tool function for this flow
        def create_flow_tool(graph_obj: Graph, flow_name: str, flow_desc: str):
            """Create a tool function for a specific flow."""
            
            @mcp.tool()
            def flow_tool(input_data: FlowInput) -> FlowOutput:
                f"""Execute the {flow_name} flow.
                
                {flow_desc}
                """
                try:
                    # Import here to avoid circular imports
                    import time
                    
                    start_time = time.time()
                    
                    # Execute the flow
                    # Note: This follows the same pattern as the REST API execution
                    result = graph_obj.run(
                        inputs={"input_value": input_data.input_value},
                        tweaks=input_data.tweaks or {}
                    )
                    
                    execution_time = time.time() - start_time
                    
                    return FlowOutput(
                        result=result,
                        execution_time=execution_time
                    )
                    
                except Exception as e:
                    return FlowOutput(
                        result=None,
                        error=str(e)
                    )
            
            # Dynamically set the function name to match the flow
            flow_tool.__name__ = f"execute_{flow_name.replace(' ', '_').replace('-', '_').lower()}"
            return flow_tool
        
        # Create and register the tool
        tool_func = create_flow_tool(graph, flow_title, flow_description)
        # The @mcp.tool() decorator is already applied in create_flow_tool

    # =====================================================================
    # MCP RESOURCES - Provide flow information and metadata
    # =====================================================================
    
    @mcp.resource("flow://flows")
    def list_flows() -> str:
        """List all available flows with their metadata."""
        flows_info = []
        for flow_id, graph in graphs.items():
            meta = metas.get(flow_id, {})
            flow_info = FlowInfo(
                id=flow_id,
                title=getattr(meta, 'title', flow_id),
                description=getattr(meta, 'description', None),
                inputs=None,  # Could be expanded to include input schema
                outputs=None  # Could be expanded to include output schema
            )
            flows_info.append(flow_info.model_dump())
        
        return json.dumps(flows_info, indent=2)
    
    @mcp.resource("flow://flows/{flow_id}/info")
    def get_flow_info(flow_id: str) -> str:
        """Get detailed information about a specific flow."""
        if flow_id not in graphs:
            return json.dumps({"error": f"Flow '{flow_id}' not found"})
        
        graph = graphs[flow_id]
        meta = metas.get(flow_id, {})
        
        flow_info = FlowInfo(
            id=flow_id,
            title=getattr(meta, 'title', flow_id),
            description=getattr(meta, 'description', None),
            inputs=None,  # Could be expanded to analyze graph inputs
            outputs=None  # Could be expanded to analyze graph outputs
        )
        
        return json.dumps(flow_info.model_dump(), indent=2)
    
    @mcp.resource("flow://flows/{flow_id}/schema")
    def get_flow_schema(flow_id: str) -> str:
        """Get the schema (inputs/outputs) for a specific flow."""
        if flow_id not in graphs:
            return json.dumps({"error": f"Flow '{flow_id}' not found"})
        
        graph = graphs[flow_id]
        
        # This could be expanded to provide detailed schema information
        # by analyzing the graph structure
        schema_info = {
            "flow_id": flow_id,
            "inputs": {
                "input_value": {
                    "type": "string",
                    "description": "Main input value for the flow"
                },
                "tweaks": {
                    "type": "object",
                    "description": "Optional parameter tweaks",
                    "optional": True
                }
            },
            "outputs": {
                "result": {
                    "type": "any",
                    "description": "Flow execution result"
                },
                "execution_time": {
                    "type": "number",
                    "description": "Execution time in seconds",
                    "optional": True
                },
                "error": {
                    "type": "string",
                    "description": "Error message if execution failed",
                    "optional": True
                }
            }
        }
        
        return json.dumps(schema_info, indent=2)

    # =====================================================================
    # MCP PROMPTS - Provide interaction templates
    # =====================================================================
    
    @mcp.prompt()
    def flow_execution_help() -> str:
        """Get help on how to execute flows via MCP."""
        flow_list = list(graphs.keys())
        return f"""
# Langflow MCP Server Help

This server exposes {len(flow_list)} Langflow flows as MCP tools.

## Available Flows:
{chr(10).join(f"- {flow_id}: {metas.get(flow_id, {}).get('title', flow_id)}" for flow_id in flow_list)}

## How to Execute Flows:
Use the corresponding MCP tool for each flow. Each tool accepts:
- input_value: The main input text/data
- tweaks: Optional parameter modifications

## Getting Flow Information:
Use these MCP resources:
- flow://flows - List all flows
- flow://flows/{{flow_id}}/info - Get flow details  
- flow://flows/{{flow_id}}/schema - Get input/output schema

## Example Usage:
1. List flows: Read resource "flow://flows"
2. Get flow info: Read resource "flow://flows/my_flow/info"
3. Execute flow: Call tool "execute_my_flow" with input_value
"""

    @mcp.prompt()
    def troubleshooting_guide() -> str:
        """Get troubleshooting help for flow execution issues."""
        return """
# Langflow MCP Troubleshooting Guide

## Common Issues:

### Flow Execution Errors:
- Check that required inputs are provided
- Verify input format matches flow expectations
- Review flow configuration and dependencies

### Tool Discovery:
- Use MCP client's tool listing functionality
- Check resource "flow://flows" for available flows
- Verify MCP server connection

### Input Formatting:
- Provide input_value as string
- Use tweaks object for parameter overrides
- Check flow schema via "flow://flows/{flow_id}/schema"

### Performance:
- Large flows may take time to execute
- Check execution_time in response
- Consider flow optimization for better performance
"""

    return mcp


def run_mcp_server(
    mcp_server: FastMCP,
    transport: str = "stdio",
    host: str = "127.0.0.1", 
    port: int = 8000,
) -> None:
    """Run the MCP server with the specified transport.
    
    Args:
        mcp_server: The FastMCP server instance
        transport: Transport type ("stdio", "sse", "websocket")
        host: Host to bind to (for network transports)
        port: Port to bind to (for network transports)
    """
    if transport == "stdio":
        # For stdio transport, run with default settings
        mcp_server.run()
    elif transport == "sse":
        # For SSE transport, run with HTTP server
        mcp_server.run(transport="sse", host=host, port=port)
    elif transport == "websocket":
        # For WebSocket transport
        mcp_server.run(transport="websocket", host=host, port=port)
    else:
        raise ValueError(f"Unsupported transport: {transport}. Use 'stdio', 'sse', or 'websocket'")