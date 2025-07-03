# FastMCP Research and Implementation Plan

## What is MCP (Model Context Protocol)?

The Model Context Protocol (MCP) is a standardized way to provide context and tools to Large Language Models (LLMs). It allows servers to expose:

- **Resources**: Data endpoints (like GET requests) that load information into context
- **Tools**: Functionality endpoints (like POST requests) that execute actions  
- **Prompts**: Reusable interaction templates

## FastMCP Library

FastMCP is a Python library that simplifies building MCP servers using decorators and a high-level, Pythonic interface.

### Key Features:
- **Servers**: Create servers with minimal boilerplate using decorators
- **Clients**: Interact with MCP servers programmatically
- **Proxy**: Existing servers to modify configuration or transport
- **Compose**: Servers into complex applications
- **OpenAPI Generation**: Generate servers from OpenAPI specs or FastAPI objects

### Current Version: 2.10.1

## Langflow's Current Serve Command

Langflow already has a `serve` command that:
- Serves individual Langflow graphs/flows as REST API endpoints
- Supports authentication via API keys
- Can serve single flows or multiple flows from directories
- Supports GitHub repositories and remote scripts
- Uses FastAPI under the hood

### API Structure:
- `GET /flows` - List all flows
- `POST /flows/{id}/run` - Execute specific flow
- `GET /flows/{id}/info` - Flow metadata
- `GET /health` - Health check

## Implementation Plan

### 1. Add MCP Dependencies
- Ensure `fastmcp>=2.10.1` is properly installed
- Add any additional MCP-related dependencies if needed

### 2. Extend Serve Command Options
Add new CLI options to the serve command:
- `--mcp` / `--no-mcp` - Enable/disable MCP mode
- `--mcp-transport` - Transport type (stdio, sse, websocket)
- `--mcp-name` - MCP server name

### 3. Create MCP Server Wrapper
Create a new module that:
- Wraps existing Langflow flows as MCP tools
- Exposes flow metadata as MCP resources
- Provides MCP prompts for flow interaction
- Handles the conversion between MCP protocol and Langflow's execution model

### 4. MCP Integration Points

#### Tools (Execute Actions)
- Each Langflow flow becomes an MCP tool
- Tool name: flow ID or title
- Tool description: flow description/metadata
- Tool parameters: flow inputs
- Tool execution: runs the flow and returns results

#### Resources (Load Information)
- Flow metadata as resources (e.g., `flow://flows/{id}/info`)
- Flow schema information (inputs/outputs)
- Available flows list

#### Prompts (Interaction Templates)
- Standard prompts for flow execution
- Help prompts for understanding flow capabilities
- Error handling prompts

### 5. Transport Support
Support multiple MCP transports:
- **Stdio**: For local tool integration
- **SSE**: For web-based integrations
- **WebSocket**: For real-time applications

### 6. Backward Compatibility
Ensure the existing REST API functionality remains unchanged when MCP is disabled.

## Implementation Benefits

1. **LLM Integration**: Langflow flows can be directly used by LLM applications
2. **Standardized Protocol**: Uses the industry-standard MCP protocol
3. **Tool Discovery**: LLMs can automatically discover and use Langflow capabilities
4. **Flexible Deployment**: Support multiple transport mechanisms
5. **Ecosystem Compatibility**: Works with any MCP-compatible LLM client

## Example Usage

```bash
# Start MCP server with stdio transport
langflow serve my_flow.py --mcp --mcp-transport stdio

# Start MCP server with SSE transport
langflow serve ./flows_folder --mcp --mcp-transport sse --port 8000

# Traditional REST API (existing behavior)
langflow serve my_flow.py --no-mcp
```

## MCP Protocol Example

When a flow is exposed via MCP:

```python
# MCP Tool Definition
{
    "name": "process_document", 
    "description": "Process documents using AI analysis",
    "inputSchema": {
        "type": "object",
        "properties": {
            "document_text": {"type": "string"},
            "analysis_type": {"type": "string"}
        }
    }
}

# MCP Resource Definition  
{
    "uri": "flow://flows/process_document/info",
    "name": "Document Processing Flow Info",
    "description": "Metadata about the document processing flow"
}
```