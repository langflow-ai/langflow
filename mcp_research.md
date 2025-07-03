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

## Implementation Status

✅ **COMPLETED**: Full MCP support has been implemented for Langflow's serve command!

### What's Been Implemented:

1. **✅ Dependencies Added**: `fastmcp>=2.10.1` added to pyproject.toml
2. **✅ CLI Options Extended**: New MCP flags added to serve command:
   - `--mcp/--no-mcp`: Enable/disable MCP mode
   - `--mcp-transport`: Choose transport (stdio, sse, websocket)
   - `--mcp-name`: Custom MCP server name

3. **✅ MCP Server Module**: Created `src/backend/base/langflow/cli/mcp_server.py` with:
   - Flow-to-MCP tool conversion
   - MCP resources for flow metadata
   - MCP prompts for help and troubleshooting
   - Support for multiple transports

4. **✅ CLI Integration**: Updated `src/backend/base/langflow/cli/commands.py`:
   - MCP mode validation and execution
   - Backward compatibility with existing REST API mode
   - Error handling and user feedback

5. **✅ Comprehensive Tests**: Added extensive test coverage:
   - CLI MCP functionality tests in `src/backend/tests/unit/test_cli.py`
   - MCP server unit tests in `src/backend/tests/unit/test_mcp_server.py`
   - Mocking and integration testing

6. **✅ Example Script**: Created `examples/mcp_serve_example.py` demonstrating usage

### Features:

- **🎯 Flow as Tools**: Each Langflow flow becomes an MCP tool
- **📚 Metadata Resources**: Flow info and schemas available as MCP resources  
- **❓ Help Prompts**: Built-in help and troubleshooting via MCP prompts
- **🚀 Multiple Transports**: stdio, SSE, and websocket support
- **🔄 Backward Compatible**: Existing REST API functionality unchanged
- **🔐 Security**: MCP mode doesn't require API keys (different security model)

## Example Usage

```bash
# Start MCP server with stdio transport (for local LLM tools)
langflow serve my_flow.py --mcp --mcp-transport stdio

# Start MCP server with SSE transport (for web-based LLM clients)
langflow serve ./flows_folder --mcp --mcp-transport sse --port 8000

# Start MCP server with custom name
langflow serve my_flow.py --mcp --mcp-name "My Custom AI Tools"

# Traditional REST API (existing behavior - still works)
langflow serve my_flow.py --no-mcp
```

## MCP Protocol Example

When a flow is exposed via MCP:

```python
# MCP Tool Definition
{
    "name": "execute_document_processor", 
    "description": "Process documents using AI analysis",
    "inputSchema": {
        "type": "object",
        "properties": {
            "input_value": {"type": "string"},
            "tweaks": {"type": "object", "optional": True}
        }
    }
}

# MCP Resource Definitions
{
    "uri": "flow://flows",
    "name": "All Available Flows",
    "description": "List all flows with metadata"
}

{
    "uri": "flow://flows/document_processor/info",
    "name": "Document Processing Flow Info", 
    "description": "Metadata about the document processing flow"
}

{
    "uri": "flow://flows/document_processor/schema",
    "name": "Flow Input/Output Schema",
    "description": "Schema information for the flow"
}
```

## Testing

Run the comprehensive test suite:

```bash
# Run all MCP tests
pytest src/backend/tests/unit/test_cli.py::TestMCPServeCommand -v
pytest src/backend/tests/unit/test_mcp_server.py -v

# Run specific MCP functionality tests  
pytest src/backend/tests/unit/test_cli.py::TestMCPServeCommand::test_mcp_transport_validation -v
pytest src/backend/tests/unit/test_mcp_server.py::TestMCPServerCreation::test_create_mcp_server_basic -v
```