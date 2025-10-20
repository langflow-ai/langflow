# Langflow Agentic MCP Server

This MCP (Model Context Protocol) server exposes Langflow's agentic functions as tools that can be used by AI assistants like Claude.

## Overview

The server uses [FastMCP](https://github.com/jlowin/fastmcp) to expose template search functions as MCP tools with simple decorator-based registration.

## Installation

First, ensure you have FastMCP installed:

```bash
pip install fastmcp
# or
uv pip install fastmcp
```

## Available Tools

The server exposes four tools:

1. **search_templates** - Search and filter templates by query, tags, and fields
2. **get_template** - Get a specific template by its UUID
3. **list_all_tags** - Get all unique tags across templates
4. **count_templates** - Get the total count of available templates

## Usage

### Running the Server

#### Option 1: Using the CLI

```bash
# Run the server
python -m langflow.agentic.mcp.cli

# List available tools
python -m langflow.agentic.mcp.cli --list-tools

# Show version
python -m langflow.agentic.mcp.cli --version
```

#### Option 2: Direct Python execution

```bash
python -m langflow.agentic.mcp.server
```

#### Option 3: Using FastMCP CLI

```bash
# Run with FastMCP's built-in CLI
fastmcp run langflow.agentic.mcp.server:mcp
```

### Connecting to the Server

The FastMCP server uses stdio transport by default, which is perfect for integration with Claude Desktop and other MCP clients.

#### Claude Desktop Configuration

Add this to your Claude Desktop MCP settings:

```json
{
  "mcpServers": {
    "langflow-agentic": {
      "command": "python",
      "args": [
        "-m",
        "langflow.agentic.mcp.server"
      ],
      "cwd": "/path/to/langflow/src/backend/base"
    }
  }
}
```

Or use the `fastmcp` command:

```json
{
  "mcpServers": {
    "langflow-agentic": {
      "command": "fastmcp",
      "args": [
        "run",
        "langflow.agentic.mcp.server:mcp"
      ],
      "cwd": "/path/to/langflow/src/backend/base"
    }
  }
}
```

## Tool Examples

### search_templates

Search for templates with flexible filtering:

```python
# Get all templates with only specific fields
search_templates(fields=["id", "name", "description"])

# Search for templates containing "agent"
search_templates(query="agent", fields=["id", "name", "tags"])

# Get templates by tags
search_templates(tags=["chatbots", "rag"], fields=["name", "description"])

# Combine query and tag filtering
search_templates(
    query="document",
    tags=["rag"],
    fields=["id", "name", "description", "tags"]
)
```

### get_template

Get a specific template by ID:

```python
# Get full template data
get_template(template_id="0dbee653-41ae-4e51-af2e-55757fb24be3")

# Get only specific fields
get_template(
    template_id="0dbee653-41ae-4e51-af2e-55757fb24be3",
    fields=["name", "description", "tags"]
)
```

### list_all_tags

Get all available tags:

```python
# Returns sorted list like: ['agents', 'chatbots', 'rag', 'tools', ...]
list_all_tags()
```

### count_templates

Get the total number of templates:

```python
# Returns integer count
count_templates()
```

## Architecture

### FastMCP Decorator Pattern

The server uses FastMCP's `@mcp.tool()` decorator to automatically register functions as MCP tools:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("langflow-agentic")

@mcp.tool()
def search_templates(query: str | None = None, ...) -> list[dict[str, Any]]:
    """Tool documentation becomes the MCP tool description."""
    return list_templates(query=query, ...)
```

### Key Features

- **Automatic Schema Generation**: FastMCP automatically generates JSON schemas from type hints
- **Simple Registration**: Just decorate functions with `@mcp.tool()`
- **Standard Transport**: Uses stdio transport for compatibility with MCP clients
- **Zero Configuration**: No manual tool registration or schema writing needed

## Development

### Adding New Tools

To add new tools to the MCP server:

1. Create your function in the appropriate module (e.g., `langflow/agentic/utils/`)
2. Import it in `langflow/agentic/mcp/server.py`
3. Create a wrapper function with the `@mcp.tool()` decorator
4. Add comprehensive docstrings (they become tool descriptions)

Example:

```python
from langflow.agentic.utils.your_module import your_function

@mcp.tool()
def your_tool_name(param1: str, param2: int = 10) -> dict:
    """Your tool description here.

    This becomes the MCP tool description that AI assistants see.
    """
    return your_function(param1, param2)
```

### Testing

Run the server locally to test:

```bash
# Start the server
python -m langflow.agentic.mcp.cli

# In another terminal, test with MCP client
# (or use Claude Desktop with the config above)
```

## Comparison with Discovery-based Approach

This FastMCP implementation is simpler than a custom discovery-based approach:

**FastMCP Benefits:**
- Less code to maintain
- Automatic schema generation from type hints
- Standard MCP implementation
- Built-in CLI and utilities
- Well-documented and tested library

**Trade-offs:**
- Requires explicit wrapper functions for each tool
- Less dynamic than auto-discovery
- Requires fastmcp dependency

## Dependencies

- `fastmcp` - FastMCP library for MCP server creation
- `langflow` - Parent Langflow installation

## References

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Claude Desktop MCP Integration](https://docs.anthropic.com/claude/docs/mcp)
