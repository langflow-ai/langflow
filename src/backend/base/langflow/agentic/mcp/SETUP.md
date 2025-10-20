## 🚀 Langflow Agentic MCP Server Setup Guide

Complete setup guide for the Langflow Agentic MCP Server.

## 📁 Folder Structure

```
langflow/agentic/
├── mcp/                                    # MCP Server implementation
│   ├── __init__.py                         # Package exports
│   ├── config.py                           # ⚙️ Tool configuration
│   ├── discovery.py                        # 🔍 Automatic function discovery
│   ├── server.py                           # 🖥️ MCP server implementation
│   ├── cli.py                              # 💻 Command-line interface
│   ├── test_server.py                      # 🧪 Test suite
│   ├── README.md                           # 📖 Documentation
│   ├── SETUP.md                            # 📋 This file
│   └── claude_desktop_config.example.json  # ⚙️ Claude Desktop config example
├── utils/
│   ├── __init__.py
│   └── template_search.py                  # ✅ Functions exposed as tools
└── ... (other modules)
```

## 🎯 How It Works

### 1. Configuration (`config.py`)

Define which functions to expose as MCP tools:

```python
TOOL_CONFIGS = {
    "utils.template_search": {
        "list_templates": ToolConfig(
            enabled=True,  # ✅ Expose this function
            name="list_templates",
            description="Search and list Langflow templates",
        ),
        "get_template_by_id": ToolConfig(
            enabled=True,  # ✅ Expose this function
        ),
        "internal_helper": ToolConfig(
            enabled=False,  # ❌ Skip this function
        ),
    },
}
```

### 2. Automatic Discovery (`discovery.py`)

The discovery system automatically:
- 📦 Imports configured modules
- 🔍 Finds all public functions (non-private)
- 🏷️ Extracts type hints and docstrings
- 📝 Generates JSON schemas
- ✅ Filters based on configuration

### 3. Server (`server.py`)

The MCP server:
- 🌐 Implements MCP protocol
- 📋 Lists available tools
- ⚙️ Executes tool calls
- 🛡️ Handles errors
- 📊 Returns formatted results

## ✨ Key Features

### ✅ Automatic Tool Registration

Add a new function to the agentic folder:

```python
# langflow/agentic/new_module.py
def my_new_function(param1: str, param2: int = 10) -> dict:
    """Do something awesome.

    Args:
        param1: Description of param1
        param2: Description of param2 (default: 10)

    Returns:
        Result dictionary
    """
    return {"result": "success", "param1": param1, "param2": param2}
```

Configure it in `config.py`:

```python
TOOL_CONFIGS = {
    "new_module": {
        "my_new_function": ToolConfig(enabled=True),
    },
}
```

**That's it!** The function is now available as an MCP tool.

### ⚙️ Configuration Options

```python
ToolConfig(
    enabled=True,                    # Enable/disable tool
    name="custom_name",              # Custom tool name (optional)
    description="Custom desc",       # Custom description (optional)
    parameters_schema={...}          # Custom JSON schema (optional)
)
```

### 🔍 Automatic Schema Generation

Type hints are automatically converted to JSON schemas:

```python
def example(
    text: str,                  # → "type": "string"
    count: int,                 # → "type": "integer"
    ratio: float,               # → "type": "number"
    enabled: bool,              # → "type": "boolean"
    items: list,                # → "type": "array"
    data: dict,                 # → "type": "object"
    optional: str | None = None # → optional parameter
):
    """Docstring becomes tool description."""
    pass
```

## 📋 Currently Available Tools

### 1. `list_templates`
Search and filter Langflow templates.

**Parameters:**
- `query` (string, optional): Search term
- `fields` (array, optional): Fields to return
- `tags` (array, optional): Filter by tags
- `starter_projects_path` (string, optional): Custom path

### 2. `get_template_by_id`
Get a specific template by UUID.

**Parameters:**
- `template_id` (string, required): Template UUID
- `fields` (array, optional): Fields to return
- `starter_projects_path` (string, optional): Custom path

### 3. `get_all_tags`
Get all unique tags.

**Parameters:**
- `starter_projects_path` (string, optional): Custom path

### 4. `get_templates_count`
Get total template count.

**Parameters:**
- `starter_projects_path` (string, optional): Custom path

## 🔧 Usage

### Running the Server

```bash
# Run the MCP server
cd /Users/edwin.jose/Documents/GitHub/langflow/src/backend/base
python -m langflow.agentic.mcp.server
```

### Testing the Server

```bash
# Run test suite
python -m langflow.agentic.mcp.test_server

# List available tools
python -m langflow.agentic.mcp.cli --list-tools

# List tools in JSON
python -m langflow.agentic.mcp.cli --list-tools --json

# Check version
python -m langflow.agentic.mcp.cli --version
```

### Integration with Claude Desktop

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

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
        "PYTHONPATH": "/Users/edwin.jose/Documents/GitHub/langflow/src/backend/base"
      }
    }
  }
}
```

## ➕ Adding New Tools

### Step 1: Write Your Function

```python
# langflow/agentic/workflows/runner.py
def execute_workflow(
    workflow_id: str,
    inputs: dict,
    config: dict | None = None
) -> dict:
    """Execute a Langflow workflow.

    Args:
        workflow_id: The workflow UUID to execute
        inputs: Input data for the workflow
        config: Optional configuration settings

    Returns:
        Workflow execution results
    """
    # Implementation here
    return {"status": "success", "outputs": {}}
```

### Step 2: Configure in `config.py`

```python
TOOL_CONFIGS = {
    # ... existing configs ...

    "workflows.runner": {
        "execute_workflow": ToolConfig(
            enabled=True,
            description="Execute a Langflow workflow with given inputs",
        ),
    },
}
```

### Step 3: Test

```bash
python -m langflow.agentic.mcp.cli --list-tools
```

You should see your new tool in the list!

## 🎯 Best Practices

### ✅ DO

- **Use type hints** for all parameters and return values
- **Write clear docstrings** with Args and Returns sections
- **Validate inputs** in your functions
- **Handle errors gracefully** with clear messages
- **Return JSON-serializable** data structures
- **Document parameter descriptions** in Args section
- **Use meaningful function names**

### ❌ DON'T

- Don't expose internal helper functions (use `enabled=False`)
- Don't use complex custom types without JSON serialization
- Don't forget to handle edge cases
- Don't return objects that can't be serialized to JSON
- Don't skip type hints
- Don't omit docstrings

## 🧪 Testing Your Tools

```python
# Test tool discovery
from langflow.agentic.mcp.discovery import discover_all_tools

tools = discover_all_tools()
print(f"Found {len(tools)} tools")

# Test a specific tool
if "my_tool" in tools:
    func = tools["my_tool"]["function"]
    result = func(param1="test", param2=42)
    print(f"Result: {result}")
```

## 🔍 Debugging

### Check if tool is discovered

```bash
python -m langflow.agentic.mcp.cli --list-tools | grep "my_tool"
```

### Verify configuration

```python
from langflow.agentic.mcp.config import is_tool_enabled

enabled = is_tool_enabled("module.path", "function_name")
print(f"Tool enabled: {enabled}")
```

### Test function import

```python
from langflow.agentic.mcp.discovery import discover_functions

functions = discover_functions("module.path")
print(f"Functions: {list(functions.keys())}")
```

## 📊 Current Status

**✅ Working:**
- Automatic function discovery
- Schema generation from type hints
- Tool configuration system
- MCP protocol implementation
- CLI interface
- Test suite
- 4 template search tools

**🔄 In Progress:**
- More agentic functions
- Workflow execution tools
- State management tools

**🎯 Planned:**
- Async function support
- Hot reload on config changes
- Authentication/authorization
- Rate limiting
- Tool usage analytics

## 🆘 Troubleshooting

### Tool not appearing

**Check:**
1. Is it in `config.py` with `enabled=True`?
2. Does the module import correctly?
3. Is the function public (not starting with `_`)?
4. Does it have type hints?

### Schema generation issues

**Check:**
1. All parameters have type hints?
2. Using supported types (str, int, float, bool, list, dict)?
3. Optional parameters use `| None` syntax?

### Import errors

**Check:**
1. Is `PYTHONPATH` set correctly?
2. Are all dependencies installed?
3. Is the module path in `config.py` correct?

### Execution errors

**Check:**
1. Function validates inputs?
2. Returns JSON-serializable data?
3. Handles exceptions gracefully?

## 📚 Additional Resources

- **MCP Protocol**: https://modelcontextprotocol.io/
- **Type Hints**: https://docs.python.org/3/library/typing.html
- **JSON Schema**: https://json-schema.org/

## 🎉 Success Criteria

Your tool is successfully integrated when:

✅ It appears in `--list-tools` output
✅ Schema is correctly generated
✅ Test execution completes without errors
✅ Returns expected JSON format
✅ Docstring appears as description
✅ Parameters are correctly typed

## 🚀 Next Steps

1. **Add more tools** to the agentic folder
2. **Configure them** in `config.py`
3. **Test** with the test suite
4. **Integrate** with Claude Desktop
5. **Use** in AI workflows!

The MCP server will automatically discover and expose your new functions as tools! 🎯
