# Langflow Agentic MCP Server

An MCP (Model Context Protocol) server that automatically exposes functions from the Langflow agentic folder as tools for AI agents and assistants.

## ✨ Features

- **🔄 Multiple Protocols**: MCP (stdio), HTTP/SSE, and WebSocket
- **📡 HTTP Streaming**: Server-Sent Events (SSE) for real-time updates
- **🔍 Automatic Discovery**: Automatically discovers and exposes functions
- **⚙️ Configurable**: Easy configuration to enable/disable specific tools
- **🛡️ Type-Safe**: Automatically generates JSON schemas from Python type hints
- **🔌 Extensible**: Add new modules and functions without changing server code
- **📖 Self-Documenting**: Uses function docstrings for tool descriptions
- **🌐 Network Ready**: HTTP and WebSocket servers for web integration

## Architecture

```
langflow/agentic/
├── mcp/
│   ├── __init__.py          # Package exports
│   ├── config.py            # Tool configuration
│   ├── discovery.py         # Automatic function discovery
│   ├── server.py            # MCP server implementation
│   ├── cli.py               # Command-line interface
│   └── README.md            # This file
├── utils/
│   └── template_search.py   # Functions exposed as tools
└── ... (other modules)
```

## Installation

The MCP server is part of the Langflow installation. No additional packages are required.

## Usage

### Running the Server

```bash
# Run the MCP server
python -m langflow.agentic.mcp.server

# Or using the CLI
python -m langflow.agentic.mcp.cli
```

### Listing Available Tools

```bash
# List tools in human-readable format
python -m langflow.agentic.mcp.cli --list-tools

# List tools in JSON format
python -m langflow.agentic.mcp.cli --list-tools --json
```

### Check Server Version

```bash
python -m langflow.agentic.mcp.cli --version
```

## Configuration

### Adding New Tools

To expose new functions as MCP tools, edit `config.py`:

```python
TOOL_CONFIGS = {
    "utils.template_search": {
        "list_templates": ToolConfig(
            enabled=True,
            name="list_templates",
            description="Search and list Langflow templates",
        ),
        # Add more functions here
    },
    # Add new modules here
    "core.orchestrator": {
        "execute_workflow": ToolConfig(
            enabled=True,
            name="execute_workflow",
            description="Execute a Langflow workflow",
        ),
    },
}
```

### Disabling Tools

To disable a tool without removing it from the code:

```python
"function_name": ToolConfig(
    enabled=False,  # This tool will not be exposed
),
```

### Custom Tool Names

Override the function name for the MCP tool:

```python
"internal_function_name": ToolConfig(
    enabled=True,
    name="user_friendly_name",  # Use this name in MCP
),
```

## Available Tools

### Template Search Tools

#### `list_templates`
Search and list Langflow templates with optional filtering.

**Parameters:**
- `query` (string, optional): Search term to filter templates
- `fields` (array, optional): List of fields to return
- `tags` (array, optional): Filter by tags
- `starter_projects_path` (string, optional): Custom path to templates

**Example:**
```json
{
  "query": "agent",
  "tags": ["agents", "rag"],
  "fields": ["id", "name", "description"]
}
```

#### `get_template_by_id`
Get a specific template by its UUID.

**Parameters:**
- `template_id` (string, required): The template UUID
- `fields` (array, optional): List of fields to return
- `starter_projects_path` (string, optional): Custom path to templates

**Example:**
```json
{
  "template_id": "0dbee653-41ae-4e51-af2e-55757fb24be3",
  "fields": ["name", "description", "tags"]
}
```

#### `get_all_tags`
Get all unique tags across templates.

**Parameters:**
- `starter_projects_path` (string, optional): Custom path to templates

**Example:**
```json
{}
```

#### `get_templates_count`
Get the total count of available templates.

**Parameters:**
- `starter_projects_path` (string, optional): Custom path to templates

**Example:**
```json
{}
```

## Integration with Claude Desktop

Add to your Claude Desktop MCP configuration:

### macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
### Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "langflow-agentic": {
      "command": "python",
      "args": [
        "-m",
        "langflow.agentic.mcp.server"
      ],
      "env": {
        "PYTHONPATH": "/path/to/langflow/src/backend/base"
      }
    }
  }
}
```

## Development

### Adding a New Module

1. Create your module in the agentic folder:
```python
# langflow/agentic/new_module.py
def my_function(param1: str, param2: int = 10) -> dict:
    """Description of what this function does.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Result dictionary
    """
    return {"result": "success"}
```

2. Add to `config.py`:
```python
TOOL_CONFIGS = {
    "new_module": {
        "my_function": ToolConfig(
            enabled=True,
            description="My awesome function",
        ),
    },
}
```

3. The function is now automatically available as an MCP tool!

### Schema Generation

The server automatically generates JSON schemas from Python type hints:

```python
def example(
    text: str,              # → "type": "string"
    count: int,             # → "type": "integer"
    ratio: float,           # → "type": "number"
    enabled: bool,          # → "type": "boolean"
    items: list,            # → "type": "array"
    data: dict,             # → "type": "object"
    optional: str | None = None,  # → optional parameter
) -> dict:
    """Function docstring becomes tool description."""
    pass
```

### Best Practices

1. **Use Type Hints**: Always provide type hints for parameters
2. **Write Docstrings**: Document functions with clear docstrings
3. **Parameter Descriptions**: Include Args section in docstrings
4. **Return Types**: Specify return types
5. **Validation**: Validate inputs in your functions
6. **Error Handling**: Use clear error messages

## How It Works

1. **Configuration** (`config.py`): Defines which functions to expose
2. **Discovery** (`discovery.py`): Scans modules and extracts function metadata
3. **Schema Generation**: Converts Python type hints to JSON schemas
4. **Server** (`server.py`): Implements MCP protocol and handles tool calls
5. **Execution**: Routes tool calls to the appropriate Python functions

## Automatic Features

The server automatically:
- ✅ Discovers functions from configured modules
- ✅ Generates JSON schemas from type hints
- ✅ Extracts descriptions from docstrings
- ✅ Handles optional parameters
- ✅ Validates required parameters
- ✅ Formats responses as JSON
- ✅ Catches and reports errors

## Testing the Server

```python
# Get server information
from langflow.agentic.mcp.server import get_server_info

info = get_server_info()
print(f"Server: {info['name']} v{info['version']}")
print(f"Available tools: {len(info['tools'])}")

# List all tools
from langflow.agentic.mcp.discovery import get_tool_list

tools = get_tool_list()
for tool in tools:
    print(f"- {tool['name']}: {tool['description']}")
```

## Troubleshooting

### Tool Not Appearing

Check:
1. Is the function configured in `config.py`?
2. Is `enabled=True` in the ToolConfig?
3. Does the function have a docstring?
4. Is the module importable?

### Schema Issues

- Ensure all parameters have type hints
- Use `| None` for optional parameters
- Document parameters in docstring Args section

### Import Errors

- Check `PYTHONPATH` includes Langflow base directory
- Verify module path in `config.py` is correct
- Ensure all dependencies are installed

## Future Enhancements

Planned features:
- [ ] Hot reload on configuration changes
- [ ] Async function support
- [ ] Custom validators for parameters
- [ ] Tool usage analytics
- [ ] Rate limiting
- [ ] Authentication/authorization
- [ ] Multi-language support
- [ ] GraphQL-style field selection

## Contributing

To add new tools to the MCP server:

1. Write your function in an appropriate module
2. Add type hints and docstrings
3. Configure in `config.py`
4. Test with `--list-tools`
5. Document in this README

## License

Part of the Langflow project.
