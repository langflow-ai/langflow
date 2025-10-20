# Langflow Agentic MCP Server - Structure Overview

This document provides an overview of the MCP server structure and implementation.

## Directory Structure

```
langflow/agentic/
├── mcp/                           # MCP Server implementation
│   ├── __init__.py               # Package exports
│   ├── server.py                 # FastMCP server with tool decorators
│   ├── cli.py                    # Command-line interface
│   ├── test_server.py            # Unit tests (18 tests)
│   ├── example_usage.py          # Usage examples and demos
│   ├── README.md                 # API documentation
│   ├── SETUP.md                  # Setup and configuration guide
│   └── STRUCTURE.md              # This file
│
└── utils/                         # Utility functions
    └── template_search.py        # Template search implementation
        ├── list_templates()      # Search/filter templates
        ├── get_template_by_id()  # Get specific template
        ├── get_all_tags()        # List all tags
        └── get_templates_count() # Count templates
```

## Implementation Pattern

### FastMCP Decorator Pattern

The server uses FastMCP's decorator-based approach for tool registration:

```python
from mcp.server.fastmcp import FastMCP

# Initialize server
mcp = FastMCP("langflow-agentic")

# Decorate functions to expose as tools
@mcp.tool()
def search_templates(...) -> list[dict]:
    """Tool description."""
    return list_templates(...)
```

**Benefits:**
- Simple, declarative syntax
- Automatic JSON schema generation from type hints
- Standard MCP protocol implementation
- No manual tool registration needed

## Tool Mapping

| MCP Tool Name      | Underlying Function          | Purpose                          |
|--------------------|------------------------------|----------------------------------|
| `search_templates` | `list_templates()`           | Search/filter templates          |
| `get_template`     | `get_template_by_id()`       | Get specific template by UUID    |
| `list_all_tags`    | `get_all_tags()`             | List all unique tags             |
| `count_templates`  | `get_templates_count()`      | Get total template count         |

## Tool Details

### search_templates

**Signature:**
```python
def search_templates(
    query: str | None = None,
    fields: list[str] | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]
```

**Features:**
- Free-text search in name/description
- Filter by tags (OR logic)
- Select specific fields to return
- Returns all templates if no filters provided

**Example:**
```python
search_templates(
    query="agent",
    tags=["chatbots", "rag"],
    fields=["id", "name", "description"]
)
```

### get_template

**Signature:**
```python
def get_template(
    template_id: str,
    fields: list[str] | None = None,
) -> dict[str, Any] | None
```

**Features:**
- Retrieve by exact UUID match
- Optional field selection
- Returns None if not found

**Example:**
```python
get_template(
    template_id="0dbee653-41ae-4e51-af2e-55757fb24be3",
    fields=["name", "description", "tags"]
)
```

### list_all_tags

**Signature:**
```python
def list_all_tags() -> list[str]
```

**Features:**
- Returns all unique tags across templates
- Sorted alphabetically
- No parameters needed

**Example:**
```python
tags = list_all_tags()
# Returns: ['agent', 'agents', 'assistants', 'chatbots', ...]
```

### count_templates

**Signature:**
```python
def count_templates() -> int
```

**Features:**
- Returns total count of available templates
- No parameters needed

**Example:**
```python
count = count_templates()
# Returns: 33
```

## Usage Modes

### 1. MCP Protocol (Primary Use)

Run as an MCP server for AI assistants like Claude:

```bash
# Start server
python -m langflow.agentic.mcp.cli

# Configure in Claude Desktop
{
  "mcpServers": {
    "langflow-agentic": {
      "command": "python",
      "args": ["-m", "langflow.agentic.mcp.cli"],
      "cwd": "/path/to/langflow/src/backend/base"
    }
  }
}
```

### 2. Direct Python Import

Use tool functions directly in Python code:

```python
from langflow.agentic.mcp.server import (
    search_templates,
    get_template,
    list_all_tags,
    count_templates
)

# Use functions directly
templates = search_templates(query="agent")
tags = list_all_tags()
```

### 3. CLI Commands

Command-line interface for testing and management:

```bash
# List available tools
python -m langflow.agentic.mcp.cli --list-tools

# Show version
python -m langflow.agentic.mcp.cli --version

# Start server
python -m langflow.agentic.mcp.cli
```

## Testing Infrastructure

### Test Coverage

18 unit tests across 4 test classes:

1. **TestMCPServer** (2 tests)
   - Server instance creation
   - Server configuration

2. **TestToolFunctions** (11 tests)
   - Basic functionality for each tool
   - Parameter variations
   - Field selection
   - Error cases

3. **TestToolIntegration** (3 tests)
   - Cross-tool consistency
   - Data integrity

4. **TestErrorHandling** (2 tests)
   - Edge cases
   - Invalid inputs

### Running Tests

```bash
# Run all tests
uv run pytest langflow/agentic/mcp/test_server.py -v

# Run specific test class
pytest langflow/agentic/mcp/test_server.py::TestToolFunctions -v

# Run with coverage
pytest langflow/agentic/mcp/test_server.py --cov=langflow.agentic.mcp
```

## Data Flow

```
┌─────────────────────┐
│   AI Assistant      │
│   (Claude, etc.)    │
└──────────┬──────────┘
           │ MCP Protocol (stdio)
           ↓
┌─────────────────────┐
│   FastMCP Server    │
│   (server.py)       │
└──────────┬──────────┘
           │ Function calls
           ↓
┌─────────────────────┐
│   Tool Wrappers     │
│   @mcp.tool()       │
└──────────┬──────────┘
           │ Implementation calls
           ↓
┌─────────────────────┐
│  Template Search    │
│  (utils/template_   │
│   search.py)        │
└──────────┬──────────┘
           │ File I/O
           ↓
┌─────────────────────┐
│  Starter Projects   │
│  JSON Templates     │
│  (initial_setup/)   │
└─────────────────────┘
```

## Key Design Decisions

### 1. Wrapper Pattern

Tool functions wrap underlying implementations rather than exposing them directly:

**Rationale:**
- Decouples MCP interface from implementation
- Allows renaming tools without changing implementations
- Enables parameter adaptation if needed
- Clearer separation of concerns

### 2. Field Selection

All search tools support optional field selection:

**Rationale:**
- Reduces payload size for large templates
- Allows AI to request only needed data
- Improves performance
- Maintains backward compatibility (returns all if None)

### 3. Real Template Testing

Tests use actual starter project templates, not mocks:

**Rationale:**
- Validates against production data
- Catches schema changes
- Tests real-world scenarios
- Provides confidence in deployments

### 4. FastMCP Choice

Using FastMCP library instead of custom MCP implementation:

**Rationale:**
- Less code to maintain
- Standard MCP protocol compliance
- Automatic schema generation
- Built-in CLI and utilities
- Well-documented and tested

## Extension Points

### Adding New Tools

To add a new tool:

1. **Create implementation** in `utils/` or appropriate module
2. **Import in server.py**
3. **Add @mcp.tool() decorator**
4. **Write comprehensive docstring**
5. **Add tests** in `test_server.py`
6. **Update documentation**

Example:
```python
# 1. Implementation (utils/flows.py)
def list_flows(user_id: str) -> list[dict]:
    """List user's flows."""
    return get_user_flows(user_id)

# 2. Add to server.py
from langflow.agentic.utils.flows import list_flows as _list_flows

@mcp.tool()
def list_flows(user_id: str) -> list[dict]:
    """List all flows for a user.

    Args:
        user_id: The user's unique identifier

    Returns:
        List of flow objects
    """
    return _list_flows(user_id)
```

### Configuration

For production, consider adding:
- Caching layer for templates
- Rate limiting per tool
- Authentication/authorization
- Logging and monitoring
- Configuration file support

### Alternative Transports

While the current implementation uses stdio (standard for MCP), FastMCP supports:
- HTTP/SSE streaming
- WebSocket connections
- Custom transports

See FastMCP documentation for details.

## Performance Characteristics

### Current Implementation

- **Template Loading**: O(n) where n = number of templates (33)
- **Search**: O(n) linear search through templates
- **Tag Filtering**: O(n*m) where m = average tags per template
- **Field Selection**: O(k) where k = number of fields

### Scaling Considerations

For larger deployments:

1. **Caching**: Add LRU cache for hot templates
2. **Indexing**: Pre-build search indexes
3. **Database**: Move to PostgreSQL/MongoDB for complex queries
4. **Pagination**: Add offset/limit parameters
5. **Streaming**: Stream large result sets

## Dependencies

### Required

- **Python**: 3.10+
- **fastmcp**: FastMCP library
- **langflow**: Parent Langflow installation

### Optional

- **pytest**: For running tests
- **uv**: For faster Python environment management

## Version History

- **v1.0.0** (2025): Initial FastMCP implementation
  - 4 tools: search_templates, get_template, list_all_tags, count_templates
  - 18 unit tests
  - Complete documentation
  - CLI interface

## Future Enhancements

Potential additions:

1. **More Tools**
   - Flow management (list, create, update, delete)
   - Component search and documentation
   - User management
   - Execution/run management

2. **Enhanced Search**
   - Fuzzy matching
   - Ranking/relevance scoring
   - Advanced filtering (date ranges, etc.)
   - Full-text search with Elasticsearch

3. **Caching & Performance**
   - Redis integration
   - Template pre-loading
   - Query optimization

4. **Security**
   - Authentication tokens
   - Rate limiting
   - Audit logging
   - Permission checks

5. **Monitoring**
   - Tool usage metrics
   - Performance tracking
   - Error reporting
   - Health checks

## References

- **FastMCP**: https://github.com/jlowin/fastmcp
- **MCP Spec**: https://modelcontextprotocol.io/
- **Langflow**: https://github.com/langflow-ai/langflow
- **Claude MCP**: https://docs.anthropic.com/claude/docs/mcp

## Contributing

When contributing to this MCP server:

1. Follow the wrapper pattern for new tools
2. Add comprehensive type hints
3. Write clear docstrings (they become tool descriptions)
4. Include unit tests for all tools
5. Update documentation
6. Test with Claude Desktop before submitting

## License

This code is part of Langflow and follows the same license as the parent project.
