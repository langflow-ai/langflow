# Langflow Agentic MCP Server - Setup Guide

This guide walks you through setting up and using the Langflow Agentic MCP Server with FastMCP.

## Prerequisites

- Python 3.10 or higher
- Langflow installed (from this repository)
- FastMCP library

## Installation

### 1. Install Dependencies

If you're using `uv` (recommended):

```bash
uv pip install fastmcp
```

Or with regular pip:

```bash
pip install fastmcp
```

### 2. Verify Installation

Test that the server imports correctly:

```bash
python -c "from langflow.agentic.mcp.server import mcp; print('✓ Server ready')"
```

List available tools:

```bash
python -m langflow.agentic.mcp.cli --list-tools
```

You should see:
```
Available MCP Tools:
============================================================
  - search_templates
  - get_template
  - list_all_tags
  - count_templates
============================================================
```

## Running the Server

### Method 1: Using the CLI (Recommended)

```bash
# Start the server
python -m langflow.agentic.mcp.cli

# Or from the mcp directory
cd langflow/agentic/mcp
python cli.py
```

### Method 2: Direct Module Execution

```bash
python -m langflow.agentic.mcp.server
```

### Method 3: Using FastMCP CLI

```bash
fastmcp run langflow.agentic.mcp.server:mcp
```

### Method 4: Development Mode

For development and testing, run the server directly:

```bash
cd /path/to/langflow/src/backend/base
python -c "from langflow.agentic.mcp.server import mcp; mcp.run()"
```

## Connecting to Claude Desktop

### Configuration

1. Locate your Claude Desktop config file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

2. Add the Langflow Agentic MCP server to your config:

```json
{
  "mcpServers": {
    "langflow-agentic": {
      "command": "python",
      "args": [
        "-m",
        "langflow.agentic.mcp.cli"
      ],
      "cwd": "/path/to/langflow/src/backend/base",
      "env": {
        "PYTHONPATH": "/path/to/langflow/src/backend/base"
      }
    }
  }
}
```

**Important**: Replace `/path/to/langflow` with your actual Langflow installation path.

### Alternative: Using FastMCP Command

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

### Alternative: Using UV

If you're using `uv` for Python environment management:

```json
{
  "mcpServers": {
    "langflow-agentic": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "-m",
        "langflow.agentic.mcp.cli"
      ],
      "cwd": "/path/to/langflow"
    }
  }
}
```

### Verify Connection

1. Restart Claude Desktop after editing the config
2. Open a new conversation
3. Look for the 🔌 tools icon or mention of available tools
4. Try asking: "What Langflow templates are available?"

Claude should be able to use the MCP tools to search and retrieve template information.

## Testing the Server

### Run Unit Tests

```bash
# From the base directory
uv run pytest langflow/agentic/mcp/test_server.py -v

# Or with regular pytest
pytest langflow/agentic/mcp/test_server.py -v
```

Expected output:
```
18 passed in X.XXs
```

### Run Example Usage

```bash
python -m langflow.agentic.mcp.example_usage
```

This will demonstrate all four MCP tools with real data.

### Manual Testing

Test the tool functions directly in Python:

```python
from langflow.agentic.mcp.server import (
    search_templates,
    get_template,
    list_all_tags,
    count_templates
)

# Count templates
print(f"Total templates: {count_templates()}")

# Get all tags
tags = list_all_tags()
print(f"Available tags: {tags}")

# Search for templates
templates = search_templates(query="agent", fields=["name", "description"])
for t in templates:
    print(f"- {t['name']}")

# Get specific template
template = get_template(
    template_id="0dbee653-41ae-4e51-af2e-55757fb24be3",
    fields=["name", "description"]
)
print(f"Template: {template['name']}")
```

## Troubleshooting

### Issue: Module not found

**Error**: `ModuleNotFoundError: No module named 'langflow'`

**Solution**:
- Ensure you're running from the correct directory (`langflow/src/backend/base`)
- Set PYTHONPATH: `export PYTHONPATH=/path/to/langflow/src/backend/base`
- Or install Langflow in development mode: `pip install -e .`

### Issue: FastMCP not found

**Error**: `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`

**Solution**: Install FastMCP:
```bash
pip install fastmcp
# or
uv pip install fastmcp
```

### Issue: Templates not found

**Error**: `FileNotFoundError: Starter projects directory not found`

**Solution**:
- Verify you're in the correct Langflow directory structure
- The server expects templates at: `langflow/initial_setup/starter_projects/`
- Check the path exists: `ls langflow/initial_setup/starter_projects/`

### Issue: Claude Desktop not detecting server

**Troubleshooting steps**:
1. Verify config file path and syntax (must be valid JSON)
2. Check that the `cwd` path is correct and absolute
3. Test the server runs standalone: `python -m langflow.agentic.mcp.cli --list-tools`
4. Check Claude Desktop logs for errors
5. Restart Claude Desktop completely (quit and relaunch)

### Issue: Import errors in server.py

**Error**: Import errors when running the server

**Solution**: Ensure all dependencies are installed:
```bash
# From langflow root
pip install -e src/backend/base
# or
uv pip install -e src/backend/base
```

## Development

### Adding New Tools

To add a new tool to the MCP server:

1. Create your function in the appropriate module:
```python
# langflow/agentic/utils/your_module.py
def your_new_function(param1: str, param2: int = 10) -> dict:
    """Your function documentation."""
    # Implementation
    return {"result": "data"}
```

2. Import and decorate in `server.py`:
```python
from langflow.agentic.utils.your_module import your_new_function

@mcp.tool()
def your_tool_name(param1: str, param2: int = 10) -> dict:
    """Tool description for AI assistants.

    This docstring becomes the tool description in MCP.
    """
    return your_new_function(param1, param2)
```

3. Test your new tool:
```bash
python -m langflow.agentic.mcp.cli --list-tools
```

### Running in Development Mode

For rapid development and testing:

```bash
# Start server with auto-reload (if supported by your IDE)
python -m langflow.agentic.mcp.cli

# Or use FastMCP's development features
fastmcp dev langflow.agentic.mcp.server:mcp
```

## Architecture

### Server Structure

```
langflow/agentic/mcp/
├── __init__.py           # Package initialization
├── server.py             # FastMCP server with @mcp.tool decorators
├── cli.py                # Command-line interface
├── test_server.py        # Unit tests
├── example_usage.py      # Example tool usage
├── README.md             # Main documentation
└── SETUP.md             # This setup guide
```

### Tool Function Pattern

Each MCP tool follows this pattern:

```python
@mcp.tool()
def tool_name(param: Type, optional: Type | None = None) -> ReturnType:
    """Clear description for AI assistant.

    Args:
        param: Parameter description
        optional: Optional parameter description

    Returns:
        Description of return value

    Example:
        >>> result = tool_name("value")
    """
    # Call underlying implementation
    return underlying_function(param, optional)
```

Key points:
- **Decorator**: `@mcp.tool()` registers the function as an MCP tool
- **Type hints**: Required for automatic schema generation
- **Docstring**: Becomes the tool description for AI assistants
- **Wrapper pattern**: Tool functions wrap underlying implementations

## Performance Considerations

### Template Loading

The template search functions load JSON files from disk on each call. For production use, consider:

1. **Caching**: Add LRU cache for frequently accessed templates
2. **Indexing**: Pre-load templates into an in-memory index
3. **Database**: Move templates to a database for complex queries

### Concurrent Requests

FastMCP handles concurrent tool calls efficiently. No special configuration needed for multiple simultaneous requests.

## Next Steps

1. **Explore Examples**: Run `python -m langflow.agentic.mcp.example_usage`
2. **Connect to Claude**: Follow the Claude Desktop setup above
3. **Add Custom Tools**: Extend the server with your own agentic functions
4. **Read Full Docs**: See [README.md](README.md) for detailed API documentation

## Resources

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Claude Desktop MCP Guide](https://docs.anthropic.com/claude/docs/mcp)
- [Langflow Documentation](https://docs.langflow.org/)

## Support

For issues or questions:
- Check [Troubleshooting](#troubleshooting) section above
- Review test output: `pytest langflow/agentic/mcp/test_server.py -v`
- Verify installation: `python -m langflow.agentic.mcp.cli --list-tools`
