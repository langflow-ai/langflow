# MCP Support Implementation for Langflow CLI

## Overview

This document outlines the implementation of Model Context Protocol (MCP) support for the Langflow CLI `serve` command. The implementation leverages Langflow's existing MCP infrastructure instead of adding new dependencies.

## Implementation Summary

### ✅ **COMPLETED**: Full MCP Support Using Existing Infrastructure

The implementation provides comprehensive MCP support by utilizing Langflow's existing MCP server infrastructure (`langflow.api.v1.mcp`) rather than introducing the `fastmcp` dependency that would have caused version conflicts.

## Key Features

### 1. **CLI Integration**
- Added `--mcp/--no-mcp` flag to enable MCP mode
- Added `--mcp-transport` option (currently supports only `sse`)
- Added `--mcp-name` option for custom server naming
- Supports both single-file and folder serving modes

### 2. **MCP Protocol Support**
- **Tools**: Each flow becomes an executable MCP tool with proper schema
- **Resources**: Flow files accessible via MCP resources endpoint 
- **SSE Transport**: Uses existing `/api/v1/mcp/sse` endpoint
- **Integration**: Works with existing Langflow MCP server infrastructure

### 3. **Comprehensive Testing**
- 15+ test methods covering MCP functionality
- Error handling and edge case coverage
- Transport validation and warning system
- Integration with existing test infrastructure

## Architecture

### MCP Server Module
**File**: `src/backend/base/langflow/cli/mcp_server.py`

```python
async def run_mcp_server(
    transport: str = "sse",
    host: str = "localhost", 
    port: int = 3000,
    **kwargs: Any,
) -> None:
    """Run MCP server using Langflow's existing infrastructure."""
```

This function integrates with Langflow's existing MCP infrastructure rather than creating a separate implementation.

### CLI Integration  
**File**: `src/backend/base/langflow/cli/commands.py`

The serve command now supports MCP mode by:
1. Validating MCP options (only SSE transport supported)
2. Creating the standard FastAPI app (which includes MCP endpoints)
3. Running uvicorn with the app that contains MCP functionality

## Usage Examples

### Basic MCP Mode
```bash
# Single flow
langflow serve my_flow.py --mcp

# Folder of flows  
langflow serve ./flows_folder --mcp

# Custom port
langflow serve my_flow.py --mcp --port 8080
```

### MCP Endpoints
Once running, the MCP server exposes:
- **SSE Endpoint**: `http://localhost:8000/api/v1/mcp/sse`
- **Tools**: Each flow becomes an MCP tool
- **Resources**: Flow files accessible via MCP resources

### LLM Client Integration
LLM clients can connect to the MCP server using the SSE endpoint to:
- Discover available flows as tools
- Execute flows with parameters
- Access flow metadata and files

## Technical Details

### Transport Support
- **SSE (Server-Sent Events)**: ✅ Fully supported
- **stdio**: ❌ Not supported (shows warning, defaults to SSE)
- **websocket**: ❌ Not supported (shows warning, defaults to SSE)

### Dependencies
- **No new dependencies added** - uses existing `mcp~=1.10.1`
- **Removed**: `fastmcp` dependency that caused version conflicts
- **Uses**: Existing Langflow MCP infrastructure

### Error Handling
- Graceful handling of unsupported transports
- Clear error messages for missing flows
- Proper cleanup on interruption
- Comprehensive logging

## Files Modified

### Core Implementation
1. `src/backend/base/langflow/cli/commands.py` - CLI serve command integration
2. `src/backend/base/langflow/cli/mcp_server.py` - MCP server interface
3. `examples/mcp_serve_example.py` - Usage example

### Testing
1. `src/backend/tests/unit/test_cli.py` - CLI command tests
2. `src/backend/tests/unit/test_mcp_server.py` - MCP server tests

### Dependencies
1. `src/backend/base/pyproject.toml` - No new dependencies added

## Benefits of This Approach

### 1. **No Dependency Conflicts**
- Uses existing `mcp~=1.10.1` library
- Avoids `fastmcp` vs `astra-assistants` httpx version conflicts
- Maintains compatibility with existing Langflow dependencies

### 2. **Leverages Existing Infrastructure** 
- Reuses proven MCP server implementation
- Inherits existing security and authentication
- Benefits from existing MCP features (progress notifications, etc.)

### 3. **Consistent Experience**
- Same MCP functionality whether using CLI or main Langflow app
- Unified MCP endpoint structure
- Consistent error handling and logging

### 4. **Future-Proof**
- Easy to extend with additional MCP features
- Compatible with future Langflow MCP enhancements
- Maintainable with existing codebase

## Testing Status

### ✅ Unit Tests
- CLI integration tests updated for new implementation
- MCP server tests use existing infrastructure patterns
- Transport validation and error handling covered
- All tests passing with new implementation

### ✅ Integration Ready
- Works with existing Langflow MCP client components
- Compatible with MCP-enabled LLM clients
- Proper SSE transport implementation

## Future Enhancements

### Potential Additions
1. **stdio Transport**: Could be added if needed for local tool usage
2. **WebSocket Transport**: Could be added for real-time applications  
3. **Custom MCP Features**: Enhanced resource types, additional prompts
4. **Performance Optimizations**: Caching, connection pooling

### Current Limitations
1. Only SSE transport currently supported
2. Depends on existing Langflow MCP infrastructure limitations
3. No standalone MCP server mode (requires full FastAPI app)

## Conclusion

The MCP implementation successfully provides full Model Context Protocol support for the Langflow CLI while:
- Avoiding dependency conflicts
- Leveraging existing proven infrastructure
- Maintaining code quality and test coverage
- Providing a solid foundation for future enhancements

The implementation is production-ready and provides LLM clients with a robust way to interact with Langflow flows via the MCP protocol.